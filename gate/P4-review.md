**TIME-BOXED review, categories 1+4 only, run under submission deadline —
full P4 deferred to next iteration, same as P3/graphify.**

Entry gate note: PROMPTS.md's real P4 entry gate is `docs/architecture.md`
(P3), which does not exist yet — P3 was deferred (per the same note this
file opens with). This review was explicitly requested to run ahead of
that, scoped narrowly, by the operator. Not a full P4; do not treat this
file as satisfying P4's own entry-gate chain for a future P3/P4 pass.

**Scope, per instruction:** category 1 (SILENT WRONGNESS) and category 4
(AUTO-ACCEPT PATHS) only. Categories 2 (P1 rotation), 3 (checksum
three-state), 5-8 (P-10, immutability, licences, constant provenance)
explicitly skipped — already covered by signed-off gates.

**Method:** read `CLAUDE.md` and every `gate/*.md` file in full, then
adversarially re-read every module built this session (`profiles/`,
`fingerprint/`, `discovery/`, `review/`, plus this session's edits to
`acquire/pipelines.py`) against categories 1 and 4 specifically, running
small targeted checks against real data (not just reading code) where a
claim was checkable. Did not re-review `extract/`, `convert/`, `classify/`,
or `acquire/`'s pre-existing modules beyond the one edited file — those are
covered by already-signed-off P2A/P2B/P2C gates and excluded from this
time-boxed pass by the same logic as skipping categories 2-3.

---

## Findings, most severe first

### HIGH

**H1 — `discovery/candidates.py` has no defense against an incidental
(non-disclosure) `<table>` on a homepage; T3's PASS is real but narrow.**

- **File/line:** `discovery/candidates.py::generate_candidates` (the whole
  function) — every cell of every table in an `html_table`-labeled
  document becomes a scored candidate uniformly. Nothing distinguishes an
  institutional self-disclosure table from page furniture (a nav table, a
  footer link grid, a cookie-consent widget) that happens to use a
  `<table>` element.
- **What breaks:** `gate/P2E-profiles.md`'s T3 result (0 values, 0
  candidates) is a real, verified PASS for the one fixture tested
  (swarthmore.edu, confirmed zero `<table>` elements). It is **not**
  evidence the mechanism is safe against homepages that *do* have an
  incidental table — `classify/labels.py` routes any HTML page with even
  one `<table>` to `html_table` and it proceeds straight through convert +
  fingerprint + discovery. If that table contains anything that
  token-overlaps a KPI dictionary entry (plausible for a footer listing
  "Students", "Faculty", "Contact" links, or a stats-widget-style nav),
  discovery would propose it as a real candidate with a real score.
- **What the operator would see:** nothing wrong at first — candidates
  would appear in a review queue with visible scores, same as any other
  discovery run, so a reviewer would likely reject them by inspection. The
  danger is upstream of the reviewer: this is exactly the scenario
  `PROMPTS.md` P2E's own STOP CONDITION calls CRITICAL ("If T3 returns even
  one value... the rotation failure wearing a new costume") — it has just
  never been *exercised* against a document where it would actually fire,
  because the one fixture tested happens to have zero tables. This
  reviewer cannot certify T3 is safe in general from one clean fixture.
- **Fix (not applied — report only):** classify or discovery should
  distinguish structural/navigational tables from content tables before
  scoring — e.g. a minimum-cell-count / non-boilerplate-text heuristic, or
  requiring the surrounding page to carry an institutional-disclosure
  signal before any `html_table` candidate is scored. Absent that, T3
  should be re-run against a *second* homepage that is known to contain an
  incidental `<table>` (many university sites do, for layout or a stats
  widget) before this gap is closed.

---

### MEDIUM

**M1 — The NIRF profile's declared `page_rotation: 90` fingerprint
criterion is never actually checked; it is unconditionally treated as
satisfied.**

- **File/line:** `profiles/engine.py::fingerprint_matches`, lines ~95-120
  (the `[VERIFIED, this session]` comment block ending `return True`).
- **What breaks:** `docs/<sha8>/docling.json`'s `pages{}` dict carries only
  `{page_no, size}` — no rotation field — confirmed directly in this
  session and in the (v4) gate entry. Once the text anchor (the
  `Institute Name:.*\[IR-...\]` regex, since the 2026-09-14 (v4) fix)
  matches, the function returns `True` unconditionally; the declared
  `page_rotation: 90` requirement is never independently verified against
  anything. The code comment's own justification — "a matched table grid
  with correct label-to-value association is itself evidence rotation was
  handled" — is circular: `CLAUDE.md`'s central lesson (the `/Rotate 90`
  incident) is precisely that *wrong* rotation handling also produces
  plausible, well-formed-looking output. The same reasoning this project
  was built to distrust is being used here to justify not checking.
- **What the operator would see:** nothing, silently, unless a future
  document happens to share the bracket-ID text pattern (`Institute
  Name: ... [IR-X-Y-NNNNN]`) while having genuinely different table
  geometry (e.g. a future NIRF form revision, or an unrelated Ministry of
  Education document reusing the same institution-code convention) — that
  document would fingerprint-match and have the same block/geometry rules
  silently applied to a structure they were never verified against.
- **Severity note:** not CRITICAL because (a) the actual rotation
  *correction* is P2B/Docling's job, already covered by the signed-off P1
  regression test (category 2, out of this review's scope), and (b) no
  such colliding document exists among the 4 artifacts currently acquired
  — this is a dormant gap, not an active wrong output. It is MEDIUM because
  the profile's own declared safeguard is decorative, and the whole point
  of this project is not to rely on "it looked fine" as a rotation check.
- **Fix (not applied):** either drop `page_rotation` from the fingerprint
  schema (stop declaring a check that isn't performed — CLAUDE.md's own
  epistemic-discipline table would call an unchecked declared criterion an
  untagged claim), or find and check an actual structural proxy (e.g. a
  90°-rotated table's row/column count ratio, or Docling's own per-item
  geometry if a future version exposes it).

**M2 — `fingerprint/matcher.py::match_document` resolves a multi-profile
match by alphabetical order with no collision detection.**

- **File/line:** `fingerprint/matcher.py`, `match_document()`, the loop
  `for profile_id in known_profile_ids(): ... if result.matched_fingerprint:
  return ...` — first match wins, `known_profile_ids()` is a sorted glob.
- **What breaks:** if two profiles' fingerprints were ever both satisfied
  by the same document, the alphabetically-earlier `profile_id` silently
  wins, with no warning, no log line, and no record that a second profile
  also matched. Nothing currently exploits this (`nirf_submission_
  v2020_2026`'s bracket-ID regex and `us_cds_v2025`'s `"Common Data Set"`
  substring do not overlap on any of the 5 real artifacts in this repo),
  but the mechanism itself has zero defense if that ever changes.
- **What the operator would see:** a document silently extracted (or
  discovery-routed) under the wrong profile's rules, reported as a clean
  single match with no indication a collision occurred.
- **Fix (not applied):** check all profiles, not just until the first hit;
  raise (or at minimum flag CRITICAL in a self-verification step) if more
  than one fingerprint matches the same document.

**M3 — `profiles/engine.py::_apply_block` hardcodes `profile["blocks"][0]`
for every table; a future multi-block profile would silently lose blocks
1+.**

- **File/line:** `profiles/engine.py:149`,
  `block = profile["blocks"][0]  # ANY_TABLE: the one declared block applies to every table`.
- **What breaks:** this is correct today because
  `nirf_submission_v2020_2026.yaml` deliberately has exactly one
  `ANY_TABLE` block (a documented design choice, not an oversight). But
  `_mechanically_applicable()` (the gate that decides whether a profile can
  be run at all) checks only that `blocks[0]` has the right shape — it
  never checks `len(blocks) == 1`. A future profile with two real,
  differently-scoped blocks (e.g. a per-section anchor design, which
  `PROMPTS.md`'s own PROFILE SHAPE section explicitly anticipates as the
  general case) would pass `_mechanically_applicable()` and then have
  every table processed using only `blocks[0]`'s rules — `blocks[1:]`
  silently never run, for any table, with no error.
- **What the operator would see:** a profile that looks complete in its
  YAML (multiple blocks defined) but whose second-and-later blocks never
  produce a single value or checksum row, with nothing in the run output
  indicating why.
- **Fix (not applied):** either loop over `profile["blocks"]` and match
  each table to its own anchor (the design `PROMPTS.md` actually
  describes: "blocks: anchor (SECTION header) + geometry rule..."), or, if
  the single-block ANY_TABLE design is being kept intentionally,
  `_mechanically_applicable()` should explicitly assert `len(blocks) == 1`
  and treat more than one block as *not* mechanically applicable rather
  than silently applying only the first.

**M4 — `review/queue.py`'s `contestable` flag is caller-supplied, not
structurally derived from the dictionary; nothing prevents a future
CONFIRM/REASSIGN from losing it.**

- **File/line:** `review/queue.py:61`, `review(candidate, action, *,
  reviewer, kpi_code=None, note="", contestable=False)` — `contestable`
  defaults to `False` and is never cross-checked against
  `discovery.kpi_dictionary.KpiEntry.contestable` for the `kpi_code` being
  recorded.
- **What breaks:** in this session's own `scripts/run_p2e_t2_v2.py`,
  `contestable` was set correctly by hand for both `S10`-touching rows
  (verified against the dictionary's `v2_Note`). But the mechanism itself
  provides no structural guarantee — a future script (or a future person
  extending the review queue) calling
  `review(candidate, CONFIRM, reviewer=..., kpi_code="S10")` with no
  `contestable=` argument would silently produce a `ReviewRecord` that
  reports `S10` as an ordinary, undisputed confirmation, losing the
  "different analyst could invert this" signal the dictionary itself
  carries. This is adjacent to category 4's "any mapping that becomes a
  stored value without a recorded human decision" concern: the human
  decision would be recorded, but a decision-relevant fact about it (its
  own contestedness) is not structurally protected the way `kpi_code`
  presence/absence already is by `__post_init__`.
- **What the operator would see:** a KPI mapping presented as settled when
  the dictionary itself flags it as one two competent analysts could
  disagree on — invisible unless someone manually re-checks the dictionary
  for every confirmed code.
- **Fix (not applied):** have `review()` look up `contestable` from the
  dictionary itself when `kpi_code` is given, rather than trusting the
  caller to pass it; keep the explicit parameter only as an override for a
  documented reason.

---

### LOW

**L1 — `discovery/candidates.py::generate_candidates` silently drops any
value-bearing cell lacking both a `row_label` and a `column_label`, before
scoring; the resulting candidate count is reported as if it were complete.**

- **File/line:** `discovery/candidates.py:117`, `if not label: continue`.
- **What breaks:** measured directly against MIT's document (not
  estimated): of 790 real, non-header, non-empty value cells, 2 have
  neither a `row_label` nor a `column_label` (both from the same table,
  `#/tables/30`, isolated `"Yes"`/`"No"` checkbox cells at row 0) and are
  silently excluded before generation — `generate_candidates` returns 788,
  which is exactly the figure `gate/P2E-profiles.md`'s T2 sections (both
  the 24-code and real-dictionary runs) report as *"candidate count"*, with
  no footnote that 2 real cells were never candidates at all.
- **What the operator would see:** a candidate count that looks like a
  complete inventory of the document's value cells but is off by a small,
  silently-dropped margin. On this document the magnitude is trivial (2 of
  790); nothing here checks whether a differently-shaped table could lose
  a much larger fraction the same way.
- **Fix (not applied):** either candidate-ize label-less cells too (with an
  empty/placeholder label, so they still enter the review queue and get a
  `NO_KPI_HOME`-by-inspection outcome rather than vanishing before
  scoring), or report the exclusion count explicitly alongside the
  candidate count.

---

## Summary

CRITICAL: 0
HIGH: 1 (H1)
MEDIUM: 4 (M1-M4)
LOW: 1 (L1)

No active auto-accept path was found executing anywhere in this session's
code (both T2 runs recorded 0 CONFIRM/REASSIGN actions; every `MARK_PARTIAL`
carries a hand-written, falsifiable reason). Category 4's findings (M4)
are about a gap in the *safety net around* recorded human decisions, not an
observed instance of a mapping becoming a stored value without one.

**DO NOT SHIP** is not the right verdict for a time-boxed, categories-1-and-4-
only pass against a repo whose live acceptance tests (P2C, P2E v1-v4) are
already signed off — this file does not attempt that verdict. Read as: one
HIGH item (H1) should be closed with a second T3-style test against a
homepage that has an incidental table, before this project's own P-15
guarantee is trusted beyond the one fixture already tested; the four MEDIUM
items are real but currently dormant design gaps, worth fixing before this
codebase is extended with more profiles or a real reviewer UI, not before
the president demo on the documents already acquired.

Not fixed. Report only, per instruction.
