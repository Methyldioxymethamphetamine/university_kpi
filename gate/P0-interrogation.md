# P0 — Interrogation gate

**Phase:** P0. **Entry gate:** `CLAUDE.md` + six documents — all resolve at their exact paths. [VERIFIED]
**Tooling note:** No working `grillme` skill exists in this environment. An earlier attempt to pull one
(`npx skills use https://github.com/mattpocock/skills --skill grill-me`) returned a stub whose body is
`Call the Skill tool with "grilling"` — "grilling" is not a registered skill here, and the stub carries
no actual interview logic. Rather than fabricate having invoked a tool, the interrogation below was
performed directly against the required lines of attack. [OPEN — should the project want a real
grillme skill, one needs to be authored, not downloaded from that source.]

---

## Confirmation of reading — one new number per document

1. `iteration-1-source-investigation.md` — Sandip's 190-row faculty annexure: average experience
   **124.7 months** (~10.4 years).
2. `digits-words-checksum-analysis.md` — Sandip's Engineering submission expenditure figure is wrong by
   **₹53 crore** (`173860605` read vs `70.39 crore` intended vs `17.39 crore` as typed — a leading-digit
   defect, distinct from the ₹37.5-lakh salary error).
3. `nirf-coverage-of-229-kpis.md` — of the 72 NIRF concepts found in the forms, **39** have no KPI code
   at all in the 229-row dictionary (more than half).
4. `notes/methodology.md` — the checksum's 2.75% pooled disagreement rate carries a 95% Wilson score
   interval of **1.54%–4.86%** on 11 events in 400 trials; the honest quote is "a few percent," not
   "2.75%."
5. `v2-spec-disagreements.md` — Doc 3's source directory routes **93%** (148 of 160 themes) to
   "University official website / annual report / statutory disclosures" — a homepage, not a
   retrievable document.
6. `dictionary-defect-verification.md` — the `Formula` column is **three** columns left of
   `Benchmark_Direction`, not one as originally briefed (`Unit → Data_Type → Formula → Scraping_Keywords
   → Primary_Source → Benchmark_Direction`).

---

## Severity summary

```
 A1  Docling/rotation assumption ............ ASSUMED, untested .......... HIGH   (no change — P1 IS the test)
 A2  Silent-wrong inventory .................. 6 concrete points .......... —      (carry-forward, no single verdict)
 A3  docs/ regenerable claim ................. FALSE as stated ............ HIGH   (pin + record Docling version)
 A4  Postgres vs SQLite+FTS5 ................. argued, stack holds ........ LOW    (no change)
 A5  What breaks first at 537 ................ checksum geometry consts ... HIGH   (carry-forward to P2C)
 A6  Unhandled-artifact classifier ........... fetch-failure gap .......... MEDIUM (schema note for P2A)
 A7  Storage-tree ambiguity .................. docs/values provenance ..... HIGH   (schema note for P2D)
 A8  Profile/fingerprint model ............... brittleness relocated ...... MED-HIGH (decision + rule needed by P2E)
 A9  Unasked attacks ......................... 3 raised .................... HIGH  (carry-forward)
```

None of these block starting **P1**, for a reason specific to each — argued below, not asserted.

---

## A1 — Does Docling's layout-model approach make `/Rotate 90` a non-issue?

**The attack.** `notes/methodology.md` §2.5 establishes the failure mode against `pdf.js`'s raw
coordinate API: grouping by `transform[5]` under `/Rotate 90` groups columns and calls them rows,
merging two side-by-side tables into fluent, wrong output with no error raised. Docling's approach is
different in kind — it renders the page and runs a trained layout-detection model on the rendered
bitmap, then maps detected regions back to coordinates. **[ASSUMED]** this sidesteps the bug, on the
theory that if the rasterizer honours `/Rotate` when producing the bitmap, the model sees an
upright page and never encounters the swapped-axis trap at all.

That assumption has two unverified sub-claims, not one: (a) that Docling's *rendering* step
honours page rotation, and (b) that Docling's *bounding boxes*, once computed on the rotated bitmap,
are reported back in the same coordinate space a citation viewer will use to draw a rectangle on the
original PDF page. (b) matters even if (a) is true — a layout model can correctly read an upright
rendered page and still hand back a bbox that doesn't line up when a standard PDF viewer auto-rotates
the page for display. Nothing in the six documents tests (b), because nothing in the investigation
used Docling at all (`methodology.md` §10: "Not used, and why... Docling... none was exercised here").

**Cheapest test.** Exactly P1's own CHECK B: convert the IIT Bombay 2025 Overall PDF, and assert —
not eyeball — that the row `UG [4 Years Program(s)] | 1161 | 1059 | 1039 | 1030` comes back with that
exact label-to-value association, and separately confirm the reported bbox for one of those cells
lands on the correct rectangle when the original (rotated) page is rendered.

**Fallback and cost.** Already specified and budgeted: port the geometric reconstruction in
`methodology.md` §2.5 to `pypdfium2`, one day, isolated to `convert/`, per `INSTRUCTIONS.md` §8.

**Verdict:** ASSUMED, HIGH severity, **no change implied for P0** — this is not a gap in the
architecture, it is precisely the question P1 exists to settle. The only requirement I'm adding: P1's
gate file must record the exact Docling + docling-core version and confirm bbox alignment, not only
label-value association (see A3).

---

## A2 — Every point where wrong output can be produced with no error raised

Enumerated by layer, each with what the operator would see and how long before anyone noticed:

1. **Acquisition — content-type mismatch.** A fetch could return a 200 with an HTML error/CAPTCHA page
   at a URL expected to be a PDF. If `expected_content_type` in `IN_sources.yaml` isn't enforced
   strictly at fetch time, this stores as if it were a valid artifact. Operator sees: nothing, until
   conversion either fails loudly (good) or — worse — Docling extracts *some* text from the HTML shell
   and it silently becomes a near-empty, oddly-shaped document. Not noticed until someone checks yield
   counts per document, which is a P2C/P2E-stage check, not an acquisition-stage one.

2. **Conversion — field-set variance by category untested.** `methodology.md` §2.6 confirms rotation
   and structure across 8 documents from 2 institutions, both "Overall" category. Engineering/
   Management/Pharmacy categories, or any institution-published copy with a different layout (already
   evidenced: Sandip's own-site copy differs in page count and content from IIT Bombay's NIRF-portal
   copy), could silently return nulls for blocks that exist if the parser is templated rather than
   discovering sections by header (P5 in the pattern catalogue already names this correctly).

3. **Digits/words checksum — regression risk on parser edits.** `methodology.md` §6.3 shows a
   scale-absorption bug and an idiom-parsing bug both produced *confident, wrong* mismatches; the
   idiom bug (ratio exactly 1.0000, deltas of a few hundred on nine-figure numbers) "very nearly
   shipped." P22 mandates a self-test before use — but nothing structural prevents a future edit to
   this parser from skipping that self-test. This is process discipline, not a code guarantee.

4. **Fingerprint/profile matching — partial match under-extraction.** Covered fully in A8.

5. **Value normalization — `int(x) if x else 0`-shaped bugs.** P-8 already prohibits treating `-` as
   zero, but the *mechanism* by which a careless cast could reintroduce this (a default-on-parse-failure
   pattern) isn't named. `999 (Zero)` in `digits-words-checksum-analysis.md` is exactly the kind of
   handwritten-form artifact that would trip a naive int-cast fallback.

6. **A new one, not in any document: unit-scale agreement without correctness.** The digits/words
   checksum only catches *disagreement within a cell*. It cannot catch a field where an institution
   consistently mistypes a Rs.-Crore field as Rs.-Lakh throughout a document — digits and words would
   agree with each other (both wrong by the same factor), and the checksum would report `CONFIRMED`
   with *higher* apparent confidence than an unconfirmed value. This is structurally the same shape of
   error as the ₹37.5-lakh case, but invisible to the exact mechanism built to catch that case. See A9.

7. **Database writes — commit semantics.** `P-10`/P21 cover the openpyxl `value=None` no-op trap for
   Excel writes, but the same *class* of bug exists at the Postgres layer: `psycopg` 3 defaults to
   `autocommit=False`; a script that executes an INSERT and never calls `.commit()` (or relies on a
   context-manager pattern borrowed from a different client library) reports success and persists
   nothing. Not covered by any existing P-rule, which are all about the xlsx/write-then-readback case
   specifically, not the DB case.

**No single severity applies to this section** — it's an inventory, carried forward to inform P2A–P2E
design, not a verdict on the current architecture.

---

## A3 — Is `docs/` really regenerable with nothing lost?

**Attack.** `docs/` is declared regenerable: delete it, re-run Docling, lose nothing. `pyproject.toml`
pins `docling>=2.0` and `docling-core>=2.83` — open floors, no ceiling. **[VERIFIED]** During this
project's own setup, `uv pip install` resolved to Docling **2.127.0** — a large distance from the
"2.0" floor the constraint suggests was the baseline. Two runs of "the same" pipeline, months apart,
or on two different machines, can silently get different Docling and model-weight versions with zero
version pin recorded anywhere per-document.

**Why that breaks "lose nothing."** If a `values/` row's citation is anchored to a bounding box or
element identifier from a specific `docs/` JSON export, and `docs/` is later regenerated under a
different Docling version whose layout model segments the page slightly differently, the citation can
silently point at a shifted or wrong rectangle — the exact "plausible, confident, wrong" failure shape
`CLAUDE.md` exists to prevent, now at the tooling-version layer instead of the document layer.

**What would be lost:** citation fidelity across a `docs/` regeneration, invisibly, unless the exact
Docling/model version used to produce a given `docs/` artifact is recorded and checked before any
citation built from it is trusted after a regeneration.

**Verdict:** the claim is **FALSE as stated**. Severity: **HIGH**. Change implied — not for P0/P1
directly, but as a requirement to carry into P1's own output and into P2D's schema: (a) P1's gate file
must record the exact Docling + docling-core versions used [VERIFIED, not just claimed]; (b) the P2D
schema must record a `docling_version` (or equivalent) alongside every `docs/` artifact and propagate
it to any row that cites it, so a future regeneration under a different version is a detectable event,
not a silent one.

---

## A4 — Postgres for 3 institutions is over-built. Argue SQLite+FTS5.

**The strongest case for SQLite.** Iteration 1's own yield estimate is ~175–210 populated rows across
3 institutions × 2 years (`nirf-coverage-of-229-kpis.md`) — trivial volume. A single `.db` file needs
no container, no port (I hit a live port-5432 conflict with an unrelated container during this
project's own setup — SQLite has no such failure mode), can ship inside the repo, and is trivially
reproducible for a demo that has to work live in front of a university president. FTS5 covers the
`doc_item` search requirement (P-16) without pgvector.

**Why it still loses.** `CLAUDE.md` provisions pgvector specifically, which only makes sense as
preparation for *fuzzy candidate search* in the mapping-review queue (P-13's discovery mode) or future
scale beyond iteration 1's 3 institutions — a capability SQLite doesn't have a comparably mature
equivalent for. `CLAUDE.md` also states the stack is "settled, not open for re-litigation," and this
project's own escalation table treats a proposal to relax a settled rule as something to flag, not
decide solo. The operational cost of Postgres (docker compose) is, as of this session, a **paid, working
cost** rather than a future unknown — it's already running and healthy.

**Migration cost if I'm wrong and iteration 1 should have started on SQLite:** low. Every P-rule
(`P-4` immutable `raw/`, `P-5` insert-only `value`, no UPDATE/DELETE) forces a small number of flat,
append-only tables — the cheapest possible schema shape to move between engines. Dump to CSV, `COPY`
into Postgres, resolve SQLite's dynamic typing into explicit constraints. Comfortably under a day,
consistent with how cheaply this project's other fallback paths are already costed (P1's one-day
pypdfium2 port).

**Verdict: no change.** Severity: **LOW**. The attack is genuinely strong on operational simplicity but
loses on (a) explicit "settled" status, (b) pgvector's evident future purpose, (c) sunk, working setup
cost.

---

## A5 — What breaks first at 3 → 537 institutions? Name the component.

**Not "scale."** Two components in this project are explicitly fitted to exactly 2 institutions
(IIT Bombay, Sandip) and 8 documents, and the documents say so themselves (`methodology.md` §8:
*"Whether `/Rotate 90` holds across all 537 ranked institutions... Verified on 8 documents from 2
institutions... almost certainly... but 'almost certainly' is not 'checked.'"*).

Between the two, the one that fails **first**, specifically: the digits/words checksum's cell-reassembly
constants — the `22`-unit horizontal-gap threshold and the `/6` column-bucket divisor in
`methodology.md` §6.1, explicitly marked `[R]` and "fitted to this form's leading and column spacing,
would need re-tuning for a differently-typeset document." This breaks before the rotation-handling
itself does, because rotation-handling is a **binary** property (`page.rotate == 90` or not) that
generalizes cleanly across any document sharing the form, while the reassembly constants are
**continuous values tuned by inspection** — a category of failure that degrades silently: a slightly
wrong gap threshold doesn't crash, it just occasionally merges or splits a wrapped cell wrong, which
either produces a safe `UNVERIFIED` (regex finds nothing) or, less safely, a corrupted-but-still-valid-
looking `digits(words)` string that could feed a false `CONFIRMED` or `CONFLICTING`.

The specific failure point: any institution using a NIRF category template other than "Overall," or
publishing an institution-generated copy with different typesetting (already evidenced — Sandip's own
copy differs in page count and layout from IIT Bombay's NIRF-portal copy of the same form).

**Verdict:** carry-forward to P2C. Severity: **HIGH**, but scoped correctly to the checksum-at-scale
phase, which is explicitly out of iteration 1's stated boundary (3 institutions only). Not a P0/P1
blocker.

---

## A6 — The unhandled-artifact classifier: where does it fail, what still needs re-crawling?

**Where it fails.** "Record what we can't handle yet, so later phases don't need to re-crawl" presumes
the classifier's own judgment about *what an artifact is* is reliable. If a fetch succeeds but returns
mistyped content (A2, point 1), the record itself is wrong — not "unhandled and flagged," but silently
mis-filed as a failed parse of the expected type. The recorded metadata degrades quietly rather than
loudly.

**What still needs re-crawling regardless of this design:** anything that never became an artifact in
the first place — a failed fetch (network error, 404, auth-wall, a WordPress media URL that 404s
between discovery and fetch). Nothing in the six documents describes a `fetch_attempt`/crawl-log record
distinct from `artifact`; if only successful fetches are recorded, a failed one leaves **no trace at
all**, and the only way to find it later is to re-run the whole source registry, which is exactly the
re-crawl this design is meant to avoid.

**Verdict:** MEDIUM. Not a P0/P1 blocker (iteration 1 is 3 institutions, hand-supervised). Schema note
for P2A: a fetch-attempt log, separate from `artifact`, closes this gap cheaply.

---

## A7 — Attack the storage tree: `raw/` + `docs/` + `values/`

**Ambiguity found, compounding A3.** Nothing in `CLAUDE.md`'s three-way description of the tree pins
which `docs/` generation (by Docling version) a given `values/` row's citation was built from.
`values/` is described as "run-partitioned," which pins the *extraction* run, but not the *conversion*
run that fed it. After any `docs/` regeneration, this is unresolvable without an explicit link.

**Two more gaps, found by comparing the documented tree against the actual scaffold:**

- `derived/` exists in the repo (`INSTRUCTIONS.md` step 2, its own `.gitignore` rule) but is never
  named in `CLAUDE.md`'s tree description (which lists only `raw/`, `docs/`, `values/`). Its mutability
  contract and contents are undefined.
- `db/` exists in the scaffold (same `mkdir -p` line) but is referenced nowhere else — `docker-
  compose.yml` uses a named Docker volume (`pgdata`), not a bind mount to `./db`. As things stand, `db/`
  is an empty, purposeless directory in a tree that otherwise assigns every directory a clear
  ownership and mutability rule.

**Verdict:** the `docs/`↔`values/` provenance gap is **HIGH** (ties to A3, matters before P2D's schema
is final — P2D's own reviewer checklist already requires "Q4 re-run proves prior rows unchanged with a
checksum," which is exactly where this gap would surface). The `derived/`/`db/` documentation gaps are
**LOW** — cosmetic today, but worth closing before they're mistaken for settled decisions.

---

## A8 — Attack the profile model

**PARTIAL fingerprint match (same anchor, unknown blocks).** `INSTRUCTIONS.md` §11 already names this
as unresolved and explicitly defers final authority to "P0/A8" — this phase, this question. I'm
answering it, not deferring it further: **[ASSUMED — recommendation, requires explicit reviewer
sign-off in this gate file, not a settled decision]** adopt the stated default — apply known blocks,
queue the unknown blocks into the P2E review queue, and flag the artifact `PROFILE_INCOMPLETE`. The
reasoning is the same one behind P-15: a PARTIAL match that silently returns only the known blocks is
visually indistinguishable from a document that genuinely lacks those blocks (e.g. "MIT doesn't report
patents" vs. "our profile doesn't know MIT's patents block yet") unless the flag exists. This needs a
reviewer to actually check the box, not just be present in this document.

**Where a profile can silently apply to the wrong document.** The pattern-catalogue finding that "one
parser handles all NIRF years and both institution types" (§2, `iteration-1-source-investigation.md`)
cuts both ways. If a profile fingerprints on section-anchor + geometry, and two institutions share an
*identical* form template by design, fingerprint content alone has **zero discriminating power between
institutions** — which is fine only if "profile" is scoped to a *form template*, and institution
identity is carried separately via `source_id` from the registry, never re-derived from the document's
own content. Nothing in the six documents makes this distinction explicit. If an implementer conflates
"profile" with "institution," the system would work today (both institutions currently share one
template) while hiding a landmine for the day one institution's form deviates.

**Is "anchor on section, locate by geometry, verify by label" actually robust?** It correctly kills the
*already-proven* failure mode (P4: label text varies by institution). It does not eliminate brittleness
— it relocates it to two places that are less proven-broken but structurally the same *kind* of risk:
geometry tolerances (subject to the exact same small-sample generalization problem as A5's checksum
constants), and label-verification, which — because label text varies — must be *fuzzy*, reopening the
precise threshold-fragility already demonstrated twice in this project (KPI-mapping's 0.34→0.30
threshold changing match counts 116→164; the digits/words idiom-vs-number ambiguity). "Verify by label"
is not exempt from `P-13`'s auto-accept prohibition just because it's a secondary check rather than the
primary key.

**Verdict:** Severity **MEDIUM-HIGH**. Change implied, due before P2E (not before P1): a PARTIAL or
weak fingerprint match must route to human review exactly as a weak KPI-label match does — no
auto-accept of a fingerprint at any confidence score, symmetric with `P-13`.

---

## A9 — What wasn't asked, that I'd attack

At least two, as required; three raised:

1. **The checksum can't catch a systematically-wrong-but-self-consistent scale.** Covered in full in
   A2, point 6. This is the sharpest new finding here: the entire persuasive case for this project rests
   on catching digit/word disagreement, but the mechanism is structurally blind to an institution that
   consistently mistypes Rs.-Lakh as Rs.-Crore (or vice versa) throughout a document — digits and words
   agree with each other, and the checksum would report `CONFIRMED` with *more* apparent confidence
   than an unconfirmed single-source value, not less. Nowhere in the six documents is this considered.

2. **Docling/model version pinning is a live, unmanaged risk, not a hypothetical.** Covered in A3 as a
   provenance problem; it's also, independently, a *reproducibility* problem for the P2D requirement
   that a re-run produce checksum-identical prior rows. Nothing pins the model weights or the library
   version anywhere the pipeline itself checks.

3. **Staleness of institution-published PDFs has no detection mechanism.** `P-4` correctly makes a
   re-fetch that returns different bytes a new artifact — but nothing describes *when* a re-fetch is
   triggered. Sandip's own-site PDFs are not under NIRF's central authority and could be silently
   replaced at the source URL at any time with no version marker in the file itself. For iteration 1
   (fixed 3 institutions, 2 years, one demo) this doesn't matter. For anything past the demo, there's no
   described policy for detecting that a previously-fetched URL now serves different content without a
   human manually re-running P2A.

---

## BLOCKERS

None of A1–A9 requires resolution before **Phase 1** specifically. P1's own scope — per
`INSTRUCTIONS.md` §8 and the P1 prompt's own CHECK B — is narrow: one document, does Docling recover a
known value with correct label-to-value association, and it is explicitly forbidden from starting any
fallback work in the same session even if it fails. None of the HIGH-severity items above (A1, A3, A5,
A7) are prerequisites to running that narrow spike; they are prerequisites to **later** phases
specifically:

- **P1 itself** must additionally record the exact Docling + docling-core version used, and confirm
  bounding-box alignment, not only label-value association (A1, A3).
- **P2A** should add a fetch-attempt log distinct from `artifact` (A6).
- **P2C** must treat the checksum's reassembly constants as unverified beyond the 2 tested institutions
  before running it at wider scale (A5).
- **P2D**'s schema must record a Docling/model version per `docs/` artifact and propagate it to citing
  rows, and must document `derived/` and `db/`'s actual contracts or remove them (A3, A7).
- **P2E** must apply the `PROFILE_INCOMPLETE` recommendation from A8 (pending explicit reviewer
  sign-off in this file, not just my recommending it), and must extend `P-13`'s no-auto-accept rule to
  fingerprint/profile matches, not only KPI-label matches (A8).

Separately, unresolved but also not a P1 blocker: the three client-original files
(`DOC-20260901-WA0019.xlsx`, `requirement-spec.docx`, `parameters.docx`) are not present in
`registry/client-docs/`. [OPEN] P1 needs only the raw PDFs already available; these are needed starting
at P2E.

**P0 CLEAR — proceed to P1.**
