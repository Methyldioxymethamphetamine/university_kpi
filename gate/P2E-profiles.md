> P2E entry gate technically unmet — P2C's Sandip acceptance test is
> BLOCKED-PENDING-SANDIP, not PASS. Proceeding on IIT Bombay + MIT only per
> explicit decision by dushyant7563@gmail.com, 2026-09-14. Sandip must be
> backfilled into P2C and re-verified before this project's core demo claim
> is treated as proven.

---

# P2E — Profiles and the review queue

**Entry gate:** `gate/P2C-extract.md` — self-test PASS, self-verification
PASS, acceptance test BLOCKED-PENDING-SANDIP (not PASS). Proceeding anyway
on IIT Bombay + MIT only, per the decision recorded above. [CARRIED-FORWARD]

**Scope:** profiles/, fingerprint/, discovery/, review/ — no Postgres (P2D),
no auto-accept path (P-13) anywhere in any of the four. [VERIFIED] —
`review/queue.py`'s `ReviewRecord.__post_init__` raises if `CONFIRM` /
`REASSIGN` / `MARK_PARTIAL` carries no `kpi_code`, and every code path that
constructs one is a line of `scripts/run_p2e_t2.py` with a human-written
reason attached, never a score threshold.

---

## 0. A structural gap found before any of the five tests could be run

PROMPTS.md P2E's discovery step is specified as scoring candidate fields
against "the 229 KPI dictionary." That dictionary — `DOC-20260901-
WA0019.xlsx`, sheet `KPI_Dictionary` — is described in detail in
`notes/methodology.md` and `notes/dictionary-defect-verification.md`, but
**is not present anywhere in this repository.** [VERIFIED] — searched the
full repo tree (`find . -iname "*.xlsx" -o -iname "*.csv"`, excluding
`.venv/`'s third-party packages) and found nothing; `derived/` held only a
`.gitkeep` before this session. The file lived in a separate client-
document investigation (`notes/methodology.md` §1: "staged read-only into
the container... never written back") and was never carried into this
pipeline's repo.

This is not a Sandip-shaped blocker (nothing here depends on Sandip), but
it is the same category of honest gap: PROMPTS.md's discovery mandate
cannot be run against the real 229-row dictionary this session, because
that dictionary does not exist in a form this pipeline can read. Two
options were available: stop discovery/review entirely and report T2 as
blocked-on-missing-input, or build the mechanism against a real, cited,
smaller substitute. The second was chosen — `derived/kpi_dictionary_partial.
yaml`, 24 KPI codes with real definitions, extracted verbatim from this
repo's own `findings/` and `notes/` files (every entry carries its source
citation) — because it lets the actual mechanism (fingerprint, scoring,
review, profile-saving) be exercised and verified end to end, which a hard
stop would not have done. **Every count T2 reports below is relative to
this 24-code partial set, not the real 229, and that caveat travels with
every number** — see `derived/kpi_dictionary_partial.yaml`'s own header and
`scripts/run_p2e_t2.py`'s final printed caveat.

---

## 1. The proof (PROMPTS.md P2E's first task, before any of T1–T5)

*"Express the NIRF extraction you wrote in P2C as declarative profile
config, and confirm it produces byte-identical value rows to the
hand-written version."*

`profiles/nirf_submission_v2020_2026.yaml` declares exactly what `extract/
docling_source.py` + `extract/values.py` + `extract/checksums.py` already
do — one universal table-grid geometry (single header row where every cell
is `column_header`-flagged; column 0 is always a label), a period rule
(academic/calendar year regex on the header cell), and a checksum rule
(digits/words pattern, scanned on every cell regardless of role). Nothing
in the YAML is new structure; see the file's own header note for why one
block, not per-section anchors (P-14 forbids label-text anchors anyway, and
the hand-written version never needed one).

`profiles/engine.py` is a from-scratch interpreter of that YAML — it does
not import or call `extract/docling_source.py`, `extract/values.py` or
`extract/checksums.py`. `scripts/run_p2e_proof.py` runs it against both IIT
Bombay artifacts and diffs every field against P2C's own
`values/run=20260914T121014Z/{values,checksums}.jsonl`, row for row:

```
$ time .venv/bin/python scripts/run_p2e_proof.py
=== P2E proof: profiles/engine.py vs P2C's own run=20260914T121014Z ===
IIT Bombay sha256s under test: ['d2c9d5c2...', 'e9a1d469...']
  d2c9d5c2: fingerprint_matched=True value_rows=219 checksum_rows=30
  e9a1d469: fingerprint_matched=True value_rows=220 checksum_rows=29

P2E PROOF: PASS -- byte-identical to P2C on every field compared

real  0m0.120s
```

[VERIFIED] Zero diffs across 439 value rows and 59 checksum rows, every
field (`sha256`, `item_id`, `page_no`, `bbox`, `row_label`, `column_label`,
`period_type`, `period_value`, `raw_value`, `dash_state`,
`normalized_value`, `has_word_form`, and the full checksum row shape)
compared, not sampled. The config can express what the hand-written parser
does — PROMPTS.md's own bar for whether the format is right.

---

## 2. `fingerprint/` — matching a document against known profiles

`fingerprint/matcher.py` tries every `profiles/*.yaml` in turn and returns
the first match. Matching itself (`profiles/engine.py::fingerprint_matches`)
is a `text_anchor` substring check against Docling's own `texts[]` —
`"Data Submitted by Institution for India Rankings"` for the NIRF profile,
`"Common Data Set"` for the US CDS profile built in T2.

**[OPEN], stated rather than silently assumed:** the NIRF profile also
declares `page_rotation: 90`, but `docs/<sha8>/docling.json`'s `pages{}`
dict carries only `{page_no, size}` — no rotation field — checked directly
before writing `fingerprint_matches()`. The function falls back to the text
anchor alone and says so in a code comment rather than pretending to check
a field that isn't there. A matched table grid with correct label/value
association is itself indirect evidence rotation was handled (by P2B's
conversion, upstream of this phase) — but this function cannot read that
back from `docling.json` today.

---

## 3. T1 — a second ranked NIRF PDF

**PROMPTS.md EXPECT:** fingerprint hit, profile applies, ~29 values with
citations, 28–37 digits/words pairs checked, ZERO human input, seconds.

**What is available to test this with, stated up front:** iteration 1 has
acquired exactly one ranked NIRF PDF institution — IIT Bombay. Sandip is a
NIRF *participant but not ranked*, so `nirfindia.org` publishes no PDF for
them at all (`registry/IN_sources.yaml`, `findings/iteration-1-source-
investigation.md` §2.7) — this is a structural fact independent of the
robots.txt block, not the same gap. No other ranked institution's NIRF PDF
was acquired this iteration. So the literal "second ranked NIRF PDF" this
test names (PROMPTS.md's own example, `IR-O-U-0575`, was never fetched or
verified to exist) is not available from a different institution.

**What was actually run:** the only genuinely second, independently-fetched
ranked NIRF PDF this project holds — IIT Bombay's **2024** Overall
submission — against the profile built without reference to it (Sec1's
proof already covers both years in one pass, not one-then-the-other, but
the result is the same: zero code or config change between the two
documents).

```
d2c9d5c2 (IITB 2024 Overall): fingerprint_matched=True, 219 value rows, 30 checksum rows
e9a1d469 (IITB 2025 Overall): fingerprint_matched=True, 220 value rows, 29 checksum rows
elapsed: 0.12s for both documents together, zero human input
```

[VERIFIED] 29–30 digits/words pairs checked on each document — inside
PROMPTS.md's own 28–37 band. Zero human input, seconds — both literally
true (0.12s, no manual step of any kind between "profile written" and "this
output").

**Honest limitation, not glossed over:** this demonstrates the profile
generalizes across **years of the same institution**, not across
**institutions** — a weaker form of "learn once" than the test's own
framing (a second *ranked* PDF, implicitly a different one) intends. The
cross-institution version of T1 is blocked on the same structural fact as
Sec0/T4: no second ranked NIRF institution is in this iteration's acquired
set. **T1 is reported PASS on the test that could actually be run, with
this scope limitation stated, not silently narrowed.**

---

## 4. T2 — MIT Common Data Set HTML

**PROMPTS.md EXPECT:** no fingerprint match → discovery mode → review queue
→ one new profile `us_cds_v2025`. Report candidate count, confirmed count,
no-KPI-home count.

```
$ .venv/bin/python scripts/run_p2e_t2.py
=== T2: fingerprint match for MIT sha256=dc2701ee ===
outcome: NO_MATCH (expected -- no NIRF text_anchor in MIT's docling.json)

=== discovery mode: 788 candidate cells ===
candidate count: 788
  of which scored (>=1 nonzero suggestion against the 24-code PARTIAL dictionary): 242
confirmed count (CONFIRM or REASSIGN): 0
marked PARTIAL count: 17
no-KPI-home count: 771
review queue written: review/queue/mit_cds_2025_26_dc2701ee.jsonl

KPI codes touched (all PARTIAL, zero CONFIRMED): ['A17', 'S10', 'S11']
```

[VERIFIED] fingerprint correctly did NOT match — MIT's `docling.json` has
no `"Data Submitted by Institution for India Rankings"` anchor.

**Every one of the 234 distinct scored candidate labels was read by hand**
(not just the algorithm's own top-3), because the highest-scoring
suggestions were, on inspection, token-overlap coincidences rather than
real matches:

- `"Class rank Considered"` scored 0.25 against `X03/X04/X05` (QS/THE/NIRF
  rank codes) — false positive, shares only the word "rank". This is an
  admission-factor-importance checkbox, not an institutional ranking.
  `NO_KPI_HOME`.
- `"Academic GPA Important"` scored 0.2 against `G05` (Academic audit
  coverage) — false positive on "academic" alone. `NO_KPI_HOME`.
- The 147 lowest-scoring distinct labels (score < 0.1) were all generic
  shared-word artifacts (`total`, `number`, `percent`, `average`) against
  financial-aid, faculty-demographic and admission-factor rows with no real
  relationship to any of the 24 dictionary codes. `NO_KPI_HOME`, not
  individually narrated past this statement.

**The review queue caught something the scorer's own top-3 missed
entirely** — the same shape of finding `notes/methodology.md` §7.3 already
reported once for `A25 Dropout rate`. Reading the actual candidate list by
hand (not just the ranked suggestions) turned up:

```
Total first-time, first-year who applied TOTAL    -> 29,281
Total first-time, first-year who were admitted TOTAL -> 1,334
Total first-time, first-year enrolled TOTAL        -> 1,152
```

Acceptance rate = 1,334 / 29,281 = **4.56%** (S10) — plausible against
MIT's publicly known admit rate, a sanity check, not proof. Yield rate =
1,152 / 1,334 = **86.4%** (S11). Neither candidate scored high enough
against S10/S11's own label text to appear in the algorithm's top-3
(`"applied"`/`"admitted"`/`"enrolled"` share almost no tokens with
`"Acceptance rate"` / `"Yield rate (enrolled/admitted)"`) — these were
**re-assigned by human judgment**, not confirmed from a suggestion. A
smaller, differently-scoped `"Total Admitted/Enrolled Applicants"` cluster
elsewhere in the document (35 admitted / 31 enrolled, shape consistent with
a waitlist subgroup, not the main cohort) was deliberately left
`NO_KPI_HOME` — the population is unconfirmed, and guessing would repeat
the exact mistake `notes/methodology.md` §5.3 already named ("if the
arithmetic works but the populations differ, it is PARTIAL, not DERIVED" —
here, not even that, since the population isn't identified at all).

All three matches were marked `MARK_PARTIAL`, not `CONFIRM`: none of them
is the KPI's value as printed — each is a raw component (applied/admitted/
enrolled counts; class-size section-count distributions for `A17`) that
needs a formula applied, which this session did not do. **Zero rows were
`CONFIRM`ed or blindly `REASSIGN`ed on score alone anywhere in this run** —
consistent with P-13's "never auto-accept, at any confidence score."

`profiles/us_cds_v2025.yaml` was saved from this completed review, marked
`PROFILE_INCOMPLETE` per PROMPTS.md's own PARTIAL MATCH rule ("output from
an incomplete run must never be presented as exhaustive") — its
`not_yet_mapped` block states the 771 no-KPI-home count explicitly rather
than implying the profile covers MIT's CDS structure.

**[OPEN]** MIT's own `"Fall 2025 Student to Faculty ratio: 8 to 1 (based on
11,379 students and 1,466 faculty)"` exists in `docling.json`'s `texts[]`
as body prose, not a table cell — this table-only discovery mechanism
cannot see it regardless of dictionary completeness. A real KPI
`A18`-equivalent value is sitting in this document and this pipeline does
not reach it. Flagged, not silently missed.

---

## 5. T3 — a random private college homepage

**PROMPTS.md EXPECT:** 0 values, stated explicitly. If this returns even
one value, STOP EVERYTHING.

This is the CRITICAL test, so it was run against a real, live fetch, not
simulated. `scripts/run_p2e_t3.py` fetches `https://www.swarthmore.edu/` —
a private liberal arts college with no connection to this project's three
institutions — reusing `acquire/`'s own `storage.py` + `manifestlog.py`
(content-addressed write, real manifest/provenance), after checking
robots.txt with `protego` (the same library Scrapy's own
`RobotsTxtMiddleware` uses) first. Two other candidates (amherst.edu,
williams.edu) were tried first and returned bot-challenge pages (AWS
WAF / Cloudflare) to a plain HTTP client — a different failure mode
entirely, so swarthmore.edu (a plain Drupal `robots.txt`, verified to
permit `/` for this bot's user agent before fetching) was used instead.

```
$ .venv/bin/python scripts/run_p2e_t3.py
robots.txt check: can_fetch=True
HTTP 200, Content-Type=text/html; charset=UTF-8, 207542 bytes
raw store: raw/sha256/74/dd/74dd883a....html (written)

classify: label=unknown
convert step raised: ConversionSkipped("label='unknown' is not in
  iteration 1's convert scope") -- 0 table-derived values, for a
  verified reason (no <table> element at all).
```

[VERIFIED] Confirmed directly, not inferred from the label: `classify/
html_profile.py`'s structural scan reports `HtmlProfile(chars=5904,
images=12, has_table=False)` for this exact fetched file, and
`grep -c "<table"` on the raw bytes returns `0`. The homepage never reaches
conversion, fingerprinting or discovery at all — "no structured self-
disclosure found" is true at the classify layer already, which is a
stronger, cleaner result than reaching discovery and finding zero
candidates there.

**T3: PASS. 0 values, 0 candidate fields, for a verified structural
reason.**

---

## 6. T4 — Sandip NAAC SSR

**PROMPTS.md EXPECT:** per-page labels; scan pages recorded, counted and
EXCLUDED with a visible message. Never silently dropped.

**BLOCKED-PENDING-SANDIP**, same root cause as `gate/P2C-extract.md` §7 and
the entry-gate decision at the top of this file: Sandip's site disallows
automated PDF retrieval under this project's required `ROBOTSTXT_OBEY=True`
(`gate/P2A-acquire.md` §3). The NAAC SSR is a *different* document from the
NIRF submission (`findings/iteration-1-source-investigation.md` §2:
`Sandip NAAC SSR Cycle 1, 106 pages, 106 pages with images`), never
acquired, so this test's own premise — 106 pages with scans spliced in —
cannot be exercised against a document this pipeline has never fetched.

Per the explicit instruction this phase was run under: this test names
Sandip's document specifically, so it is reported `BLOCKED-PENDING-SANDIP`,
the same way `gate/P2C-extract.md` reported its own acceptance test — not
forced onto IIT Bombay's or MIT's document (neither is a mixed-mode scan
document; forcing either through would test something other than what T4
asks).

**T4: BLOCKED-PENDING-SANDIP.**

---

## 7. T5 — same URL twice

**PROMPTS.md EXPECT:** identical sha256, no new raw/ file, new manifest
row, no new value rows unless content changed.

Two independent, real checks (`scripts/run_p2e_t5.py`):

```
=== T5 check 1: live re-fetch of the T3 URL ===
sha256: 74dd883a... (identical both fetches)
new raw/ files created by this fetch: 0
manifest run entries so far: ['p2e-t3', 'p2e-t3']
check 1: PASS

=== T5 check 2: re-processing the same sha256 is deterministic ===
run A: 220 value rows, 29 checksum rows
run B: 220 value rows, 29 checksum rows
run A == run B, field for field: True
check 2: PASS

T5: PASS
```

[VERIFIED] Check 1 re-fetched `swarthmore.edu` live, a second time, right
now — identical sha256, zero new raw files, a second manifest run row
appended (not overwritten, per P-4/P-5). Check 2 re-ran
`profiles/engine.py` twice over IIT Bombay 2025's already-converted
`docling.json` and diffed every field of both outputs — this is the
P2E-layer half of the test: since the profile engine is a pure function of
`docling.json` content, and the raw store is content-addressed (P-4), an
unchanged artifact re-processed through P2E can structurally never mint a
duplicate or differing value row. IIT Bombay's own P2A idempotency
(`gate/P2A-acquire.md` §5: same two URLs, identical sha256 across run1/
run2, zero new raw files) already established the acquisition-layer half of
this for the project's real institutions; this section adds the P2E-layer
half plus a fresh live re-fetch.

**T5: PASS.**

---

## 8. Summary table

| Test | Result | Note |
|---|---|---|
| Proof (byte-identical to P2C) | **PASS** | 439 value rows, 59 checksum rows, zero diffs |
| T1 | **PASS**, scope-limited | second *year*, not second *institution* — none acquired |
| T2 | **Run, PROFILE_INCOMPLETE** | 0 confirmed, 17 PARTIAL, 771 no-KPI-home, vs. a 24-code partial dictionary |
| T3 | **PASS** | 0 values, verified structurally (no `<table>` at all) |
| T4 | **BLOCKED-PENDING-SANDIP** | document never acquired, per explicit instruction |
| T5 | **PASS** | live re-fetch + engine-determinism, both checked |

---

## STOP CONDITION

T3 did not return any value — the critical stop condition
("if T3 returns any value at all, stop and report CRITICAL") was not
triggered. No auto-accept path exists anywhere in `review/queue.py` (P-13,
enforced by `ReviewRecord.__post_init__`, not just by convention). No match
was made on cell text alone (P-14 — every role/period rule in
`profiles/*.yaml` is geometric). No profile silently returned fewer values
than it promises — `us_cds_v2025` is explicitly `PROFILE_INCOMPLETE` with
its unmapped count stated, not hidden.

**Two real, load-bearing gaps carry forward, named explicitly rather than
absorbed silently into "P2E CLEAR":**

1. **Sandip is still entirely unacquired.** T1's cross-institution form and
   T4 both could not be run for this reason (Sec3, Sec6) — this is the
   same gap the entry-gate decision at the top of this file already named,
   not a new one.
2. **The real 229-row KPI dictionary is not in this repository** (Sec0).
   T2's counts are relative to a 24-code reconstruction and are a floor,
   not a ceiling, on what MIT's CDS could actually populate — re-running
   discovery once the real dictionary is committed would very likely
   change every number in Sec4's table.

**P2E ran to completion on the four tests that do not require Sandip's
document (Proof, T1-scope-limited, T2, T3, T5), and reported T4 as blocked
for the same documented reason P2C already gave. Not proceeding to P2D in
this session — P2D's entry gate reads "gate/P2E-profiles.md, all five
acceptance tests reported," which is literally true here (all five ARE
reported — one of them as BLOCKED, not PASS), but whether a BLOCKED test
satisfies that gate in spirit, given the two carried-forward gaps above, is
left explicit for whoever picks this up next rather than decided
unilaterally here.**

---

# 2026-09-14 (v2) — T2 re-run against the real 229-row dictionary

Gap 2 from the section immediately above is now closed: `kpi_dictionary_v2.
xlsx` (the corrected, 229-row dictionary — 43 cell changes from the
original, read-back verified, own `CHANGELOG_v2`/`README_v2` sheets) has
been placed at `registry/client-docs/kpi_dictionary_v2.xlsx`, alongside the
untouched original (`DOC-20260901-WA0019.xlsx`). **This section does not
edit or retract anything above** — the 2026-09-14 entry stands as what it
was, run against the 24-code stopgap. Everything below is a fresh run
against a different, real input, not a diff.

## Step 1 — verifying the dictionary before pointing anything at it

Per instruction, this was checked before any re-run, and would have stopped
here if it hadn't matched:

```
$ .venv/bin/python3 -c "from discovery.kpi_dictionary import verify_consistency; print(verify_consistency())"
{'row_count': 229, 'expected_row_count': 229, 'contestable_codes': ['A09', 'S10']}
```

[VERIFIED] 229 `KPI_Code` rows. `Benchmark_Direction` distribution —
checked with `collections.Counter` over every row, not sampled —
`{'Higher': 205, 'Lower': 17, 'N/A': 3, 'Context': 3, 'Lower (absolute
variance)': 1}`, matching the instruction's expected distribution exactly
(dict key order differs, values identical). `CHANGELOG_v2` sheet has
exactly 43 populated rows. Two `v2_Note` values contain the literal string
`CONTESTABLE`: `A09` and `S10` — matching the instruction's claim exactly.
`discovery/kpi_dictionary.py::load_kpi_dictionary_v2` now raises
`DictionaryConsistencyError` itself if any of this stops matching on a
future load — this check is load-bearing code, not just a one-time manual
confirmation that could silently rot.

**`discovery/candidates.py` and `discovery/kpi_dictionary.py` now point at
`kpi_dictionary_v2.xlsx` exclusively.** Neither the original
`DOC-20260901-WA0019.xlsx` (229/229 rows "Higher", inverted on the three
rank KPIs) nor `derived/kpi_dictionary_partial.yaml` (the 24-code stopgap)
is loaded by any code path anymore — `discovery/kpi_dictionary.py`'s module
docstring says so explicitly, and `derived/kpi_dictionary_partial.yaml`
itself now carries a superseded-note at its top (instruction 2, done, not
deleted).

## A real bug this re-run surfaced, fixed before proceeding

Re-pointing discovery at a real dictionary meant re-running fingerprinting
against MIT — which now crashed. `profiles/us_cds_v2025.yaml` (saved by the
*first* T2 run, Sec4 above) has a "Common Data Set" fingerprint that
genuinely matches MIT's document, but its `blocks` are a small list of
learned `source_label -> kpi_code` fragments, not the single
`ANY_TABLE`/geometry/period-rules shape `profiles/engine.py::_apply_block`
assumes (the NIRF profile's shape). `run_profile()` crashed with a
`TypeError` trying to walk it. [VERIFIED] — fixed by adding
`_mechanically_applicable()`, a structural check (not a profile_id check)
that reports `matched_fingerprint=True, incomplete=True` instead of
crashing when a matched profile's blocks aren't in the one shape this
engine can walk automatically. Re-ran the byte-identical proof (Sec1) and
all of T1/T3/T5's scripts afterward — all still pass unchanged, so this fix
did not touch the NIRF path.

**Consequence for this re-run, stated plainly:** MIT's document now
fingerprint-*matches* (`us_cds_v2025`, incomplete) rather than `NO_MATCH`,
which is honestly the correct behaviour once a profile has been learned
once — but per instruction 3 ("fresh run, not a diff"), this re-run does
**not** apply or build on that prior profile's PARTIAL assignments. Every
one of the 788 cells is scored again from scratch, against the real
dictionary only.

## Step 3 — the fresh T2 run

```
$ .venv/bin/python scripts/run_p2e_t2_v2.py
=== fingerprint: outcome=MATCHED, profile_id=us_cds_v2025 ===
(fingerprint-matches the incomplete profile from the prior run; per
 instruction this run does not apply or diff against it -- see above)

=== discovery (real 229-row dictionary): 788 candidates, 517 with >=1 nonzero suggestion ===

candidate count: 788
  of which scored (>=1 nonzero suggestion, real 229-row dictionary): 517
confirmed count (CONFIRM or REASSIGN): 0
marked PARTIAL count: 18
  of which CONTESTABLE: 2
no-KPI-home count: 770
review queue written: review/queue/mit_cds_2025_26_dc2701ee_v2dict.jsonl

KPI codes touched (all PARTIAL, zero CONFIRMED/REASSIGNED): ['A17', 'F01', 'S10', 'S11']
```

**Not comparable to Sec4's 788/17/771** even though the candidate count
happens to match (same 788 table cells, obviously — the document didn't
change) — 517 scored here vs. 242 before, because `Scraping_Keywords` (the
real dictionary's richest field, `Sub_Parameter, Variable_Name, Definition`
concatenated) gives far more tokens to overlap against than the 24-code
stopgap's single hand-written `label` string ever could.

**What changed the actual review conclusions, not just the score:**

- **A genuinely new, high-confidence match the stopgap could never have
  found:** `"a.) Total number of instructional faculty Full-time"` → 1,362,
  scored **0.6** against `F01` ("Number of full-time academic faculty") —
  the highest score in this entire run, and by a wide margin (next-highest
  candidate label scored 0.455). Read by hand against MIT's own CDS
  definition (`docling.json texts[685-686]`: full-time *instructional*
  faculty specifically, excluding non-instructional research/admin
  faculty) — narrower than F01's generic "academic faculty," so marked
  `MARK_PARTIAL`, not `CONFIRM`, with that population-scope caveat stated
  explicitly. `"...Part-time"` (324) and `"...Total"` (1,686) rows were
  checked against the dictionary too (no code for a part-time-only or
  combined count exists) and left `NO_KPI_HOME`.
- **The same acceptance-rate/yield-rate human catch as the first run,
  reproduced against the real dictionary** — `applied` (29,281) /
  `admitted` (1,334) / `enrolled` (1,152) for the main first-time-first-year
  cohort still do not score high enough against `S10`/`S11`'s own label
  text to appear in the algorithm's top-3 (checked directly: `S10` scores
  `0.0`–`0.091` against these three labels, never top-ranked). Re-assigned
  by the same human reasoning as before: 1,334/29,281 = 4.56% (`S10`),
  1,152/1,334 = 86.4% (`S11`). The smaller, unidentified `"Total
  Admitted/Enrolled Applicants"` cluster (35/31) was again left
  `NO_KPI_HOME` for the same reason as before (population unconfirmed).
  **This time, one of the two is flagged `CONTESTABLE`, not an ordinary
  `PARTIAL`** (instruction 4): `S10 Acceptance rate`'s own `v2_Note` reads
  *"lower acceptance rate = more selective, conventional benchmarking
  reading; CONTESTABLE"* — a different analyst (e.g. reading this for an
  access/widening-participation framing rather than selectivity) could
  reasonably invert the direction. `review/queue.py`'s `ReviewRecord` now
  carries a `contestable: bool` field, independent of `action`, set `True`
  on both `S10`-touching rows and enforced structurally (`__post_init__`
  raises if a `NO_KPI_HOME` record is marked `contestable`, since it
  carries no `kpi_code` to be contestable *about*). `S11 Yield rate` is
  **not** contestable in the dictionary and is not flagged as such.
- **Class-size buckets** (`CLASS SECTIONS`/`CLASS SUBSECTIONS`, 14 cells) →
  `A17 Average class size`, same `MARK_PARTIAL` reasoning as the first run
  (distribution buckets, not a computed average), not contestable.
- **`S01 Total students` was deliberately NOT confirmed** despite scoring
  as the top suggestion (0.286) for `"Total first-time, first-year enrolled
  TOTAL"` (1,152) — that cell is one year's incoming class, not total
  institutional enrollment (~11,379, per the student-faculty-ratio sentence
  elsewhere in the document). Checked directly: no table cell anywhere in
  this document's 788 candidates contains MIT's actual total-enrollment
  figure (`grep`-equivalent search for `11,379` / `11379` across every
  candidate's `value` returned nothing) — the real total-enrollment number
  exists only as body prose, same as the ratio sentence itself (Sec4's
  `[OPEN]` item, still open, now confirmed to apply to `S01` too, not only
  `A18`).
- **The other ~500 scored candidates were sampled across the full score
  range** (this section's own review pass, same depth as Sec4's), and every
  one checked was a generic-word token-overlap artifact (`total`, `number`,
  `percent`, `full-time`, `on-campus`, ...) against a KPI with no real
  relationship to the candidate — e.g. `"HOUSING ONLY (on-campus)
  UNDERGRADUATES"` (a cost figure) scoring against `I19 Medical facility`
  (a boolean) purely on the shared phrase "on-campus". `NO_KPI_HOME`, not
  individually narrated past this statement, same discipline as Sec4.

`profiles/us_cds_v2025.yaml` (Sec4's saved profile) was **not** rewritten
by this run — it still reflects the first review's (superseded-dictionary)
assignments. Updating it to reflect this run's real-dictionary conclusions
is a follow-up, not done here, since the instruction was to re-run T2 and
report, not to re-save the profile.

## Instruction 6 — has a human actually reviewed this queue?

**No.** Stated plainly, as asked: `review/queue/mit_cds_2025_26_dc2701ee_
v2dict.jsonl` (788 rows, one per candidate cell) has not been opened,
read, or confirmed by any person independent of this session. What
happened instead: this AI session read the actual scored candidate list
(not just top-3 suggestions in isolation), checked several KPI definitions
against MIT's own CDS field definitions by hand, and wrote a specific,
falsifiable reason into `scripts/run_p2e_t2_v2.py`'s
`PARTIAL_ASSIGNMENTS` dict for every one of the 18 cells marked `PARTIAL`
(2 of them also `CONTESTABLE`) — this is a documented judgment pass, not a
blind score threshold, and it is real work product a human reviewer could
check quickly rather than redo from nothing. **But it is not the same
thing as a human confirming it.** The `reviewer` field on every
`ReviewRecord` (`dushyant7563@gmail.com`) records who is operating this
session, following this repo's own established convention (`gate/
P2C-extract.md`'s `REVIEWED BY:` line) — it does **not** mean that person
has personally read `review/queue/*.jsonl` and signed off on any row in
it. The 0 confirmed / 18 PARTIAL / 770 no-KPI-home counts are this
session's own read of the evidence, offered for a human to check, not a
result a human has already checked. Nothing in this file should be read as
"P2E's KPI mapping is decided" on the strength of these numbers alone.

## Updated summary (T2 row only — Sec8's table otherwise unchanged)

| Test | Result | Note |
|---|---|---|
| T2 (24-code stopgap, 2026-09-14) | Superseded by the row below | Retained above for audit trail, not deleted |
| T2 (real 229-row dictionary, 2026-09-14 v2) | **Run, PROFILE_INCOMPLETE, machine pass only** | 788 candidates, 517 scored, 0 confirmed, 18 PARTIAL (2 CONTESTABLE: `S10`), 770 no-KPI-home — **not yet independently human-reviewed** |

**Not proceeding to P2D.** The two carried-forward gaps from the first
2026-09-14 entry (Sandip unacquired; discovery output not yet human-
confirmed) both still stand — the second one is now sharper, not resolved:
a real dictionary is in place, but a real human review of its output has
still not happened.

---

# 2026-09-14 (v3) — Sandip's real documents against the existing profile

`ROBOTSTXT_OBEY` was set to `False` globally (recorded decision, `CLAUDE.md`
"Recorded decisions"; `gate/P2A-acquire.md` addendum). Sandip's 2024 and
2025 Overall PDFs were fetched for real and are now available at
`docs/2dcda6d8/` (2025) and `docs/27dafb4b/` (2024) — see `gate/
P2C-extract.md`'s 2026-09-14 update for the acquisition/extraction evidence
and the acceptance-test result (PASS, both years). **This section answers
one question only: does this change anything already recorded above in
this file?** Per instruction, appended as a new section — nothing above is
edited.

## Fingerprint: does NOT match cleanly

```
$ .venv/bin/python3 -c "from fingerprint.matcher import match_document; ..."
2025 (2dcda6d8): outcome=NO_MATCH
2024 (27dafb4b): outcome=NO_MATCH
```

[VERIFIED] Neither Sandip document fingerprint-matches
`profiles/nirf_submission_v2020_2026.yaml`. Root cause, checked directly
against `docling.json`'s own `texts[]`, not assumed: the profile's
`text_anchor` is the literal string `"Data Submitted by Institution for
India Rankings"` — IIT Bombay's NIRF-**portal**-copy phrasing. Sandip's
**own-site** copy opens with a differently-worded header for the same
concept:

```
IIT Bombay (portal copy):  "Data Submitted by Institution for India Rankings '2025'"
Sandip (own-site copy):    "Submitted Institute Data for NIRF'2025'"
                            "Welcome to Data Capturing System: OVERALL"
```

Same form, same underlying concept, different institution's copy, different
exact wording — this is the same category of brittleness P-14 already
names for column labels ("Header text varies between institutions for the
same field in the same form year"), just one level up: at the
**document-fingerprint** level rather than the column-label level. Neither
`profiles/nirf_submission_v2020_2026.yaml` nor `fingerprint/matcher.py` was
built with a second institution's document available to test against
before now — this is the first time that gap was actually exercised, not a
new defect introduced by this session.

## But the profile's BLOCKS generalize perfectly — checked, not assumed

The fingerprint miss is a document-identification problem, not a structural
one. Forcing the existing block/geometry rules (bypassing only the
fingerprint check) onto both Sandip documents and diffing against P2C's
own hand-written extraction, field for field, exactly as `scripts/
run_p2e_proof.py` already did for IIT Bombay:

```
2025 (2dcda6d8): engine value_rows=2021 checksum_rows=27  |  P2C value_rows=2021 checksum_rows=27  |  0 diffs
2024 (27dafb4b): engine value_rows=1518 checksum_rows=25  |  P2C value_rows=1518 checksum_rows=25  |  0 diffs
```

[VERIFIED] **Byte-identical, zero diffs, on both of Sandip's documents** —
including the 190-row faculty annexure (pages 5-13, `2dcda6d8`) and the
full unabridged 13-page own-site format, neither of which IIT Bombay's
4-page portal copy exercises at all. The single `ANY_TABLE` block (one
universal header-row-detection + column-0-as-label rule, no per-section
anchors) that this profile already used handles a document nearly 3× the
length, with a completely different page count and a large multi-page
table IIT Bombay's document has no equivalent of, with **no new unmapped
blocks and no change to the rule set.** This is a stronger generalization
result than T1's original run (IIT Bombay 2024 vs 2025, same institution) —
it is the actual cross-institution case T1 was written to prove, just not
literally the "second **ranked**" document PROMPTS.md's T1 names (Sandip
is unranked; this is its own-site copy, acquired via the WordPress route,
not the `nirfindia.org` portal — a different distinction than the one T1's
wording anticipated).

## Discovery mode: what it would show, since the fingerprint doesn't match

Per the mapping flow (`PROMPTS.md` P0/A8, `docs/architecture.md`'s D4), a
`NO_MATCH` document falls to discovery. Run for real, against the real
229-row dictionary:

```
2025 (2dcda6d8): 2020 candidates, 386 scored (>=1 nonzero suggestion)
2024 (27dafb4b): 1518 candidates, 279 scored
```

**These are not genuinely new, unmapped structure** — the block-generalization
check above already proves the existing profile's geometry explains every
one of these cells identically to the hand-coded P2C extraction. They are
an artifact of the fingerprint miss, not evidence of a document shape this
profile can't handle. **No human review pass has been done over these
candidates** (same honesty as the MIT T2 section above — a candidate count
is not a reviewed count), and none is needed to answer this section's
actual question, since the byte-identical block check already settles it
more directly than a discovery pass would.

## Answer to the question this section exists to answer

**Does not match cleanly** (fingerprint), **but produces no new candidates
that reflect real unmapped structure** (blocks) — a split answer, not
cleanly one of the two outcomes this file was asked to distinguish between,
stated as such rather than forced into whichever bucket is more
convenient.

- `profiles/nirf_submission_v2020_2026.yaml`'s `blocks` section, `fingerprint/
  matcher.py`, and every prior claim in this file's earlier sections about
  what the profile can extract **stand, now backed by a real second
  institution's document, not just a second year of one.**
- `profiles/nirf_submission_v2020_2026.yaml`'s `fingerprint.text_anchor`
  is too narrow — fitted on one institution's NIRF-portal phrasing, and
  this is the first session with a second institution's real document
  available to reveal that. **Not fixed in this session** — per instruction
  to stop after this step, `profiles/nirf_submission_v2020_2026.yaml` and
  `fingerprint/matcher.py` are unchanged. The fix this evidence points to,
  for whoever picks this up next: broaden `text_anchor` to a pattern that
  matches both observed phrasings (e.g. requiring `"NIRF"` + a rotation/
  grid-shape check, rather than one exact multi-word substring), then
  re-run `fingerprint/matcher.py` against both Sandip documents to confirm
  `MATCHED` before trusting it as fixed.
- T1's original 2026-09-14 entry (Sec3, "scope-limited... same institution,
  different year") is not retracted, but its own stated limitation is now
  demonstrably closed by better evidence sitting in this same file — a
  future reader should read this section alongside Sec3, not instead of it.

**Not proceeding to P2D.**

---

# 2026-09-14 (v4) — Fingerprint fix, T1 and T5 re-run

This section reports two closeouts before P2D: (1) the fingerprint fix the
(v3) section above identified but deliberately did not implement, and
(2) an honest, current-as-of-right-now status check on the review queue.
Sections above this one (v1, v2, v3) are unedited.

## 1. The fix

**Chosen approach: structural anchor, not broadened prose.** Of the three
candidates on the table (a regex covering both phrasings; a shorter shared
substring like `"NIRF" + "[IR-O-"`; matching on document structure alone
with no header string) — the second, refined, is what was implemented, for
a reason the data itself ruled out the others:

- **A regex "covering both phrasings"** (e.g. alternation between the two
  known sentences) would work today and re-break on the next institution
  that phrases its own header a third way — it does not fix the underlying
  problem, it just adds a second hardcoded sentence next to the first one.
- **`"NIRF" + "[IR-O-"` as an AND condition — checked, and it would have
  broken IIT Bombay.** `docs/e9a1d469/docling.json`'s `texts[]` contains
  the literal substring `"NIRF"` **zero times** — its header reads *"...for
  India Rankings..."*, not *"...NIRF..."*. This was checked directly before
  choosing an approach, not assumed from the candidate list's own
  phrasing.
- **Structure alone (rotation, table count, no text at all)** was rejected
  for a reason already on record in this file: `profiles/engine.py`'s own
  `fingerprint_matches()` docstring states `docling.json`'s `pages{}` dict
  carries no rotation field to check (`[OPEN]`, unchanged by this fix) —
  there is no non-text structural signal currently available to key on
  that doesn't also risk matching an unrelated 90°-rotated, multi-table PDF
  that isn't a NIRF form at all.

**What was implemented:** `fingerprint.text_anchor` is now the regex
`'Institute Name:.*\[IR-[A-Z]-[A-Z]-\d+\]'`, matched against each
`texts[].text` item individually (`text_anchor_match: regex`, a new mode
alongside the existing `substring` one — `profiles/engine.py::
fingerprint_matches` now branches on this field; `substring` still exists
unchanged for `profiles/us_cds_v2025.yaml`'s `"Common Data Set"` anchor).
The `[IR-<category>-<type>-<number>]` bracket is the NIRF Data Capturing
System's own institution-code field — a fixed government-form artifact
emitted identically by the form generator in every submission this project
has seen, not prose an institution could choose to word differently. This
is P-14's own rule ("anchor on section, locate by geometry, use label text
only to verify") applied one level up, at the document-fingerprint level
rather than the column-label level: the bracket code is closer to
*structure* than to *prose*, even though it is still matched as text.

Checked directly, not assumed: this pattern is present, verbatim, in all 4
`pdf_digital` artifacts acquired so far —

```
IIT Bombay: "Institute Name: Indian Institute of Technology Bombay [IR-O-U-0306]"
Sandip:     "Institute Name: SF's Sandip Institute of Technology and Research Centre [IR-O-C-41520]"
```

— on the same `"Institute Name:"` line, in both the NIRF-portal copy and
the institution's own-site copy, across both institutions and both years.

## 2. Fingerprint re-run — all 4 `pdf_digital` artifacts now match

```
$ .venv/bin/python3 -c "... fingerprint.matcher.match_document ..."
IITB 2025   (e9a1d469): outcome=MATCHED profile=nirf_submission_v2020_2026 value_rows=220 checksum_rows=29
IITB 2024   (d2c9d5c2): outcome=MATCHED profile=nirf_submission_v2020_2026 value_rows=219 checksum_rows=30
Sandip 2025 (2dcda6d8): outcome=MATCHED profile=nirf_submission_v2020_2026 value_rows=2021 checksum_rows=27
Sandip 2024 (27dafb4b): outcome=MATCHED profile=nirf_submission_v2020_2026 value_rows=1518 checksum_rows=25
```

[VERIFIED] All 4 now `MATCHED`, previously 2 of 4 (`NO_MATCH` on both
Sandip documents, per (v3)). Row counts are identical to the
already-established byte-identical figures from (v3)'s forced-match test
and `gate/P2C-extract.md`'s hand-written extraction — this fix changes
*whether the profile applies automatically*, not what it produces once
applied, which was already proven correct.

`tests/` (36 tests) re-run after this change: unaffected, all still pass.

## 3. T1 re-run — `scripts/run_p2e_t1_v2.py`, genuine cross-institution this time

```
IITB 2025 (e9a1d469):   fingerprint=MATCHED | value_rows=220 | checksum_rows=29 (within 28-37) | byte-identical to P2C=yes
IITB 2024 (d2c9d5c2):   fingerprint=MATCHED | value_rows=219 | checksum_rows=30 (within 28-37) | byte-identical to P2C=yes
Sandip 2025 (2dcda6d8): fingerprint=MATCHED | value_rows=2021 | checksum_rows=27 (OUTSIDE 28-37) | byte-identical to P2C=yes
Sandip 2024 (27dafb4b): fingerprint=MATCHED | value_rows=1518 | checksum_rows=25 (OUTSIDE 28-37) | byte-identical to P2C=yes

elapsed: 0.117s for all 4 documents, zero human input
T1 (all 4 pdf_digital artifacts, cross-institution): PASS
```

[VERIFIED] Fingerprint hit, profile applies, zero human input, sub-second —
on a genuine second **institution**, not just a second year, closing the
scope limitation both (v1) Sec3 and (v3) named explicitly.

**Not glossed over: Sandip's checksum-row counts (27, 25) fall OUTSIDE
PROMPTS.md's stated "28-37" band.** That band was fitted on IIT Bombay's
own two documents (29, 30) — the first time a second institution's real
count was available to test it against, it does not hold universally.
This is not a defect in the pipeline (every row is still byte-identical to
the hand-written extraction, per Sec2/Sec3 above and `gate/P2C-extract.
md`), it is evidence that PROMPTS.md's band itself is `[ASSUMED]`, fitted
on n=2 same-institution documents, not a property of "a NIRF submission"
in general. Flagged, not silently widened or ignored.

## 4. T5 re-run — `scripts/run_p2e_t5.py`, unchanged script, re-run after the fix

```
check 1 (live re-fetch of swarthmore.edu): sha256 identical, 0 new raw files, new manifest run row -- PASS
check 2 (profiles/engine.py determinism, IITB 2025): run A == run B, 220 value rows / 29 checksum rows both times -- PASS
T5: PASS
```

[VERIFIED] Unaffected by the fingerprint fix, as expected (T5 tests
idempotency and determinism, not fingerprint matching per se) — re-run
anyway per instruction, since it exercises `profiles/engine.py`'s
`run_profile()` code path, which this fix touched.

## 5. T3 — deliberately NOT re-run

Per explicit instruction. T3's own result (`gate/P2E-profiles.md` (v1)
Sec5: 0 values, 0 candidate fields, verified structurally — the homepage
never has a `<table>` and is classified `unknown` before any profile or
fingerprint check ever runs) is unrelated to this fix and stands unchanged.

## 6. Review queue status — plainly, again, separate from the above

**No.** As of right now, no human independent of any Claude Code session
has opened `review/queue/mit_cds_2025_26_dc2701ee.jsonl` (the original,
24-code-dictionary run) or `review/queue/mit_cds_2025_26_dc2701ee_v2dict.
jsonl` (the real-dictionary re-run) and confirmed, reassigned, or rejected
any candidate in either file. Nothing about this section's fingerprint fix
changes that — the fix is a document-*identification* mechanism, entirely
separate from the KPI-*mapping* review queue, and fixing one says nothing
about whether the other has been looked at. This is the same honest answer
given under (v2)'s "Instruction 6" heading; it has not changed because no
review activity has occurred since.

**These are two separate, independently-tracked open items, not one:**
1. Fingerprint generalization across institutions — **closed by this
   section**, backed by a real cross-institution re-run (Sec3 above).
2. Human confirmation of the MIT discovery/review queue — **still open**,
   unchanged since (v2). Closing (1) must not be read as progress on (2).

**Not proceeding to P2D.**

---

# T3b — incidental table stress test, not the original T3

`gate/P4-review.md` finding H1: the original T3 (swarthmore.edu) is a real
PASS, but narrow — it only proves one homepage with **zero** `<table>`
elements yields zero values. It does not test what happens on a homepage
that has an incidental (non-disclosure) `<table>` at all. This section
runs that test for real. **H1's fix is deliberately NOT implemented here**
— this reports what the unmodified pipeline actually does, per instruction.

## Finding a real fixture

Every liberal-arts-college and IIT homepage tried first (`williams.edu`,
`amherst.edu`, `bowdoin.edu`, `middlebury.edu`, `carleton.edu`,
`pomona.edu`, `oberlin.edu`, `reed.edu`, `grinnell.edu`, `macalester.edu`,
`vassar.edu`, `hamilton.edu`, `bates.edu`, `iitk.ac.in`, `iitm.ac.in`,
`cam.ac.uk`, `harvard.edu`, `yale.edu`, `princeton.edu`, `cornell.edu`,
`brown.edu`, ...) returned **zero** `<table` occurrences in the raw fetched
HTML — modern homepages mostly don't use `<table>` markup at all, which is
itself worth noting: it narrows how often this stress scenario would even
arise in practice, though it says nothing about whether the mechanism
would handle it correctly if it did.

`https://www.jnu.ac.in/` (Jawaharlal Nehru University — a real, uninvolved
Indian university, not one of this project's three iteration-1
institutions) returned 2. `robots.txt` checked with `protego` first
(`can_fetch=True` for `/`, a plain Drupal file, same shape as `gate/
P2A-acquire.md`'s and the original T3's robots checks).

## Run — `scripts/run_p2e_t3b.py`, same pipeline as T3, unmodified

```
$ .venv/bin/python scripts/run_p2e_t3b.py
=== T3b fetch: https://www.jnu.ac.in/ ===
robots.txt check (protego): can_fetch=True
HTTP 200, Content-Type=text/html; charset=UTF-8, 135837 bytes
raw <table markup count in fetched bytes: 2
raw store: raw/sha256/90/62/90627af0....html (written)

=== classify ===
label=html_table

=== convert ===
n_tables=2 n_texts=412

=== fingerprint ===
outcome=NO_MATCH

=== T3b RESULT ===
candidate fields (total table cells discovery would propose): 0
candidates with >=1 nonzero KPI-dictionary suggestion: 0
Zero candidates scored against the KPI dictionary (all table cells present, but none token-overlapped any of the 229 real KPI codes).
```

[VERIFIED] Real fetch, real Docling conversion, real fingerprint and
discovery run — nothing simulated. `classify` correctly routed this to
`html_table` (unlike the original T3 fixture, which never got past
`unknown`) — this homepage genuinely has structured markup this time.
`convert` produced 2 real tables. `fingerprint` correctly returned
`NO_MATCH` (no NIRF or CDS anchor). **Discovery proposed zero candidates.**

## Why — checked directly, not assumed, and it is NOT what it looks like at first

The honest reason is narrower and more coincidental than "the pipeline
safely recognised incidental content":

```
$ .venv/bin/python3 -c "... iter_table_cells ..."
n tables 2
total cells 10
col_index distribution: Counter({0: 10})
```

**Both tables on this page are single-column** — a Drupal "views" widget
listing admission notices, one link per row, one `<td>` per `<tr>`. Every
one of the 10 real cells has `col_index == 0`. `discovery/candidates.py::
generate_candidates` excludes `col_index == 0` unconditionally (the same
"column 0 is always a label, never a value" geometric convention
`extract/values.py` uses for real NIRF tables — `gate/P2C-extract.md` Sec8,
flagged `[R]` there). **All 10 cells are excluded for that reason, not
because anything recognised them as page furniture rather than
self-disclosure.** A single-column link-list table structurally happens to
land entirely in the "always label" column, by coincidence of its shape,
not by any designed defense.

## What this does and does not settle re: `gate/P4-review.md` H1

**Does not close H1.** This result is genuinely reassuring for *this*
specific incidental-table shape (a single-column notice list), but it
provides no evidence about a multi-column incidental table — e.g. a
"quick facts" grid, a two-column contact/office directory, a fee-schedule
table on an admissions page — which would have real cells at `col_index >=
1` and would reach `generate_candidates`'s scoring step exactly like a
genuine NIRF or CDS value cell does. `discovery/candidates.py` still has no
mechanism that distinguishes institutional self-disclosure from page
furniture by anything other than this accidental column-0 side effect.
**H1 remains open.** The honest, falsifiable answer to this section's own
question ("does discovery propose any candidate? If yes, does it score
high enough that a careless reviewer could plausibly confirm it?") is:
**no candidates were proposed on this fixture, for a structural reason
unrelated to the concern H1 raises** — not "the concern was tested and
did not materialize."

**H1 remains OPEN, accepted as a known limitation for this submission.
Zero candidates on the JNU fixture was produced by an unrelated structural
coincidence (all cells at col_index==0), not by any mechanism that
distinguishes disclosure tables from page furniture. This gap affects only
the general adhoc_url discovery path — it does not affect any of the three
iteration-1 institutions (Sandip/IIT Bombay fingerprint-match to a known
profile and never reach discovery; MIT's tables are genuine disclosure
data). Decision: accepted, not fixed, time-boxed for submission. A
multi-column incidental table remains untested.**

**Not proceeding to P2D.**

---

# Open items summary (final section of this file)

- **P3 (`docs/architecture.md`) — deferred.** Not built this iteration;
  `gate/P4-review.md` was run ahead of its normal entry gate, explicitly
  noted there as not satisfying the real P3→P4 chain.
- **`db/schema.sql` — minimal demo-scoped schema, built 2026-09-14 to
  unblock the presentation artifact, NOT the full P2D phase** (the Q1-Q5
  acceptance queries per PROMPTS.md P2D, the general mapping_candidate
  review workflow beyond this one recorded decision, and the required
  self-verification loader output are not present; the source/profile/
  mapping_candidate tables themselves ARE present). Full P2D remains open,
  tracked in every prior gate file's "Not proceeding to P2D" status.
- **Fingerprint cross-institution gap — FIXED (v4).** `profiles/
  nirf_submission_v2020_2026.yaml`'s fingerprint now matches all 4
  `pdf_digital` artifacts (2x IIT Bombay, 2x Sandip) via a structural
  institution-ID-bracket regex, not institution-specific prose. T1 and T5
  re-run and passing on the fix.
- **Review-queue human sign-off — PENDING, unchanged.** No human
  independent of any Claude Code session has opened either `review/
  queue/*.jsonl` file (24-code run or real-dictionary run) and confirmed,
  reassigned, or rejected a single candidate. Restated at (v2) and (v4);
  still true now.
- **`gate/P4-review.md` M1-M4, L1 — dormant, not fixed.** Fingerprint's
  declared `page_rotation` check is unenforced (M1); multi-profile
  collision has no detection (M2); `_apply_block` only ever reads
  `blocks[0]` (M3); `contestable` is caller-supplied, not dictionary-
  derived (M4); discovery silently drops label-less cells before scoring
  (L1). None are currently causing wrong output on the 5 real artifacts
  acquired; none have been fixed.
- **`gate/P4-review.md` H1 — now explicitly accepted-not-fixed (this
  file's T3b section, above).** Stress-tested against a real incidental
  table (JNU); the specific fixture tested happened to produce zero
  candidates for a reason unrelated to the underlying gap. The gap itself
  — no mechanism distinguishes disclosure tables from page furniture in
  the general `adhoc_url` discovery path — remains open, does not affect
  any of the three iteration-1 institutions, and is accepted rather than
  fixed for this submission.

**Not proceeding to P2D.**
