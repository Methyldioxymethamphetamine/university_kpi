# P1 — Spike gate

**Entry gate:** `gate/P0-interrogation.md` exists and ends with `P0 CLEAR — proceed to P1.` [VERIFIED]
**Scope:** exactly one document — `https://www.nirfindia.org/nirfpdfcdn/2025/pdf/Overall/IR-O-U-0306.pdf`
(IIT Bombay, Overall, 2025). No second document fetched. Created only `spike/` and this file.

All P0-mandated changes honoured: this file records exact Docling/docling-core versions (A3), and CHECK
B verifies bbox alignment as well as label-value association, not label-value association alone (A1).

---

## CHECK A — Idempotent acquisition

**PASS.**

Fetched with Scrapy (`spike/check_a_acquisition.py`, a one-shot spider — no project scaffold, per the
"no repo structure" constraint), storing content-addressed under `spike/raw/sha256/`.

```
First fetch:  status=200  bytes=12127  sha256=e9a1d469ba17262f052948f22d8a15b6f4c37a4646af72efea77e0a7e0b1e019
              file_existed_before_this_fetch=false   new_file_created=true

Second fetch: status=200  bytes=12127  sha256=e9a1d469ba17262f052948f22d8a15b6f4c37a4646af72efea77e0a7e0b1e019
              file_existed_before_this_fetch=true    new_file_created=false
```

[VERIFIED] Byte-identical, identical sha256 both times, second fetch created no new file (content-
addressed store found the existing path and skipped the write). Independently re-hashed the stored
file with `sha256sum` outside the script: matches.

---

## CHECK B — P1 / rotation. Docling recovery + independent pypdfium2 confirmation.

**PASS.**

**Versions used** [VERIFIED] (closing the A3 gap — this is the version-recording requirement P0 added):
`docling==2.127.0`, model cache at `~/.cache/docling/models` (pre-warmed via `docling-tools models
download` during project setup, not the `DocumentConverter()`-alone approach `INSTRUCTIONS.md`
describes, which downloads nothing on this version — already flagged in the setup gate).

**Docling conversion** (`spike/check_b_docling_convert.py` → `spike/docling.json`, `save_as_json()`
only, per P-2): 4 pages recovered, matching the known page count.

**Assertion, not eyeballing** (`spike/check_b_assert.py`) — searched every table's grid for the exact
row, asserted header match, and asserted the row is unique across all 17 detected tables (no ambiguous
association):

```
ASSERTION PASSED
table_index=0 row_index=1
header=['Academic Year', '2023-24', '2022-23', '2021-22', '2020-21', '2019-20', '2018-19']
row=['UG [4 Years Program(s)]', '1161', '1059', '1039', '1030', '-', '-']
provenance=[{"page_no": 1, "bbox": {"l": 7.05, "t": 498.01, "r": 834.66, "b": 428.51,
             "coord_origin": "BOTTOMLEFT"}, "charspan": [0, 0]}]
```

Exact match to the known-correct row from `notes/methodology.md` §2.5, including the trailing dashes
(not coerced to blank or zero at this extraction stage). `-` for the two oldest years, `1161/1059/
1039/1030` for the four most recent — same order, same values, correctly paired to their header. This
directly answers A1's open sub-question: Docling's render-then-detect approach did **not** reproduce
the `pdf.js`-style axis-swap merge; two side-by-side tables (this one and the neighbouring lateral-
entry/placement table) were correctly segmented, not collapsed.

**Independent confirmation with pypdfium2** (`spike/check_b_pypdfium2_rotation.py`, raw text-run dump,
not routed through Docling):

```
page_rotation_degrees=90
distinct_text_angles=[90]
sample matrices, e.g.: (a=0.0, b=1.0, c=-1.0, d=0.0, e=24.0, f=302.64)  -> angle 90
```

[VERIFIED] Page-level rotation is 90, and every sampled text object's matrix carries a 90° rotation
component — matches `notes/methodology.md`'s original `pdf.js`-based finding (`rotate 90`, `textAngles
[90]`) exactly, now independently reproduced through a different library.

**A1 verdict, resolved:** the assumption ("Docling's layout-model approach makes `/Rotate 90` a
non-issue") holds for this document [VERIFIED, n=1]. Not generalized beyond this one document/category
— that generalization risk (A5, A9) stands as recorded in P0 and is not retested here.

---

## CHECK C — Citation + checksum survival

**FAIL.** Not an extraction defect — a scope mismatch between this check and P1's own document scope,
found and reported rather than routed around.

**What was searched for:** `3750000(Three Lakh Seventy Five Thousand)`, byte-level, across the entire
499,158-byte `docling.json` — not just the table grids. Zero occurrences:

```
grep -c "3750000" spike/docling.json                  -> 0
grep -c "Three Lakh Seventy Five" spike/docling.json  -> 0
```

**Why, and why this isn't ambiguous.** Every one of the six P0-mandated documents — `CLAUDE.md`,
`iteration-1-source-investigation.md` §6, `digits-words-checksum-analysis.md` — attributes this exact
cell to **Sandip's** 2025 NIRF submission (`IR-O-C-41520`, own-site copy), not IIT Bombay's
(`IR-O-U-0306`, the NIRF-portal copy that is P1's entire scope). `CLAUDE.md` itself: *"Sandip's 2025
submission has a cell where the digits read `3750000`..."* P1 forbids fetching a second document. The
correct action per the RULES ("do not tune, retry, or work around a failure... a FAIL is a result") is
to report this as a FAIL of the check as literally scoped, not to fetch Sandip's file to satisfy it.

**Supplementary evidence — the underlying mechanism was still exercised, on a string that genuinely
belongs to this document,** so this FAIL is not left uninformative:

```
Table 2, row 2, col 8: "1963000(Nineteen Lakhs Sixty Three Thousand Only)"
cell.bbox = {l: 673.8, t: 450.97, r: 731.39, b: 471.45, coord_origin: TOPLEFT}
table.prov[0].page_no = 1
```

[VERIFIED] The parenthetical digits(words) pattern survives as one contiguous string, with a **cell-
level** bbox (not merely a table-level one — corrected from an earlier misread of the schema where I
initially checked for `cell['prov']`, which doesn't exist; the bbox lives directly on the cell object)
and a page number from the table's provenance. IIT Bombay's real median-salary figures — `1880000`,
`1963000`, `1961000`, `1655556`, `1500000`, `1730000` — all extracted cleanly, all digits/words
internally consistent, and `1963000`/`1961000` match the "~₹19.6 lakh" figure `iteration-1-source-
investigation.md` §6 cites as IIT Bombay's real median salary. So: the citation/survival *mechanism*
this check exists to validate does work, on this document, on this run. What could not be tested is the
**specific conflict case** — because that case lives in a document outside P1's scope by construction.

**This is worth surfacing as a process point, not just a data point:** P1 is defined as a one-document
spike, but the one finding that motivates the entire project (the digits/words conflict) is only
observable in the *other* institution's document. A single-document P1 can verify the rotation/
label-association mechanism (CHECK B, the harder and more important of the two) and the citation
survival mechanism in general (demonstrated above), but cannot, by its own scope rules, verify the
specific conflict-detection scenario end to end. That verification has to happen at P2A/P2C once
Sandip's document is in scope — it is not something this phase's design can close.

---

## Fallback assessment (per the RULES, in case B or C required one)

Not needed for **B** — B passed. Not applicable to **C** in the fallback sense (C's failure is scope,
not a broken parser) — there is nothing to port or replace; the fix is procedural (test the conflict
scenario once Sandip's document is in scope, at P2A/P2C), not architectural.

---

## Tags summary

[VERIFIED]: sha256 idempotency (both fetches, independently re-hashed); Docling version and page count;
the CHECK B assertion result; pypdfium2 rotation and text-angle values; the absence of the target
string (byte-level grep across the full JSON); the substitute cell's contiguity, bbox, and page number;
IIT Bombay's real salary figures matching the source investigation's cited ~₹19.6 lakh.
[ASSUMED]: none load-bearing in this file — A1's remaining generalization question (does this hold
beyond this one document/category?) is explicitly left open, not assumed, per P0.

---

**P1 FAILED — check(s) C. Architecture decision required. Do not proceed.**

---

REVIEWED BY: dushyant7563@gmail.com   DATE: 2026-09-14
CHECKLIST: CHECK A pass, CHECK B pass (the load-bearing one). CHECK C's
  failure traced to a defect in the phase prompt itself — it searched for a
  string that only exists in Sandip's document while scoped to IIT Bombay's.
  Not a pipeline defect. Corrected in PROMPTS.md.
NOTES: P0's A1 is now resolved — Docling handles /Rotate 90 correctly on this
  document, verified by assertion and cross-checked via pypdfium2. No
  pypdfium2 fallback parser needed for convert/.
STATUS: SIGNED OFF — CHECK C superseded, see corrected P1 below.

---

## CHECK C (re-run) — Citation + checksum survival, corrected scope

Before this re-run, `prompts/PROMPTS.md`'s CHECK C block was itself still the
uncorrected version — it still named `3750000(Three Lakh Seventy Five
Thousand)` and "the same docling.json" despite the note above claiming it had
already been fixed. That was caught and corrected in `prompts/PROMPTS.md`
first (CHECK C is now a mechanism test: locate any digits(words) monetary
field in this document, not a specific value that only exists in Sandip's).
Only then was CHECK C re-run. CHECK A and CHECK B are unchanged from above and
are cited, not re-run.

**PASS.**

`spike/check_c_citation_survival.py`, run against the same `spike/docling.json`
produced during the original CHECK B (no re-fetch, no re-convert):

```
digits(words)-shaped cells found: 33
CHOSEN CELL FOR CHECK C:
{
  "table_index": 2,
  "text": "1880000(Eighteen Lakhs Eighty Thousand)",
  "cell_bbox": {
    "l": 673.8, "t": 419.974, "r": 731.004, "b": 440.449,
    "coord_origin": "TOPLEFT"
  },
  "page_no": 1,
  "start_row": 1,
  "start_col": 8
}
exact-string occurrences in raw docling.json (json-encoded): 2
CHECK C ASSERTION PASSED
```

[VERIFIED] `1880000(Eighteen Lakhs Eighty Thousand)` — a real salary field on
IIT Bombay's own document — survives as one contiguous string (found verbatim
in the raw JSON, not reflowed or split across items), with a **cell-level**
bbox and a page number (from the table's provenance, `page_no=1`) attached. 33
distinct digits(words) cells exist in this document in total; this run reports
the first one found, per the corrected check's "use whichever one you
actually find" instruction. This is the same underlying cell-provenance
mechanism already exercised on `1963000(...)` during the original FAIL's
supplementary check — now formally the PASS result for CHECK C itself,
against a target the corrected check actually permits.

**What this does and does not close:** this confirms the survival/citation
mechanism holds on IIT Bombay's document. It does not, and per P1's own
single-document scope cannot, exercise the specific Sandip digits/words
conflict — that remains P2C's job, against Sandip's document, as recorded
above.

[VERIFIED]: digits(words) cell count (33); the chosen cell's text, bbox,
page_no; verbatim occurrence in the raw JSON.
[ASSUMED]: none load-bearing.

---

**P1 CLEAR — A/B/C all PASS. Proceed to P2A.**
