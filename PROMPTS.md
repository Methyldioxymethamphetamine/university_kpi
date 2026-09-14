# Claude Code — phase-gated prompt set

**University KPI benchmarking: acquisition, extraction and storage layer, iteration 1**

Version 2 — includes the profile/mapping layer (P2E) and laws P-13 to P-16.

---

## How to use this file

Each block below is a **separate prompt**. Paste **one per Claude Code session**.
Do not concatenate them. Do not run two in one session.

Every phase declares an **entry gate** — a file that must already exist. If the
gate file is absent, the correct behaviour is to stop, not to improvise.

`CLAUDE.md` lives at the repo root and loads automatically. It is not pasted.

### Gate chain

```
P0  ──►  gate/P0-interrogation.md
P1  ──►  gate/P1-spike.md
P2A ──►  gate/P2A-acquire.md
P2B ──►  gate/P2B-convert.md
P2C ──►  gate/P2C-extract.md
P2E ──►  gate/P2E-profiles.md        ← before P2D, deliberately
P2D ──►  gate/P2D-index.md
P3  ──►  docs/architecture.md
P4  ──►  gate/P4-review.md
```

**Why P2E precedes P2D:** the `profile` and `mapping_candidate` tables are part of
the schema. Discovering you need them after writing `schema.sql` means a
migration in week two.

---
---

# P0 — Interrogation gate

- **Entry gate:** repo contains `CLAUDE.md` and the six documents it lists
- **Exit artifact:** `gate/P0-interrogation.md`
- **Forbidden:** writing code, creating directories, installing packages, network requests

```
PHASE 0 — INTERROGATE THE ARCHITECTURE. NO CODE.

Read CLAUDE.md and all six documents it lists. Confirm you have read them by
quoting one specific number from each that you did not previously know.

You may not write code in this phase. If you produce a code block longer than
five lines, you have violated scope. The only file you create is
gate/P0-interrogation.md.

Invoke the `grillme` skill against the architecture below. Attack it. I want it
broken now, while breaking it is free.

  ARCHITECTURE UNDER TEST
  -----------------------
  Acquisition:  Scrapy, fetch-only, content-addressed raw store
  Conversion:   Docling -> DoclingDocument JSON (page + bbox per element)
  Verification: pypdfium2 for coordinate-level checks
  Index:        Postgres 17 + pgvector, single system of record
  Tree:         raw/ immutable | docs/ regenerable | values/ run-partitioned
  Mapping:      fingerprint -> stored profile, else discovery -> human review

  REQUIRED LINES OF ATTACK — answer every one explicitly
  ------------------------------------------------------
  A1. Docling uses a layout-detection model on rendered pages rather than raw
      PDF coordinates. I have ASSUMED this makes /Rotate 90 a non-issue.
      Is that assumption sound? What is the cheapest test that settles it?
      What is the fallback if it is false, and what does the fallback cost?

  A2. Enumerate every point in this design where wrong output can be produced
      with no error raised. For each: what would the operator see? How long
      before anyone noticed? This list is the primary output of this phase.

  A3. docs/ is declared regenerable — delete it, re-run Docling, lose nothing.
      Is that true? Name anything that would be lost. Consider: Docling model
      versions changing between runs.

  A4. Postgres for a 3-institution iteration 1 is arguably over-built. Argue
      the case for SQLite+FTS5 as hard as you can, then tell me which wins and
      what the migration would actually cost if I start with SQLite.

  A5. What breaks first at 3 institutions -> 537? Name the specific component
      and the specific failure. Do not say "scale".

  A6. The classifier records artifacts iteration 1 does not handle (scans,
      DOCX, unknown types) so later phases can find them without a re-crawl.
      Where does this fail? What would we still have to re-crawl for?

  A7. Attack the storage tree itself. Is there a case where the
      raw/ + docs/ + values/ split loses information or creates ambiguity?

  A8. The profile model: fingerprint a document, apply a stored profile of
      (section anchor + geometry + column roles), fall back to discovery mode
      with a human review queue. Attack it.
      - What happens on a PARTIAL fingerprint match — same anchor, but blocks
        the profile does not know about? Propose the behaviour and argue it.
      - Where can a profile silently apply to a document it should not match?
      - Is "anchor on section, locate by geometry, verify by label" actually
        robust, or does it just move the brittleness somewhere less visible?

  A9. What have I not asked about that you would attack if this were your
      project? At least two items. This is not optional.

  OUTPUT FORMAT — gate/P0-interrogation.md
  ----------------------------------------
  For each of A1-A9: the attack, your verdict, severity (CRITICAL / HIGH /
  MEDIUM / LOW), and the specific change it implies — or "no change, and here
  is why the attack fails".

  Then a final section: BLOCKERS. Anything CRITICAL or HIGH that must be
  resolved before Phase 1 begins.

  STOP CONDITION
  --------------
  If any BLOCKER exists, end your response with:
    "BLOCKED — N blockers. Do not proceed to P1."
  and stop. Do not propose fixes unless asked. Do not proceed to P1 under any
  circumstances, including if the operator seems to want you to.

  If there are none, end with:
    "P0 CLEAR — proceed to P1."
```

---

# P1 — Spike gate

- **Entry gate:** `gate/P0-interrogation.md` exists and ends with `P0 CLEAR`
- **Exit artifact:** `gate/P1-spike.md`
- **Forbidden:** repo structure, pipelines, Postgres, more than one document

```
PHASE 1 — SPIKE. ONE FILE. THREE CHECKS. NOTHING ELSE.

Read CLAUDE.md. Read gate/P0-interrogation.md and honour every change it
mandated. If gate/P0-interrogation.md does not exist or does not end with
"P0 CLEAR", stop immediately and say so.

Scope is exactly one document:
  https://www.nirfindia.org/nirfpdfcdn/2025/pdf/Overall/IR-O-U-0306.pdf

You may create only: spike/ and gate/P1-spike.md. No repo structure. No
Postgres. No second document. If you find yourself generalising, you are out
of scope — stop and return to the three checks.

  CHECK A — IDEMPOTENT ACQUISITION
  Fetch with Scrapy. Store under raw/sha256/. Fetch again.
  PASS: byte-identical, same sha256, second fetch creates no new file.
  Report: the actual hash, both times.

  CHECK B — P1 / ROTATION. THIS IS THE ONE THAT MATTERS.
  Convert with Docling. save_as_json(). Then, in the resulting JSON, locate:
      "UG [4 Years Program(s)]"  followed by  1161, 1059, 1039, 1030
  in document order, associated with that label and no other.
  PASS: the row is recoverable with correct label-to-value association.
  FAIL: anything else, including plausible-looking output with wrong pairing.

  You must not eyeball this. Write an assertion. The failure mode is fluent,
  plausible output — your eyes are not a valid instrument here.

  Additionally, independently: use pypdfium2 to dump raw text runs with
  transform coordinates for page 1, and confirm page rotation and text angle
  are both 90. Report the actual values.

  CHECK C — CITATION + CHECKSUM SURVIVAL (mechanism test)
  In the same docling.json, locate ANY monetary field in this document written
  in the form digits(words) — e.g. a salary or expenditure figure with its
  word form in parentheses in the same cell. IIT Bombay's file has several;
  use whichever one you actually find.
  PASS: it survives as ONE contiguous string, with page_no and a bbox attached.
  FAIL: split across items, reflowed, or missing provenance.

  Report the actual string, page_no and bbox values.

  NOTE — do not search for "3750000(Three Lakh Seventy Five Thousand)" here.
  That specific value belongs to Sandip's 2025 submission, not this document
  (see findings/digits-words-checksum-analysis.md). P1 is scoped to one
  document and fetching a second is forbidden, so the actual conflict this
  project is built around cannot be exercised end to end in this phase — that
  is what P2C's acceptance test is for, and it is already correctly scoped to
  Sandip's document there. P1 only proves the survival mechanism holds; it
  does not need the specific conflicting value to do that.

  RULES
  -----
  - Report each check as PASS or FAIL with the evidence inline. No summaries
    without the underlying values.
  - Do not tune, retry, or work around a failure to make it pass. A FAIL is a
    result, not an obstacle. Report it.
  - If CHECK B fails, do NOT begin writing a replacement parser. Report the
    failure, state the fallback (pypdfium2 geometric parser, porting the
    browser-side approach in notes/methodology.md §2.5), estimate its cost,
    and stop.
  - Tag every claim [VERIFIED] / [ASSUMED].

  STOP CONDITION
  --------------
  End with exactly one of:
    "P1 CLEAR — A/B/C all PASS. Proceed to P2A."
    "P1 FAILED — check(s) X. Architecture decision required. Do not proceed."

  You may not proceed to P2A in the same session regardless of outcome.
```

---

# P2A — Acquisition

- **Entry gate:** `gate/P1-spike.md` ends with `P1 CLEAR`
- **Exit artifact:** `gate/P2A-acquire.md`
- **Forbidden:** any parsing, any Docling, any Postgres, any extraction

```
PHASE 2A — ACQUISITION LAYER ONLY.

Read CLAUDE.md and gate/P1-spike.md.

Build exactly these, and nothing beyond them:

  registry/IN_sources.yaml     source declarations, hand-editable
  acquire/                     Scrapy project
    SourceRegistry             loads YAML -> Request objects
    ManifestPipeline           writes provenance BEFORE anything touches bytes
  raw/sha256/xx/yy/<sha>.ext   immutable content-addressed store
  docs/<sha8>/manifest.json    url, run_id, http_status, etag, last_modified,
                               content_type, fetched_at, source_id, sha256

  HARD SCOPE BOUNDARY
  -------------------
  This layer produces bytes and provenance. It does not know what a PDF is.
  If any file under acquire/ imports a PDF library, an HTML parser, or Docling,
  you have violated P-3. Delete it and start that part again.

  REQUIREMENTS
  ------------
  - A source is DATA, not code. Zero URLs hardcoded in any spider. Adding MIT's
    CDS or the 101-300 rank bands must be a YAML edit and nothing else.
  - The registry supports two entry types, sharing ONE fetch path:
        type: pattern      templated URL + enumerator (the 537 NIRF IDs)
        type: adhoc_url    a single pasted URL
    A pasted link is a registry entry, not a special case in a spider. If
    adhoc_url needs its own code path in acquire/, the abstraction is wrong.
  - Enable AUTOTHROTTLE, JOBDIR (resumable), a real User-Agent with contact
    details. ROBOTSTXT_OBEY: see CLAUDE.md "Recorded decisions" — currently
    False, globally, by explicit dated decision. Do not silently change this
    setting either direction without adding a new dated entry there first.
  - Conditional re-fetch via ETag / If-Modified-Since.
  - P-4: raw/ is write-once. A re-fetch producing different bytes is a NEW
    artifact with a new sha256. No code path may overwrite or delete there.
  - P-12: any institution-ID list must come from a page you actually fetched.
    537 is a floor derived from the top-100 pages, not a verified total. Do not
    hardcode or extrapolate an ID range.
  - Registry entries carry robots_checked_at and terms_reviewed_at fields.
    Leave them null and surface them as [OPEN] — do not fabricate review dates.
  - Acceptance: run twice. Second run fetches nothing new, creates no new files
    under raw/, and writes a manifest row recording the 304 or hash match.

  SELF-VERIFICATION — REQUIRED, NOT OPTIONAL (P-10)
  -------------------------------------------------
  The run script must, before exiting, re-open raw/ and the manifest and print:
  file count, total bytes, distinct sha256 count, http_status distribution,
  and any manifest row whose referenced file is missing. Any mismatch is a
  hard failure that exits non-zero.

  DELIVERABLE — gate/P2A-acquire.md
  ---------------------------------
  The three iteration-1 institutions acquired, with the actual self-verification
  output pasted in. Plus: every assumption you made, tagged [ASSUMED], with what
  would confirm it.

  STOP CONDITION
  --------------
  If you cannot acquire Sandip or MIT (Sandip is unranked — NIRF publishes no
  PDF; see the WordPress /wp-json/wp/v2/media route in the investigation doc),
  report it as a finding. Do not silently skip an institution. Do not proceed
  to P2B in this session.
```

---

# P2B — Classify and convert

- **Entry gate:** `gate/P2A-acquire.md` exists, self-verification passed
- **Exit artifact:** `gate/P2B-convert.md`
- **Forbidden:** extracting values, computing KPIs, touching Postgres

```
PHASE 2B — CLASSIFY AND CONVERT. NO VALUE EXTRACTION.

Read CLAUDE.md and gate/P2A-acquire.md.

Build:

  classify/    per-page: char count, image count, rotation, MIME from MAGIC
               BYTES (never the URL extension — it lies), -> routing label
  convert/     Docling wrapper -> docs/<sha8>/docling.json  (save_as_json only)
  docs/<sha8>/pages/NNN.json     raw (chars, images, rotation) + label
  docs/<sha8>/pages/NNN.png      rendered page, for click-through
  docs/<sha8>/assets/            every extracted image, none skipped

  LABELS — recognise everything, handle only what iteration 1 needs
  ----------------------------------------------------------------
  pdf_digital | pdf_mixed | pdf_scan | html_table | json_api | office_doc | unknown

  "unknown" is a first-class label and a work queue, not a failure. Every
  artifact gets a label and a manifest row even if iteration 1 does nothing
  with it. This is what makes later phases avoid a re-crawl.

  STORE THE RAW PAIR, NOT JUST THE LABEL
  --------------------------------------
  Persist (chars, images) per page alongside the derived label. The ~200-char
  threshold was fitted on ONE document (Sandip Mandatory Disclosure). Storing
  the inputs means re-tuning is a re-query, not a re-crawl. Mark the threshold
  [ASSUMED] in code comments with the fitting provenance.

  P-2 ENFORCEMENT
  ---------------
  Add a test that fails if .export_to_markdown() or .export_to_html() appears
  anywhere in convert/. Markdown is lossy; it drops page and bbox.

  P1 REGRESSION TEST — REQUIRED
  -----------------------------
  Port CHECK B from Phase 1 into the test suite as a permanent assertion, run
  on every conversion of a NIRF document. If Docling's model version changes
  and rotation handling regresses, this must fail loudly. This test is the
  single most important line of defence in the repo.

  SELF-VERIFICATION
  -----------------
  Re-read docs/ and print: artifacts converted, label distribution, pages with
  zero extracted text, artifacts where docling.json is missing or unparseable,
  and the count of doc items lacking page_no or bbox. Non-zero on the last two
  exits non-zero.

  STOP CONDITION
  --------------
  Do not extract a single KPI value in this phase. If you have written code
  that knows what a "median salary" is, you are out of scope.
```

---

# P2C — Extraction and checksum

- **Entry gate:** `gate/P2B-convert.md`, including the P1 regression test passing
- **Exit artifact:** `gate/P2C-extract.md`
- **Forbidden:** touching Postgres, building any UI, any mapping/profile work

```
PHASE 2C — VALUE EXTRACTION AND THE DIGITS/WORDS CHECKSUM.

Read CLAUDE.md, notes/methodology.md §6 in full, and
findings/digits-words-checksum-analysis.md in full. This phase reimplements
work that already failed once in a specific, documented way. Read how it failed
before you write anything.

Build:
  extract/        geometric parsing -> value rows
  values/run={ts}/values.jsonl
  values/run={ts}/checksums.jsonl

  THE WORD PARSER — BUILD IT IN THIS ORDER, NO EXCEPTIONS
  -------------------------------------------------------
  1. Write the self-test FIRST, against the six known-good word/value pairs in
     notes/methodology.md §6.3. It must pass before the parser runs on any
     real document. A parser that has not passed its self-test may not produce
     a single reported result.

  2. Scale absorption is mandatory: a larger scale multiplies everything
     accumulated so far. "One Thousand Four Hundred Sixty Crore" = 1460 crore,
     NOT 1000 + 460 crore. Version 1 of this parser got it wrong and reported
     two false defects.

  3. Idiom abstention is mandatory: a unit 1-9 immediately followed by a tens
     word with no "hundred" between is spoken English ("eight fifty six" = 856).
     ABSTAIN. Do not guess. Do not accuse. This bug nearly shipped — it
     produced a delta of 693 on a nine-figure number, which is exactly the
     shape of a real finding.

  4. Cell reassembly before regex: word forms wrap across two or three lines.
     A line-by-line reader finds "3750000(Three Lakh" with no closing bracket
     and silently reports zero pairs. Cluster by column start, read down,
     break on a large vertical gap. The tuning constants are [ASSUMED] and must
     be commented as fitted to this form's typesetting.

  THREE STATES. NOT TWO. (P-7)
  ----------------------------
    digits == words        -> CONFIRMED
    digits != words        -> CONFLICTING   flag, retain both, never resolve
    words unparseable      -> UNVERIFIED    neither confirm nor accuse

  A two-state implementation turns 18 of 418 word forms into false accusations.
  If your code has an else-branch that treats unparseable as mismatch, it is
  wrong.

  ACCEPTANCE — NON-NEGOTIABLE
  ---------------------------
  On Sandip 2025 Overall, the pipeline must emit a CONFLICTING row for
  3750000 vs "Three Lakh Seventy Five Thousand", retaining BOTH values, with
  page_no and bbox attached, and with no normalized value asserted as correct.

  If your pipeline picks a winner, it has failed, no matter how well-reasoned
  the choice. The judgment belongs in the report, where a human sees the
  reasoning. Not in the data.

  ALSO REQUIRED
  -------------
  - P-8: "-" distinguished from empty and from zero.
  - P-9: period_type on every row.
  - P-6: raw_value string preserved verbatim alongside normalized_value.
  - Every value row carries sha256 + item_id. A value without a citation is
    not a value; reject it at write time.

  P-11 GATE BEFORE REPORTING ANYTHING
  -----------------------------------
  Before any disagreement reaches gate/P2C-extract.md, hand-verify it against
  the raw text runs via pypdfium2 and state that you did, per defect. In the
  original study 4 of the first 9 were the parser's own bugs. Report the
  self-test result first, the disagreements second.

  STOP CONDITION
  --------------
  If the self-test fails on any of the six known pairs, stop. Report it. Do not
  run on real documents.
```

---

# P2E — Profiles and the review queue

- **Entry gate:** `gate/P2C-extract.md`, self-test passed, acceptance row emitted
- **Exit artifact:** `gate/P2E-profiles.md`
- **Forbidden:** Postgres schema work (that is P2D), any auto-accept path

```
PHASE 2E — PROFILES AND THE REVIEW QUEUE.

Read CLAUDE.md (P-13 to P-16 especially) and gate/P2C-extract.md.

Your FIRST task is a proof, not a feature: express the NIRF extraction you
wrote in P2C as declarative profile config, and confirm it produces
byte-identical value rows to the hand-written version. If the config format
cannot express what the parser does, the format is wrong — fix the format,
do not add an escape hatch for "special" fields.

  BUILD
  -----
  profiles/nirf_submission_v2020_2026.yaml
  fingerprint/     match a converted document against known profiles
  discovery/       propose (label, value, page, bbox) -> kpi_code candidates
  review/          the queue: candidate, top-3 suggestions WITH SCORES VISIBLE,
                   actions = confirm / re-assign / mark PARTIAL / no-KPI-home
  profiles/<new>   saving a completed review emits a reusable profile

  PROFILE SHAPE — anchors and geometry, never cell text (P-14)
  ------------------------------------------------------------
  fingerprint: text_anchor + page_rotation + match strictness
  blocks:      anchor (SECTION header) + geometry rule + column roles
  columns:     index, role (period | value | label), kpi_code, unit,
               period_type, checksum rule, caveat tags (P3, P12, P13 from the
               pattern catalogue)

  PARTIAL MATCH — decide it here, do not discover it later
  --------------------------------------------------------
  Known anchor, unknown blocks: apply the known blocks, queue the unknown ones,
  mark the run PROFILE_INCOMPLETE. Output from an incomplete run must never be
  presented as exhaustive. If P0/A8 mandated different behaviour, follow P0.

  ACCEPTANCE TESTS — all five, reported with actual output
  --------------------------------------------------------
  T1  A second ranked NIRF PDF (e.g. IR-O-U-0575).
      EXPECT: fingerprint hit, profile applies, ~29 values with citations,
      28-37 digits/words pairs checked, ZERO human input, seconds.
      This is the test that proves "learn once". If it needs a human touch,
      the profile is over-fitted to IIT Bombay — fix the profile, not the doc.

  T2  MIT Common Data Set HTML.
      EXPECT: no fingerprint match -> discovery mode -> review queue ->
      one new profile us_cds_v2025. Report candidate count, confirmed count,
      no-KPI-home count.

  T3  A random private college HOMEPAGE.
      EXPECT: 0 values, stated explicitly. "No structured self-disclosure
      found. 0 candidate fields."
      If this returns even one value, STOP EVERYTHING. That is P-15 violated
      and it is the rotation failure wearing a new costume. Report it as
      CRITICAL and do not proceed.

  T4  Sandip NAAC SSR, 106 pages with scans spliced in.
      EXPECT: per-page labels; scan pages recorded, counted and EXCLUDED with
      a visible message. Never silently dropped.

  T5  Same URL twice.
      EXPECT: identical sha256, no new raw/ file, new manifest row, no new
      value rows unless content changed.

  FORBIDDEN
  ---------
  - Any auto-accept path, at any threshold (P-13).
  - Any confidence score that is not displayed to the reviewer.
  - Any match on cell text alone (P-14).
  - Silently returning fewer values than a profile promises.

  STOP CONDITION
  --------------
  If T3 returns any value at all, stop and report CRITICAL. Do not proceed to
  P2D. Everything downstream inherits this defect.
```

---

# P2D — Index

- **Entry gate:** `gate/P2E-profiles.md`, all five acceptance tests reported
- **Exit artifact:** `gate/P2D-index.md`

```
PHASE 2D — POSTGRES INDEX.

Read CLAUDE.md, gate/P2C-extract.md and gate/P2E-profiles.md.

  db/schema.sql
    source             (source_id PK, country, institution_code, pattern,
                        entry_type, robots_checked_at, terms_reviewed_at)
    artifact           (sha256 PK, source_id FK, url, run_id, fetched_at,
                        http_status, content_type, n_pages, classify_label,
                        profile_id FK NULL, match_status)
    doc_item           (item_id PK, sha256 FK, page_no, bbox JSONB, item_type,
                        text,
                        tsv tsvector GENERATED ALWAYS AS
                          (to_tsvector('english', text)) STORED,
                        embedding vector(768) NULL)
    profile            (profile_id PK, name, version, fingerprint JSONB,
                        blocks JSONB, created_at, created_by)
    mapping_candidate  (candidate_id PK, sha256 FK, item_id FK, label_text,
                        proposed_kpi_code, score NUMERIC, status,
                        decided_by, decided_at)
    value              (value_id PK, kpi_code, institution_code, period_value,
                        period_type, raw_value TEXT, normalized_value NUMERIC,
                        sha256 FK, item_id FK, profile_id FK, auth_status,
                        run_id, confidence)

    GIN index on doc_item.tsv
    index on value (kpi_code, institution_code, period_value)

  embedding stays NULL and unindexed in iteration 1. It exists now so phase 5
  is a backfill, not a migration. Do not populate it. Do not add the vector
  index yet.

  CONSTRAINTS ENFORCED IN THE DATABASE, NOT IN APPLICATION CODE
  -------------------------------------------------------------
  - value.sha256, value.item_id, value.profile_id NOT NULL. A value without a
    citation and a traceable mapping rule cannot be inserted.
  - No UNIQUE on (kpi_code, institution_code, period_value). That constraint
    would silently enforce the exact overwrite P-5 and pattern P7 forbid.
    Identity is (kpi_code, institution_code, period_value, sha256, run_id).
  - A trigger or revoked privilege preventing UPDATE and DELETE on value.
    Make P-5 structurally impossible, not merely documented.
  - auth_status CHECK constraint limited to CONFIRMED / CONFLICTING /
    UNVERIFIED / NOT_APPLICABLE. No fifth state may be invented at insert time.
  - artifact.match_status CHECK constraint: MATCH / PARTIAL / NONE. Any export
    touching a PARTIAL artifact is flagged PROFILE_INCOMPLETE.
  - mapping_candidate.status NOT NULL with no default. A candidate cannot exist
    in an undecided-but-applied state.

  ACCEPTANCE QUERIES — must run and return correct results
  --------------------------------------------------------
  Q1. Given a kpi_code + institution, return the value AND its page_no + bbox
      + source URL in one query. This is the president's click-through.
  Q2. Keyword search across doc_item returning artifact, page, and source.
  Q3. Every CONFLICTING row with both raw and normalized values and both
      citations.
  Q4. Re-run the whole pipeline. Confirm row counts INCREASED and no prior row
      changed. Prove it with a checksum over the pre-existing rows.
  Q5. Every value traced back to the profile_id that produced it, and every
      artifact whose match_status is PARTIAL listed with its unmapped blocks.

  SELF-VERIFICATION
  -----------------
  Loader re-reads and prints: rows per table, values lacking a citation (must
  be 0), values lacking a profile_id (must be 0), auth_status distribution,
  match_status distribution, orphaned FKs (must be 0). Exit non-zero on any
  violation.
```

---

# P3 — Diagram

- **Entry gate:** `gate/P2D-index.md`
- **Exit artifact:** `docs/architecture.md`

```
PHASE 3 — DIAGRAM WHAT WAS BUILT, NOT WHAT WAS PLANNED.

Read CLAUDE.md and every gate/ file. Invoke the `graphify` skill.

Produce docs/architecture.md containing, diagrams BEFORE prose:

  D1. End-to-end pipeline: fetch -> store -> classify -> convert -> extract
      -> map -> index. Mark each stage IMMUTABLE or REGENERABLE. Mark every
      point where a silent failure is possible and name the guard that catches
      it.

  D2. The citation path, concretely:
      value -> item_id -> page_no + bbox -> rendered page PNG -> highlighted
      rectangle -> source URL. This is the president demo. It must be legible
      to a non-technical reader.

  D3. The three-state checksum decision:
      CONFIRMED / CONFLICTING / UNVERIFIED, with the abstain branch given
      equal visual weight to the other two. It is the state most likely to be
      dropped by a future maintainer.

  D4. The mapping flow: paste URL -> fetch -> classify -> convert ->
      fingerprint -> {MATCH: apply profile, zero humans} |
      {NONE: discovery -> review queue -> new profile} |
      {PARTIAL: apply known, queue unknown, flag PROFILE_INCOMPLETE}.

  D5. The phase boundary: what iteration 1 handles vs what it RECOGNISES AND
      RECORDS but does not handle (scans, DOCX, unknown). Show that the second
      set needs no re-crawl.

  RULES
  -----
  - Choose format by fit. Do not default to Mermaid.
  - Diagram the code as it actually exists. If a diagram and the code disagree,
    the code is right and you have found a bug — report it, do not draw the
    intention.
  - Every diagram is followed by prose, never preceded by it.
```

---

# P4 — Thermonuclear review

- **Entry gate:** `docs/architecture.md`
- **Exit artifact:** `gate/P4-review.md`

```
PHASE 4 — THERMONUCLEAR REVIEW. ASSUME IT IS BROKEN.

Read CLAUDE.md and every gate/ file. Invoke the
`thermonuclear code quality review` skill on the entire repository.

Your prior is that this code produces confidently wrong output. Find where.

  WEIGHT THE REVIEW IN THIS ORDER. Do not treat all findings as equal.
  --------------------------------------------------------------------
  1. SILENT WRONGNESS. Any path producing incorrect output without raising.
     This outranks everything. A crash is a good outcome in this project; a
     plausible wrong number shown to a president is the failure we exist to
     prevent. Enumerate exhaustively.

  2. P1 / rotation. Every place coordinates are read. Is it VERIFIED against a
     known value, or assumed? Is the regression test actually running?

  3. The checksum. Is it genuinely three-state at every branch? Find any path
     where UNVERIFIED collapses into CONFLICTING or CONFIRMED.

  4. AUTO-ACCEPT PATHS. Find any code path where a proposed mapping becomes a
     stored value without a recorded human decision. Find any threshold
     constant that decides a mapping. Find any match on label text alone.
     Find any path where an unrecognised document yields a non-empty value set.
     Each is CRITICAL by default (P-13, P-14, P-15).

  5. P-10. Every script re-reads its own output. Find any that does not.

  6. Immutability. Any path that can overwrite raw/, mutate a value row, or
     collide two artifacts onto one hash.

  7. (Retired — was a licence check for client work; not applicable here. See
     CLAUDE.md P-1.)

  8. Threshold and constant provenance. Every fitted constant (the ~200-char
     classifier threshold, the column-clustering gap, the vertical-break
     distance, any mapping score cutoff) must be commented with what it was
     fitted on and marked [ASSUMED]. An unmarked magic number is a finding.

  RULES
  -----
  - No praise. Findings only. If something is genuinely correct, one line.
  - Severity: CRITICAL / HIGH / MEDIUM / LOW. Anything in category 1 or 4 is
    CRITICAL by default; justify any downgrade explicitly.
  - Every finding: file, line, what breaks, what the operator would see, fix.
  - Do not fix anything in this phase. Report only. Fixing while reviewing
    ends the review early and hides the rest.
  - If you find a finding that invalidates a claim in an earlier gate/ file,
    say so explicitly and name the file. Earlier sign-off is not protection.

  STOP CONDITION
  --------------
  End with a count by severity and one line:
    "SHIP" or "DO NOT SHIP — N critical".
  Do not soften this. The demo goes to a university president.
```

---

## Adjusting for your skill set

Three skills are invoked by name: `grillme` (P0), `graphify` (P3), and
`thermonuclear code quality review` (P4). If those take arguments or expect
different trigger phrasing in your installation, edit only those invocation
lines. Everything else is skill-agnostic.
