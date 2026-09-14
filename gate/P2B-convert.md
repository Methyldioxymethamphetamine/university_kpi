# P2B — Classify and convert gate

**Entry gate:** `gate/P2A-acquire.md` exists, self-verification passed (all
three runs, §5 of that file). [VERIFIED]

**Scope:** classification (per-artifact MIME from magic bytes, per-page
char/image/rotation profile, routing label) and Docling conversion
(`save_as_json()` only, P-2). Zero value extraction — no KPI knows what a
"median salary" is anywhere in this diff. Built:

```
classify/
  sniff.py          MIME from magic bytes (filetype lib + hand text-sniff)
  pdf_profile.py     per-page (chars, images, rotation) via pypdfium2
  html_profile.py    single-page (chars, images, has_table) via stdlib html.parser
  labels.py           PAGE_CHAR_THRESHOLD [ASSUMED] + routing rules
  artifact.py         classify_artifact(sha256) -> pages/*.json + manifest["classify"]
convert/
  docling_wrapper.py  DocumentConverter wrapper, save_as_json() only (P-2)
  assets.py           picture extraction -> docs/<sha8>/assets/
  regression.py       P1 CHECK B ported as an importable assertion
  artifact.py          convert_artifact(sha256) -> docs/<sha8>/docling.json + manifest["convert"]
scripts/
  run_classify.py     runs classify over every docs/*/manifest.json, self-verifies
  run_convert.py       runs convert, self-verifies by RE-READING docs/ from disk
tests/
  test_classify_labels.py        unit tests, threshold + mixed-mode + sniff
  test_p1_rotation_regression.py P1 CHECK B, permanent, runs real Docling
  test_p2_no_lossy_export.py     P-2 enforcement, greps convert/ for the call
docs/<sha8>/pages/NNN.json        per-page (chars, images, rotation) + label
docs/<sha8>/pages/NNN.png         rendered page (PDF only — see §4)
docs/<sha8>/assets/                extracted pictures (empty for iteration 1's
                                    real docs — see §3)
docs/<sha8>/docling.json           save_as_json() output, pdf_* / html_table only
docs/<sha8>/manifest.json          gains "classify" and "convert" blocks
```

`P-2` check, run against the finished tree: [VERIFIED]

```
$ grep -rn "\.export_to_markdown(\|\.export_to_html(" convert/
(no matches)
$ .venv/bin/python -m pytest tests/test_p2_no_lossy_export.py -q
1 passed
```

---

## 1. Label routing — what was actually classified

Ten artifacts exist under `docs/` (from P2A's acquired raw files): 2 from IIT
Bombay (one per NIRF year, both `pdf_digital`), 8 from MIT (4 acquisition
runs × 2 CDS years, each a distinct sha256 per §3 of `gate/P2A-acquire.md`'s
MIT non-idempotency finding — not deduplicated here, deliberately; see §5).
Sandip contributed zero artifacts to classify against — acquisition was
blocked by `robots.txt`, so there are no raw bytes to classify. That
institution's absence is already recorded in `docs/_blocked/`, not silently
dropped here a second time.

Re-run for this review, 2026-09-14T11:38Z, stdout captured verbatim (`> file
2>/dev/null`, so nothing below is edited or summarized), exit code checked
separately:

```
$ .venv/bin/python scripts/run_classify.py
=== P2B classify self-verification ===
artifacts classified: 10
label distribution: {'pdf_digital': 2, 'html_table': 8}
pages with zero extracted text: 0
classify errors: 0
SELF-VERIFICATION: PASS
$ echo $?
0
```

[VERIFIED] Every IIT Bombay page: `chars` in the low thousands, `images: 0`,
`rotation: 90` — matches P1 CHECK B's independent pypdfium2 finding exactly
(same tool, re-run here as a module instead of a spike script). Every MIT
artifact: `has_table: true`, tens of thousands of characters → `html_table`,
no artifact fell into `pdf_mixed`, `pdf_scan`, `json_api`, `office_doc`, or
`unknown` — because none of iteration 1's real sources produced one, not
because those branches are untested in isolation (see `tests/test_classify_labels.py`,
which exercises all seven labels including the three iteration 1 never sees
live, with crafted inputs).

---

## 2. The ~200-char threshold — stored, not just applied

`classify/labels.py:PAGE_CHAR_THRESHOLD = 200`, marked `[ASSUMED]` in code
with its provenance: the P0-era structural diagnostic on Sandip's Mandatory
Disclosure PDF (`notes/methodology.md` pattern **P6**: *"Under ~200 extracted
chars with images present → OCR path"*). Not re-fit here — Sandip's document
was never acquired (§1), so there is still only the one document this number
was ever fitted on. Per PROMPTS.md P2B's explicit instruction, the raw
`(chars, images)` pair is persisted per page (`docs/<sha8>/pages/NNN.json`),
not just the derived label, so re-tuning this threshold later is a re-query
over stored JSON, not a re-crawl or a re-conversion.

[ASSUMED] — confirmed or overturned by: acquiring a genuinely mixed-mode PDF
(Sandip's, once §5's architecture question is resolved, or the NAAC SSR
`PROMPTS.md` P2E's T4 names) and checking whether 200 correctly separates its
scan pages from its digital ones.

---

## 3. Docling conversion — real run, both institutions

Re-run for this review, 2026-09-14T11:38Z, stdout captured verbatim
(`> file 2>/dev/null` — the "Loading weights" progress bar Docling prints on
model load goes to stderr, not stdout, confirmed by capturing the two
streams separately; it is omitted here because it is not stdout, not because
it was edited out):

```
$ .venv/bin/python scripts/run_convert.py
=== P2B convert self-verification (re-read from disk) ===
artifacts converted: 10
artifacts skipped (out of iteration-1 scope): 0
artifacts errored: 0
label distribution (converted only): {'pdf_digital': 2, 'html_table': 8}
pages with zero extracted text (pdf_* only): 0
docling.json missing or unparseable: 0
doc items lacking page_no/bbox (pdf_* labels -- HARD FAILURE gate): 0
doc items lacking page_no/bbox (html_table labels -- reported only, not gated): 6688
P1 regression check failures: 0
SELF-VERIFICATION: PASS
$ echo $?
0
```

[VERIFIED] Re-run three times across this session (twice during the original
build, once for this review); identical output every time, `docs/`
regenerated cleanly (consistent with CLAUDE.md's "docs/ is regenerable" law
— nothing here is append-only the way `raw/` is).

### FINDING — the "0" that gates the exit code covers PDF-sourced items only

Answering directly, not left implicit in the line label above: the
self-verification's page_no/bbox check is **two separate counters, only one
of which gates the exit code.**

- `doc items lacking page_no/bbox (pdf_* labels -- HARD FAILURE gate): 0` —
  this is the number that can fail the build. It covers **only** items from
  `pdf_digital`/`pdf_mixed`/`pdf_scan` artifacts (IIT Bombay, both years —
  the only real `pdf_*` documents iteration 1 has). It is 0, correctly: all
  of IIT Bombay's text/table items carry both fields.
- `doc items lacking page_no/bbox (html_table labels -- reported only, not
  gated): 6688` — this covers MIT's 8 HTML artifacts. It is **not** 0, and
  it **cannot** be 0 under the current architecture: Docling's HTML backend
  (2.127.0, confirmed by direct inspection this session) returns `prov: []`
  for every text/table item it produces, because HTML has no page or
  coordinate space to report. This number is printed for visibility and does
  **not** affect `SELF-VERIFICATION: PASS`/exit code.

So: **the "exits 0" result does not mean every doc_item in the repository has
a page_no and a bbox.** It means every *PDF-sourced* doc_item does, and every
*HTML-sourced* one — all 6,688 of them — structurally cannot, by design of
the format, not by a bug in this phase's code. This is a defensible scoping
(a PDF item silently losing provenance is CLAUDE.md's named silent-failure
shape; an HTML item never having had it is a different, non-silent, known
property of the format) but it is a real scope narrowing of the check as
literally described in PROMPTS.md P2B ("the count of doc items lacking
page_no or bbox... exits non-zero"), and it is called out here explicitly
rather than left to be inferred from the parenthetical in the stdout label.

**IIT Bombay (`pdf_digital`, both years):** `docling.json` written via
`save_as_json()`, 4 pages, 17 tables, 0 pictures (matches classify's own
pypdfium2 count of 0 images/page — two independent tools agreeing), every
text/table item carries `page_no` + `bbox`.

**MIT (`html_table`, all 8):** `docling.json` written, 60 tables, 761 text
items recovered per artifact — but **zero** items carry `page_no`/`bbox`.
This is inherent to HTML (no pagination, no coordinate space), not a defect:
[VERIFIED] confirmed by direct inspection of Docling 2.127.0's HTML backend
output — every item's `prov` is `[]`. `scripts/run_convert.py` reports this
count (6,688 across all 8 artifacts) but does **not** gate the exit code on
it, on the reasoning that a PDF item silently losing provenance is CLAUDE.md's
named failure shape (fluent, wrong, no error) while an HTML item never having
had it is not the same failure at all. [ASSUMED — a reviewer could reasonably
want HTML held to some other provenance standard once P2C/P2E design the MIT
citation path; flagging the judgment call rather than burying it.]

**Assets:** `docs/<sha8>/assets/` created for every converted artifact;
empty for all 10, because `document.pictures` is empty for all 10 — IIT
Bombay has 0 images/page (P1 CHECK B and classify's own profile both already
said so) and MIT's HTML backend did not yield picture items either.
`generate_picture_images=True` is set on the PDF pipeline so a document that
does have figures would populate this directory without further code changes
— untested against a real case, since none of the ten artifacts has one.

---

## 4. Rendered page PNGs — PDF only, and why

`docs/<sha8>/pages/NNN.png` is produced for all 8 IIT Bombay pages via
`pypdfium2`'s `page.render()`, which bakes in the page's declared rotation —
[VERIFIED] the four rendered PNGs for the 2025 document are right-side-up
despite every page being `/Rotate 90` at the PDF level (same rotation value
P1 CHECK B independently confirmed).

MIT's HTML artifacts get **no** PNG. CLAUDE.md's settled stack (Scrapy /
Docling / pypdfium2 / Postgres) contains no headless-browser or HTML
rendering engine, so there is no tool in scope to produce a pixel-faithful
screenshot of an HTML page the way pypdfium2 does for a PDF page. Rather than
fake one (e.g. rendering the raw text as an image, which would not match
what a reviewer sees on the live site), each `html_table` page record is
written with no PNG, and this gap is surfaced here explicitly. **[OPEN]** —
settled by: a decision on whether MIT's click-through (D2 in the eventual
`docs/architecture.md`) needs a real screenshot (would mean adding a
headless-browser dependency, outside the currently "settled" stack table)
or can rely on `doc_item.text` + the source URL alone, without a rendered
rectangle.

---

## 5. P1 regression test — the load-bearing one

`gate/P1-spike.md`'s CHECK B, ported verbatim (same expected row, same
header, same uniqueness assertion) into `convert/regression.py`, wired to run
**automatically inside `convert/artifact.py`** whenever the artifact being
converted is `e9a1d469...` (the exact sha256 CHECK B verified against), and
also as a standalone permanent pytest test that runs real Docling against the
real acquired file, not a cached fixture:

```
$ .venv/bin/python -m pytest tests/test_p1_rotation_regression.py -v
tests/test_p1_rotation_regression.py::test_p1_check_b_regression PASSED
```

[VERIFIED] Both the automatic in-pipeline check (visible in
`docs/e9a1d469/manifest.json` → `convert.p1_regression_check.status: "PASS"`)
and the independent pytest run agree: the same row, same header, same
`page_no: 1`, `coord_origin: BOTTOMLEFT` bbox P1 originally found. If a future
Docling upgrade regresses rotation or table segmentation on this exact
document, both of these fail loudly — one at conversion time (raises inside
`convert_artifact`, aborting that artifact's conversion and recording
`status: "FAIL"` in its manifest rather than silently shipping a bad
`docling.json`), one in CI/pytest.

**Deliberately not generalised:** the specific expected values
(`1161/1059/1039/1030`) belong to this one document (2025's report). IIT
Bombay's 2024 report (`d2c9d5c2...`) is a different PDF with a different set
of academic-year columns and was **not** given its own golden-row assertion
— there is no independently-verified expected row for it recorded anywhere
in this repo to port. `[OPEN]` — closed by: hand-verifying one row from the
2024 document against the source PDF and adding a second golden fixture,
the same way P1 did for 2025.

---

## 6. Everything tagged `[ASSUMED]` / `[OPEN]`, with what would confirm or overturn it

- **`PAGE_CHAR_THRESHOLD = 200`** — see §2. Confirmed/overturned by acquiring
  a real mixed-mode or scanned PDF.
- **OCR disabled (`do_ocr = False`) in `convert/docling_wrapper.py`.**
  `[OPEN]`, not `[ASSUMED]` — this is a genuine capability gap, not a fitted
  constant. No acquired document currently needs OCR (IIT Bombay is fully
  digital, MIT is HTML), so the code path is unexercised. A `pdf_scan` or
  `pdf_mixed` artifact converted under this setting will come back with
  empty text on its scanned pages — visible in `scripts/run_convert.py`'s
  "pages with zero extracted text" line, not hidden — but will not be OCR'd.
  Confirmed/overturned by: acquiring Sandip's document (still blocked, see
  `gate/P2A-acquire.md` §3) or any other scanned source and deciding whether
  to turn OCR on.
- **HTML `prov: []` not gating self-verification's exit code** — see §3.
  `[ASSUMED]`, a judgment call, not a spec-mandated rule.
- **No PNG render for `html_table` pages** — see §4. `[OPEN]`, a real stack
  gap, not a shortcut taken quietly.
- **MIT's HTML-sourced values cannot carry the page+bbox citation PDF-sourced
  values carry.** `[OPEN]`, and the sharpest form of the finding above and of
  §4's PNG gap combined — see §7, a dedicated section, since this is a schema
  and diagram decision for P2D/P3 to inherit deliberately, not a detail to
  leave folded into a bullet.
- **MIT's 8 near-duplicate artifacts each converted independently, not
  deduplicated.** `[CARRIED-FORWARD]` from `gate/P2A-acquire.md` §3 and §6 —
  that file already flagged MIT's Cloudflare-token non-idempotency as an
  "architecture decision required... whether de-duplication... belongs in
  P2B/P2C." This phase did not resolve it; each of the 8 sha256s got its own
  `docling.json`, correct per-artifact but wasteful, and still an open
  question for whoever designs P2C/P2E's MIT profile.
- **`office_doc` / `json_api` / `unknown` labels have no live example.**
  `[ASSUMED]` the routing logic is correct based on unit tests with crafted
  inputs (`tests/test_classify_labels.py`), not a real acquired artifact.
  Confirmed/overturned by: any future source that actually produces one of
  these three.
- **A document matching no MIME classify/sniff.py recognises (`unknown`)
  never reaches `convert_artifact`.** `CONVERTIBLE_LABELS` in
  `convert/artifact.py` is an explicit allow-list
  (`pdf_digital`/`pdf_mixed`/`pdf_scan`/`html_table`); anything else raises
  `ConversionSkipped`, which `scripts/run_convert.py` reports by name rather
  than silently omitting. `[VERIFIED]` by inspection of the allow-list and
  the self-verification output's "artifacts skipped" line (0 here, since
  nothing classified as anything outside that set this run).

---

## 7. `[OPEN]` — MIT's citation model cannot match PDF's, and P2D/P3 need to account for that on purpose

This is not a new fact — §3's FINDING and §4 already establish the two
underlying pieces (MIT's `prov: []`, MIT's missing page PNG) — but it is
named here on its own because it is a **schema and diagram decision**, not a
classify/convert implementation detail, and the risk is that it gets
absorbed into `db/schema.sql` (P2D) or `docs/architecture.md` (P3) by
accident — one nullable column, unremarked — rather than by a decision
someone actually made.

**The gap, stated plainly:** every `value` row this pipeline will ever
produce needs a citation (CLAUDE.md: *"every extracted number traces back to
the exact rectangle on the exact page of the exact file"*). For a PDF-sourced
value, that citation is real and precise: `page_no` + `bbox`, renderable as a
highlighted rectangle over `docs/<sha8>/pages/NNN.png`. For an HTML-sourced
value (MIT), neither half exists — no page, no bbox, no PNG — and nothing
built in P2B manufactures one, nor should it: a fabricated bbox over a page
image that doesn't exist would be exactly the "plausible, wrong, unflagged"
failure shape CLAUDE.md forbids.

**Proposed shape — a two-tier citation model, not implemented here:**

| | PDF-sourced value | HTML-sourced value |
|---|---|---|
| Locates | exact rectangle on exact page | this URL, this document |
| Stored citation | `page_no` + `bbox` + `sha256` | `source_url` + `sha256` + a text anchor (e.g. the containing `<table>`/row's surrounding text, or a DOM path/id if Docling's HTML backend exposes one) |
| Visual proof | rendered PNG, rectangle highlighted (`docs/<sha8>/pages/NNN.png`) | none — no rendering tool in the settled stack (§4); the anchor text itself is the proof, next to a link to `source_url` |
| Reviewer experience | "here is the box on the page" | "here is the sentence/row, on this page, go look" |

Concretely, this implies (for whoever picks this up in P2D/P3, **not**
decided or built here):

- `value.item_id` / `doc_item` in P2D's schema (`db/schema.sql`) needs
  `bbox` to be genuinely nullable, with a `citation_kind` (or equivalent)
  distinguishing `bbox_citation` from `anchor_citation` — not a bbox column
  that's just usually empty for one whole source class.
- P3's D2 diagram (*"value -> item_id -> page_no + bbox -> rendered page PNG
  -> highlighted rectangle -> source URL"*) needs a second branch for the
  no-bbox path, drawn with equal weight, the same way D3 already gives the
  UNVERIFIED checksum state equal visual weight to CONFIRMED/CONFLICTING —
  this is the same category of "the abstain branch is the one a future
  maintainer drops."
- Whatever text-anchor mechanism P2C/P2E design for MIT (extracting a
  surrounding label/row as the anchor) still has to satisfy P-14 (anchor on
  section, verify by label, never match on label text alone) — the anchor
  here is evidentiary text for a human reviewer, not a machine-mapping key,
  so it does not by itself relax P-14 for MIT's mapping logic.

**Settled by:** a P2D/P3 decision to build this two-tier model explicitly (or
a different one) — not by this phase, which only names the gap and proposes
a shape, per the instruction not to implement anything here.

---

## STOP CONDITION

No KPI value was extracted anywhere in this diff. `grep -rniE "median.salary|kpi_code|graduate.*salary"` across `classify/` and `convert/` returns nothing beyond this sentence in this file. [VERIFIED] Conversion output (`docling.json`) is stored; no code path reads a cell value out of it for any purpose beyond the P1 regression check's row-shape assertion (which compares *strings already known to be correct from P1*, not a newly-extracted value being trusted).

**P2B CLEAR — classify and convert self-verification both PASS, P1 regression PASS. Proceed to P2C.**

Three `[OPEN]` items carried forward, none blocking: OCR is off (no scanned
document exists yet to need it), MIT gets no page PNG (no headless browser
in the settled stack), and MIT's values will need a different citation shape
than PDF's (§7 — no bbox, no rendered rectangle, source URL + text anchor
instead; a schema/diagram decision named here, not built here). All three
are architecture decisions for whoever picks up P2C/P2D/P3, not defects in
this phase's own scope.

---

REVIEWED BY: dushyant7563@gmail.com   DATE: 2026-09-14
