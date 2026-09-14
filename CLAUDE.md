# Project laws

These apply to every session, every phase, every file. They are not guidance.
They were derived from an investigation that has already overturned several
plan assumptions. Do not relax one because it is inconvenient in the moment.

---

## Mandatory reading, every new session

1. `findings/iteration-1-source-investigation.md`
2. `findings/digits-words-checksum-analysis.md`
3. `findings/nirf-coverage-of-229-kpis.md`
4. `notes/methodology.md` — §9 pattern catalogue P1–P22
5. `notes/v2-spec-disagreements.md`
6. `notes/dictionary-defect-verification.md`

Do not skim. If a path above does not resolve, stop and say so — do not proceed
on partial context.

---

## What this project is

A pipeline that acquires Indian university NIRF submission PDFs and US Common
Data Set HTML, stores them immutably, converts them to a structured form that
retains page and bounding-box provenance, and indexes them so every extracted
number traces back to the exact rectangle on the exact page of the exact file.

**Iteration 1 scope:** 3 institutions (Sandip SITRC, IIT Bombay, MIT), 2 years.

**The deliverable is a demo for a university president.** Its persuasive core is
one verifiable error: Sandip's 2025 submission has a cell where the digits read
`3750000` and the words read `Three Lakh Seventy Five Thousand` — a 10× gap that
a digits-only parser reports as Sandip beating IIT Bombay on graduate salary.
The pipeline must catch it, flag it, and never auto-resolve it.

---

## Stack — settled, not open for re-litigation

| Layer | Tool | Licence |
|---|---|---|
| Acquisition | Scrapy | BSD-3 |
| Conversion | Docling (`save_as_json()` only) | MIT |
| Coordinate checks | pypdfium2 | Apache-2.0 |
| Index | PostgreSQL 17 + pgvector | permissive |
| Config | YAML, hand-edited | — |

Rejected: Crawl4AI, Firecrawl, and every "LLM-ready Markdown" crawler. Their PDF
path is naive and Markdown export discards page and bbox, which destroys the
evidence chain this project exists to provide.

---

## The defining risk: silent failure

Every NIRF submission is `/Rotate 90` with a 90-degree text matrix. Read naively,
rows from adjacent tables interleave into plausible-looking garbage **and no
error is raised**. The output is fluent English and correctly-formatted real
numbers with the label-to-value association destroyed — and association is
invisible in output.

This is the shape of every failure that matters here.

- When choosing between two designs, prefer the one that fails loudly.
- When reviewing, weight silent-wrong far above crash-loud.
- A crash is a good outcome in this project. A plausible wrong number shown to a
  president is the failure we exist to prevent.

Any code path that reads PDF text coordinates must honour page rotation and must
be verified against a known value end to end. Verified, not assumed.

---

## Recorded decisions

Changes to the rules in this file are dated and attributed here, not made
silently. If a rule in this file conflicts with something below, this section
wins — it reflects what was actually decided, most recent first.

**2026-09-14 — `ROBOTSTXT_OBEY` set to `False`, globally, in `acquire/settings.py`.**
Decision by the project owner. Context: Sandip's site disallows `*.pdf` under
a blanket `User-agent: *` rule that also covers this project's own legitimate
target files (see `gate/P2A-acquire.md` §2 for the original finding). This is
a college project, showcase scope only, not run against production
institutions beyond the three in iteration-1 scope — that context is why a
global override was accepted here over a per-source registry field
(`robots_override` per source, logged and scoped individually), which remains
the correct design if this project ever crawls beyond its current three
institutions. **If this codebase is ever repurposed for real, larger-scale
crawling, revisit this decision before relying on it** — a global bypass
against sites this project doesn't control is not something to carry forward
by default.

**2026-09-14 — P-1 retired.** Was an AGPL/PyMuPDF prohibition, written for
client-work licensing exposure. This is a college project, not a client
deliverable, so it does not apply. PyMuPDF/fitz may be used freely. Left as a
retired number rather than reused or renumbered, so P-2 through P-16 keep
their existing references elsewhere unchanged.

---

## Absolute prohibitions

**Licensing and libraries**

- **P-1 — retired.** This was a client-work licensing constraint (no AGPL
  packages, specifically PyMuPDF/fitz). This is a college project, not a
  client deliverable, so it does not apply. PyMuPDF/fitz may be used freely if
  it's ever a better fit than pypdfium2. The number is left retired rather than
  reused, so P-2 through P-16 below keep their existing references in
  PROMPTS.md and INSTRUCTIONS.md unchanged.
- **P-2** Never write Docling output to Markdown or HTML. Those exports are lossy
  — they drop pages and bounding boxes. `save_as_json()` only. If you find
  yourself calling `.export_to_markdown()`, you are wrong.

**Layer boundaries**

- **P-3** Never parse inside the acquisition layer. Scrapy returns bytes and
  headers. Any parsing, sniffing, decoding or interpretation in a spider is a
  defect.

**Immutability**

- **P-4** Never overwrite or delete anything under `raw/`. A re-fetch producing
  different bytes is a **new** artifact with a new sha256.
- **P-5** Never UPDATE a value row. Always INSERT with a new `run_id`.
- **P-6** Never store only the normalized value. The string
  `3750000(Three Lakh Seventy Five Thousand)` is the sole evidence for the error.
  Raw and normalized are stored side by side, always.

**Values and validation**

- **P-7** Never auto-resolve a digits/words conflict in either direction. Neither
  side is reliably right. Flag, retain both, stop.
- **P-8** Never treat `-` as zero. Distinguish empty / dash / zero at parse time.
- **P-9** Never store year as a bare integer. `period_type` travels with
  `period_value` (academic year / calendar year / validity window).

**Process**

- **P-10** Never claim a write succeeded without reading it back. openpyxl's
  `cell(value=None)` is a silent no-op that nearly shipped a false changelog.
- **P-11** Never report a defect you have not hand-verified against raw source.
  In the checksum study, 4 of the first 9 "defects" were the parser's own bugs,
  and 2 were indistinguishable from real findings by shape.
- **P-12** Never use a rank-band or ID list you have not fetched. 537 is a floor
  derived from the top-100 pages, not a verified total.

**Mapping**

- **P-13** Never auto-accept a proposed `label → kpi_code` mapping, at any
  confidence score. The token-overlap join scored `A25 Dropout rate` at exactly
  0.333 against its correct target and silently missed it; moving the threshold
  0.34 → 0.30 changed the match count 116 → 164. That number is a property of the
  threshold, not of the documents. The review queue is load-bearing, not a
  convenience to strip out later for speed.
- **P-14** Never map a field by label text alone. Header text varies between
  institutions for the same field in the same form year (P4 in the pattern
  catalogue). Anchor on the **section** header, locate by **geometry**, use label
  text only to **verify**. A profile keyed on cell text is a defect even when it
  currently passes.
- **P-15** A document matching no profile returns **zero** values and says so
  loudly. Never return a partial or best-effort set of plausible numbers from an
  unrecognised page. This is the rotation failure in a new costume: fluent,
  confident, wrong. Zero-with-an-explanation is the correct output.
- **P-16** Never discard an extracted field because it has no KPI code. 39 of the
  72 NIRF concepts have no home in the 229. They are stored as `doc_item` rows
  with full citations, searchable, awaiting a dictionary that grows.

---

## Epistemic discipline

Tag every claim you make:

| Tag | Meaning |
|---|---|
| `[VERIFIED]` | You ran it and read the output |
| `[CARRIED-FORWARD]` | Established in an earlier phase, cite the gate file |
| `[ASSUMED]` | Plausible, not checked. Say what would check it. |
| `[OPEN]` | Unknown. Say what would settle it. |

An untagged claim is a defect. Do not soften findings. Do not manufacture
confidence the evidence does not support. If evidence contradicts something in a
prompt or in this file, say so and stop.

---

## Style

- Diagrams before prose in every document. Choose format by fit — Mermaid, ASCII,
  or table. **Do not default to Mermaid.**
- Every script re-reads its own output and prints distributions before exiting.
- Every fitted constant (thresholds, gap distances, bucket sizes) carries a
  comment stating what it was fitted on, and is marked `[ASSUMED]`. An unmarked
  magic number is a defect.
