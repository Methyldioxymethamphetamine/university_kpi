# P2A — Acquisition gate

**Entry gate:** `gate/P1-spike.md` ends with `P1 CLEAR — A/B/C all PASS. Proceed to P2A.` [VERIFIED]

**Scope:** acquisition layer only — bytes and provenance, zero parsing (P-3). Built:

```
registry/IN_sources.yaml     (edited — see §2)
registry/US_sources.yaml     (new — see §1)
acquire/
  registry.py                 SourceRegistry: YAML -> scrapy.Request objects
  storage.py                  content-addressed write-once raw store
  manifestlog.py               docs/<sha8>/manifest.json + blocked-attempt log
  pipelines.py                 ManifestPipeline (manifest write, THEN raw write)
  settings.py                  ROBOTSTXT_OBEY, AUTOTHROTTLE, JOBDIR, User-Agent
  spiders/sources.py           the one spider, two entry types, one fetch path
scripts/run_acquire.py        runs the crawl, then self-verifies (P-10)
raw/sha256/xx/yy/<sha>.ext
docs/<sha8>/manifest.json
docs/_blocked/<source_id>-<period>-<run_id>.json   (see §4 — not in the original file list; required by the STOP CONDITION)
```

`P-3` check, run against the finished tree: [VERIFIED]

```
$ grep -rniE "docling|pypdfium|fitz|pymupdf|BeautifulSoup|bs4|lxml|html\.parser|pdfplumber|PyPDF" acquire/
(no matches other than two comments naming P-3 itself)
```

---

## 0. One deviation from the literal file list, made explicit up front

PROMPTS.md P2A's file list names only `registry/IN_sources.yaml`. But its own STOP
CONDITION says *"If you cannot acquire Sandip or **MIT**..."*, and
`INSTRUCTIONS.md` §10 makes "three institutions acquired, twice" the iteration-1
acceptance bar. MIT is a US source; the schema in `PROMPTS.md` P2D
(`source.country`) and `findings/iteration-1-source-investigation.md` §3.4
("adding the US is genuinely a config change: a new source registry") both
point the same way. So `registry/US_sources.yaml` was added as a sibling file,
picked up by the same glob (`registry/*_sources.yaml`) with zero code change —
this is the "source is data, not code" law applied to *which country*, not
just which institution. Flagging this as a judgment call rather than silently
either skipping MIT or hand-waving it into `IN_sources.yaml`. [ASSUMED — a
reviewer who wanted this named literally in PROMPTS.md before being built
should say so; nothing here is hard to rename.]

---

## 1. `registry/US_sources.yaml` (new)

MIT's Common Data Set has no enumerable ID or stable URL template the way
NIRF's PDF path does — each year is its own page under `ir.mit.edu/projects/`,
discoverable only by visiting the site. Rather than force a fake "pattern"
with a fabricated enumerator, both years are `type: adhoc_url` entries — a
pasted link is a registry entry (PROMPTS.md P2A). Both fetched and returned
200 during this phase. [VERIFIED]

```yaml
country: US
sources:
  - source_id: mit_common_data_set_2025_26
    type: adhoc_url
    url: "https://ir.mit.edu/projects/2025-26-common-data-set/"
    period_type: academic_year
    period_value: "2025-26"
  - source_id: mit_common_data_set_2024_25
    type: adhoc_url
    url: "https://ir.mit.edu/projects/2024-25-common-data-set/"
    period_type: academic_year
    period_value: "2024-25"
```

(condensed — the actual file also carries `institution_code`, `institution_name`,
`expected_content_type`, and `robots_checked_at`/`terms_reviewed_at: null`.)

## 2. `registry/IN_sources.yaml` (edited)

IIT Bombay's entry is unchanged from the P1-era scaffold. Sandip's entry
changed in one substantive way: the original `enumerator.filter:
"NIRF-Report-{year}_Overall"` template was replaced with explicit, per-year
`title_contains` strings, because **the scaffold's assumption of a stable
filename convention across years is false, verified by actually calling the
API** (P-12):

```
$ GET https://sitrc.sandipfoundation.org/wp-json/wp/v2/media?per_page=100&search=nirf&_fields=source_url,title
2025 title: "NIRF Report 2025_Overall"                              <- matches the old template (mod dash/space)
2024 title: "Submitted Institute Data for NIRF 2024 _Overall"        <- does NOT match it at all
```

Had this shipped as originally scaffolded, 2024 would have silently yielded
zero matches — not a crash, a quiet gap in an enumerator loop, which is
exactly the failure shape `CLAUDE.md` calls out. [VERIFIED, 2026-09-14]

---

## 3. What was actually acquired — three runs, real network, real results

Two runs (`run1`, `run2`) are the acceptance evidence PROMPTS.md asks for. A
third (`verify-only`) was run afterward purely to confirm §5's MIT finding
wasn't a one-off; its numbers are folded into the self-verification output
below and flagged where relevant.

### IIT Bombay — PASS, fully idempotent

```
run1: https://www.nirfindia.org/nirfpdfcdn/2024/pdf/Overall/IR-O-U-0306.pdf -> 200, sha256=d2c9d5c2...
run1: https://www.nirfindia.org/nirfpdfcdn/2025/pdf/Overall/IR-O-U-0306.pdf -> 200, sha256=e9a1d469... (matches P1's CHECK A hash exactly)
run2: same two URLs -> 200, IDENTICAL sha256 both times, ZERO new raw/ files
```

[VERIFIED] Both manifests (`docs/d2c9d5c2/manifest.json`,
`docs/e9a1d469/manifest.json`) show two `runs` entries each (`run1`, `run2`),
one `sha256`, one raw file. This is real idempotency, achieved by
**content-hash match, not server-side 304** — see §6, the server never once
returned 304 even when handed its own ETag back.

### Sandip SITRC — discovery mechanism verified, download blocked. FINDING, not silently skipped.

```
run1: GET .../wp-json/wp/v2/media?...search=nirf -> 200, 28 items
      matched year=2025 -> "NIRF Report 2025_Overall" -> https://.../NIRF-Report-2025_Overall.pdf   (1 hit, correct)
      matched year=2024 -> "Submitted Institute Data for NIRF 2024 _Overall" -> https://.../Submitted-Institute-Data-for-NIRF-2024-_Overall.pdf (1 hit, correct)
      GET .../NIRF-Report-2025_Overall.pdf                                    -> BLOCKED, "Forbidden by robots.txt"
      GET .../Submitted-Institute-Data-for-NIRF-2024-_Overall.pdf              -> BLOCKED, "Forbidden by robots.txt"
run2: identical outcome
```

**Root cause, verified two ways, not assumed.** [VERIFIED]
`sitrc.sandipfoundation.org/robots.txt` contains, under `User-agent: *`:
`Disallow: /pdf/` and `Disallow: *.pdf`. Checked directly with `protego`
(the library Scrapy's `RobotsTxtMiddleware` itself uses) before writing any
crawler code:

```
protego.Protego.parse(robots_txt).can_fetch(
  "https://sitrc.sandipfoundation.org/wp-content/uploads/2025/02/NIRF-Report-2025_Overall.pdf",
  "kpi-pipeline-bot") -> False
protego....can_fetch(".../wp-json/wp/v2/media?...", "kpi-pipeline-bot") -> True
```

Then confirmed live, in the actual crawl (`robotstxt/forbidden: 2`,
`acquisition/blocked_by_policy: 2` in both runs' Scrapy stats; a
`docs/_blocked/sandip_sitrc_overall-<year>-<run_id>.json` file written for
each blocked attempt instead of the request silently vanishing).

**This is not a bug to route around.** `ROBOTSTXT_OBEY = True` is a hard
requirement of this phase. Sandip's own site disallows automated PDF
retrieval for any well-behaved crawler, full stop — the discovery step (which
robots.txt does allow) correctly finds both years' PDFs, but the pipeline
cannot legitimately download either one under this configuration.
**Architecture/process decision required, not made here:** either (a) this
document is acquired by a human and dropped in as a manually-provenanced
artifact rather than a crawled one, (b) someone with authority to do so
contacts the institution or reinterprets the robots directive, or (c) Sandip
is carried as "acquisition blocked, by design, with evidence" into the demo
narrative itself — which, given `CLAUDE.md`'s own framing of Sandip as the
institution whose own site is *more* complete than the NIRF portal copy, is
not necessarily a bad story to tell a president. Not my call to make from
inside this phase.

### MIT — fetched successfully every time, but NOT idempotent at the byte level. FINDING, not silently skipped.

```
run1: https://ir.mit.edu/projects/2025-26-common-data-set/ -> 200, sha256=dc2701ee...
run1: https://ir.mit.edu/projects/2024-25-common-data-set/ -> 200, sha256=e25cab78...
run2: same two URLs -> 200, DIFFERENT sha256 both times (96acff75..., 879e1cad...)
verify-only: same two URLs -> 200, DIFFERENT sha256 again, a third pair
```

**Root cause, isolated by diffing the two run1/run2 bodies, not assumed.**
[VERIFIED] The only difference between run1's and run2's fetch of the
2025-26 page is one `<script>` tag, four levels deep in the page, injected by
Cloudflare's bot-challenge platform:

```
< ...__CF$cv$params={r:'a3aef206eaefff66',t:'MTc4OTM4NDIyOA=='}...
---
> ...__CF$cv$params={r:'a3aef263aeff3fa2',t:'MTc4OTM4NDI0Mw=='}...
```

`r` and `t` are a per-request random token and timestamp. Every byte of
actual page content is identical; this one injected line changes on every
single fetch, so a whole-body sha256 can never be stable for this source.
MIT sends no `ETag` / `Last-Modified` at all (confirmed via `HEAD`, separate
from the robots question), so the conditional-refetch path that saves IIT
Bombay isn't available here either.

**Not fixed here, deliberately.** Stripping or normalizing the Cloudflare
tag before hashing would mean the acquisition layer starts interpreting HTML
content to decide what "counts" as the document — exactly what P-3 exists to
forbid. The honest state is: MIT acquisition works, but every run currently
mints a new "artifact" in the content-addressed store for a page that hasn't
actually changed. **Architecture decision required:** whether de-duplication
for this kind of source belongs in P2B/P2C (e.g. compare converted/extracted
text, not raw bytes) or whether the raw store needs a second identity concept
beyond pure content-hash. Flagged, not decided.

---

## 4. `docs/_blocked/` — not in the original file list

The STOP CONDITION requires reporting an unacquirable institution rather than
silently skipping it. A blocked or errored request produces no sha256 and no
manifest row by construction (there's no content to key it on), so a
5th artifact type was added: one JSON file per blocked attempt per run, under
`docs/_blocked/`. Six exist after three runs (2 per run x years, Sandip only).
[ASSUMED — this is the mechanism chosen to satisfy "do not silently skip an
institution"; a reviewer may want this shaped differently, e.g. as manifest
rows with a null sha256 instead of a separate directory.]

---

## 5. Self-verification (P-10), actual output, all three runs

```
$ python scripts/run_acquire.py --run-id run1
=== P2A self-verification (P-10) ===
raw file count: 4
raw total bytes: 371263
distinct sha256 (manifests under docs/): 4
distinct sha256 (filenames under raw/):  4
http_status distribution (per run entry, all manifests): {200: 4}
manifest sha256 with a body-bearing run but no raw file on disk: []
raw files whose recomputed sha256 doesn't match their manifest: []
blocked/error attempts recorded (never silently skipped): 2
SELF-VERIFICATION: PASS

$ python scripts/run_acquire.py --run-id run2
=== P2A self-verification (P-10) ===
raw file count: 6
raw total bytes: 718845
distinct sha256 (manifests under docs/): 6
distinct sha256 (filenames under raw/):  6
http_status distribution (per run entry, all manifests): {200: 8}
manifest sha256 with a body-bearing run but no raw file on disk: []
raw files whose recomputed sha256 doesn't match their manifest: []
blocked/error attempts recorded (never silently skipped): 4
SELF-VERIFICATION: PASS

$ python scripts/run_acquire.py --run-id verify-only   # 3rd confirmatory run, not part of the acceptance pair
=== P2A self-verification (P-10) ===
raw file count: 8
raw total bytes: 1066427
distinct sha256 (manifests under docs/): 8
distinct sha256 (filenames under raw/):  8
http_status distribution (per run entry, all manifests): {200: 12}
manifest sha256 with a body-bearing run but no raw file on disk: []
raw files whose recomputed sha256 doesn't match their manifest: []
blocked/error attempts recorded (never silently skipped): 6
SELF-VERIFICATION: PASS
```

[VERIFIED] All three runs: zero missing referenced files, zero hash
mismatches — the internal integrity check the script performs (every manifest
whose runs include a body-bearing fetch has exactly the raw file its sha256
says it should) held every time. This is a narrower claim than "acquisition
is fully idempotent" — see §3, where IIT Bombay is idempotent and MIT is not,
and both are visible precisely *because* this script counts distinct sha256
rather than assuming file count == fetch count.

Raw file count growing 4 -> 6 -> 8 across the three runs is **entirely** the
MIT non-determinism from §3, not a bug: IIT Bombay contributed the same 2
files every time; Sandip contributed 0 (blocked); MIT contributed 2 new ones
per run.

---

## 6. Everything tagged [ASSUMED], with what would confirm or overturn it

- **NIRF idempotency is hash-match, not 304.** [VERIFIED, not assumed —
  confirmed the origin returns 200 even given back its own exact ETag and
  Last-Modified via a raw HTTP request outside Scrapy.] Nothing to confirm
  further; this is closed.
- **Extension-by-Content-Type map in `acquire/storage.py`** (`application/pdf`,
  `text/html`, `application/json` only, else `.bin`). Fitted to exactly the
  three iteration-1 sources' observed headers. Confirmed by: any new source
  registry entry whose Content-Type isn't one of these three and needs a
  real extension.
- **`docs/<sha8>/manifest.json` as one file with a growing `runs` list**,
  rather than one file per run. PROMPTS.md specifies the file's *fields*, not
  this shape; chosen so a second identical fetch is a new *row*, not an
  overwritten file, consistent with docs/ being regenerable but not
  history-destroying. Confirmed/overturned by: a reviewer preferring a
  flatter one-manifest-per-run-per-artifact layout.
- **JSON-parsing the WordPress media-search response to pick a follow-up
  URL is acquisition-layer discovery, not the P-3-prohibited "parsing."**
  This is a boundary judgment, flagged explicitly rather than assumed silently.
  The rule as written bans importing "a PDF library, an HTML parser, or
  Docling" in `acquire/`; nothing here imports an HTML parser, and the JSON
  read never inspects document *content*, only a structural API's own
  `title`/`source_url` fields to decide which link to follow next — the same
  category of thing a spider does with a sitemap or a directory listing.
  Confirmed/overturned by: reviewer instruction that this belongs in a
  different layer instead.
- **`period_value` for MIT is the literal CDS-year label from the URL slug**
  (`"2025-26"`, `"2024-25"`), not a bare year integer (P-9). Confirmed by
  checking `academic_year` `period_type` semantics hold once P2E maps this
  source's fields.
- **`registry/US_sources.yaml` as a new file rather than folding MIT into
  `IN_sources.yaml`** — see §0.
- `robots_checked_at` / `terms_reviewed_at` left `null` on every entry in
  both registry files, surfaced here as [OPEN] per PROMPTS.md P2A — a human
  fills these in before any full run, not this phase.

---

## STOP CONDITION

Both non-IIT-Bombay institutions hit a genuine, verified blocker:
**Sandip's PDF cannot be fetched at all under required `ROBOTSTXT_OBEY=True`**
(§3), and **MIT fetches correctly but is not idempotent at the content-hash
level** because of a Cloudflare-injected per-request token (§3). Neither was
routed around, tuned away, or silently skipped — both are reported here with
the request that was blocked, why, and the evidence, per the STOP CONDITION.
These are architecture/process decisions for the reviewer/integrator, not
something this phase resolved unilaterally.

**Not proceeding to P2B this session.**

---

## 2026-09-14 — Recorded decision: `ROBOTSTXT_OBEY` set to `False`, globally

> ROBOTSTXT_OBEY=False, set 2026-09-14, by dushyant7563@gmail.com.
> Decision: college project, showcase only, not used against real
> production institutions beyond the three in iteration 1 scope. Sandip's
> site disallows *.pdf under a blanket User-agent: * rule that also
> covers this project's own legitimate target files
> (see gate/P2A-acquire.md §2 for the original finding). Global override
> chosen over a per-source registry field for speed, knowingly trading
> away future per-source auditability. Also recorded in CLAUDE.md's
> Recorded decisions section.

Same text as the comment placed directly above `ROBOTSTXT_OBEY = False` in
`acquire/settings.py`, and the same decision already recorded in
`CLAUDE.md`'s "Recorded decisions" section (2026-09-14 entry) — reproduced
here so the audit trail is visible in this gate file too, not only in a
code comment and a rules file. This entry does not retract the STOP
CONDITION above: it stood, correctly, as this phase's real result under the
configuration active at the time. What follows below (§ Sandip re-fetch) is
new work performed under the new configuration, appended, not a rewrite of
what already happened.

---

## Sandip re-fetch, under `ROBOTSTXT_OBEY=False`

See below for the real re-fetch output.
