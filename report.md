# Debugging findings — P1 / P2A

Working notes for whoever hits these again. Not a gate deliverable — those
are `gate/P1-spike.md` and `gate/P2A-acquire.md`; this is the "why did that
break" reference underneath them.

---

## 1. Scrapy 2.19 silently drops a spider that only defines `start_requests()`

**Symptom:** `scripts/run_acquire.py` ran clean, `finish_reason: finished`,
`elapsed_time_seconds: 0.002`, zero requests, zero errors, zero log lines
indicating anything was wrong. Self-verification correctly reported 0 files
— nothing to catch, because nothing crashed.

**Cause:** Scrapy 2.13 replaced the spider entry point with an async
`Spider.start()` method. `Spider` no longer defines `start_requests` at all
(confirmed: `hasattr(Spider, 'start_requests')` is `False` on 2.19.0). A
subclass that only defines a *sync* `start_requests()` — the pre-2.13 API —
is just never called; Scrapy falls back to its default `start()`, which
reads `self.start_urls` (empty), and the crawl "finishes" having done
nothing.

**Fix:** define `async def start(self):` and `yield` requests from it
(`acquire/spiders/sources.py`). Scrapy docs say defining *both* `start()` and
a legacy `start_requests()` is the way to support pre-2.13 Scrapy too — not
needed here since `pyproject.toml` pins `scrapy>=2.14`.

**Lesson for next time:** an empty-but-clean Scrapy run (0 requests, no
errors, `finished`) is not evidence the registry/URLs are fine — it's the
signature of this exact trap. Check `item_scraped_count` and
`downloader/request_count` in the stats dump before trusting a "finished"
status.

---

## 2. Sandip's PDFs are unreachable under `ROBOTSTXT_OBEY=True`, full stop

**Symptom:** discovery (the `/wp-json/wp/v2/media` search) succeeds and
correctly resolves both 2024 and 2025 PDF URLs; the follow-up GET to each
PDF fails with `Forbidden by robots.txt` before ever hitting the network.

**Cause:** `sitrc.sandipfoundation.org/robots.txt` has, under `User-agent: *`:
```
Disallow: /pdf/
Disallow: /pdfs/
Disallow: *.pdf
```
`*.pdf` with no anchor matches any path containing `.pdf`, which covers the
NIRF submission URLs (`/wp-content/uploads/.../NIRF-Report-2025_Overall.pdf`)
even though they're nowhere near `/pdf/` or `/pdfs/`. This is *not* limited
to search-engine bots — it's under the generic `User-agent: *` block, so it
applies to any well-behaved crawler, including ours.

**Verified two independent ways** (never trust one):
1. Static: `protego.Protego.parse(robots_txt).can_fetch(url, "kpi-pipeline-bot")`
   → `False` for the PDF, `True` for the media-search API.
2. Live: the actual Scrapy run shows `robotstxt/forbidden: 2`,
   `acquisition/blocked_by_policy: 2`, and `docs/_blocked/sandip_sitrc_overall-*.json`
   written for each attempt.

**Status:** unresolved by design — this is an architecture/policy call
(hand-supply the document? get explicit permission? treat "blocked, with
evidence" as part of the demo narrative?), not something to route around
inside the acquisition layer. See `gate/P2A-acquire.md` §3.

**If revisiting:** don't just flip `ROBOTSTXT_OBEY=False` — that's the
literal thing PROMPTS.md's P2A requirements list forbids disabling. Any fix
needs a human decision recorded somewhere durable (a registry field, a gate
file, a commit message), not a silent settings change.

---

## 3. Sandip's own filename convention is not stable across years

**Symptom:** the original registry scaffold used one template,
`"NIRF-Report-{year}_Overall"`, for every enumerated year.

**Cause:** actual title strings returned by the WordPress media API:
- 2025: `"NIRF Report 2025_Overall"` (matches the template, modulo dash/space)
- 2024: `"Submitted Institute Data for NIRF 2024 _Overall"` (does **not**
  match at all)

A single templated filter would have silently produced zero hits for 2024 —
no error, just a missing year, which is exactly the "confident but wrong"
failure shape this whole project exists to catch, just one layer up from
where `CLAUDE.md` originally found it (rotation) or PROMPTS.md's own P1
CHECK C bug (wrong document scoped).

**Fix:** `registry/IN_sources.yaml`'s `sandip_sitrc_overall` entry now lists
explicit, per-year `title_contains` strings, each individually verified
against a real API response (P-12: fetched, not guessed).

**Lesson:** don't trust a single template across years for anything on this
site without pulling the real listing first. If a third year gets added,
fetch `wp-json/wp/v2/media?search=nirf` again and read the actual title
before writing the YAML entry.

---

## 4. MIT's Common Data Set page is never byte-identical between fetches

**Symptom:** IIT Bombay's two PDFs hash identically across three separate
live crawl runs. MIT's two HTML pages hash *differently* every single run —
6 distinct MIT artifacts after 3 runs, for what should be 2.

**Cause, isolated by diffing two fetches of the same URL:** Cloudflare
(fronting `ir.mit.edu`) injects a bot-challenge script with a random
per-request token into every response:
```
window.__CF$cv$params={r:'<random>', t:'<timestamp>'};
```
Everything else in the ~170KB page is byte-identical between fetches. There
is no `ETag` or `Last-Modified` on this resource either (checked via `HEAD`
separately from the robots question), so there's no conditional-refetch
escape hatch — every fetch is a full body compare, and the compare always
loses on this one injected line.

**Status:** unresolved by design. Fixing this means either (a) stripping/
normalizing known-volatile content before hashing — which turns the
acquisition layer into something that interprets HTML content, i.e. exactly
what P-3 forbids — or (b) pushing de-duplication downstream to P2B/P2C,
comparing extracted text rather than raw bytes. Not decided; see
`gate/P2A-acquire.md` §3.

**If revisiting:** don't "fix" this by regex-stripping the CF script inside
`acquire/`. If dedup at the raw-store layer is ever wanted, it needs its own
deliberate design (e.g. a second, content-agnostic identity key) reviewed as
an actual architecture change, not a quiet patch.

---

## 5. NIRF's CDN never honors conditional GET, even with the exact original ETag

**Symptom:** run2 against IIT Bombay's PDFs came back `200` both times, never
`304`, despite `acquire/spiders/sources.py` correctly attaching
`If-None-Match` / `If-Modified-Since` from the prior manifest.

**Checked before assuming a bug in our code:** replayed the request manually
outside Scrapy with the *exact* strong `ETag` and `Last-Modified` the origin
itself sent — still `200`. Consistent with the response's own
`Cache-Control: no-store, no-cache, must-revalidate` header: the origin
(CloudFront-fronted) opts out of conditional-cache semantics entirely.

**Implication:** idempotency for this source is achieved entirely by our own
content-hash comparison at the raw-store layer (`write_once` in
`acquire/storage.py` skipping an existing sha256 path), not by the server.
That's fine — PROMPTS.md's acceptance criterion says "304 **or** hash match"
— but don't waste time debugging the conditional-header code if 304 never
shows up against this specific origin; it's the server, not us. (Scrapy's
`HttpCompressionMiddleware` also turns the origin's strong `ETag` into a weak
`W/"..."` one on our side because it decompressed the gzip body — checked
that this wasn't the cause either; the server ignores both forms equally.)

---

## 6. `PROMPTS.md`'s CHECK C was claimed-corrected but wasn't (P1, prior session)

**Symptom:** a prior P1 run's `gate/P1-spike.md` said CHECK C had been
"corrected in PROMPTS.md," but `prompts/PROMPTS.md` still contained the
original, uncorrected text (`3750000(...)` searched for inside IIT Bombay's
own document — a string that only exists in Sandip's file).

**Cause:** the correction was apparently decided but never actually written
back to `prompts/PROMPTS.md` — a claim about file state that didn't match
the file's actual content. `PROMPTS.md`'s mtime predated the gate file that
claimed the fix, confirming it.

**Lesson:** when a gate file says "X was corrected in file Y," re-read file Y
before trusting the claim and re-running against it — don't take a prior
session's self-report as ground truth. This is the same discipline
`CLAUDE.md`'s epistemic-tags table is trying to enforce, just applied to
"has this file actually changed" rather than to a data claim.

---

## Quick index — where each of these live in the actual code

| Finding | File(s) |
|---|---|
| §1 async `start()` | `acquire/spiders/sources.py` |
| §2 Sandip robots block | `registry/IN_sources.yaml` (comment), `acquire/manifestlog.py::record_blocked`, `docs/_blocked/*.json` |
| §3 Sandip filename instability | `registry/IN_sources.yaml` (`sandip_sitrc_overall.enumerator.matches`) |
| §4 MIT non-idempotency | `registry/US_sources.yaml`, `acquire/storage.py` |
| §5 conditional GET | `acquire/spiders/sources.py::_attach_conditional_headers` |
| §6 stale CHECK C | `gate/P1-spike.md` ("CHECK C (re-run)" section), `prompts/PROMPTS.md` |
