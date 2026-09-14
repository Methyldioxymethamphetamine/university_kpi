iteration-1-source-investigation.md

`# Iteration 1 — Source Investigation Findings`

`**Date:** 13 September 2026`

`**Scope:** IIT Bombay, Sandip (SITRC), MIT — acquisition surface, PDF structure, real metric yield, per-document mapping cost`

`**Status of the blocker it was meant to clear:** cleared, with a better answer than expected`

`---`

`## 1. The headline`

`The plan assumed the big unknown was *"are the NIRF PDFs scans?"* — because if they were, the whole approach changed.`

`They are not. Nothing found in this investigation needs OCR. But a different problem was hiding underneath, and it is the one that would have silently corrupted the dataset.`

` ``` `

`        WHAT WE FEARED                    WHAT IS ACTUALLY THERE`

`   ┌──────────────────────────┐     ┌──────────────────────────────┐`

`   │  Scanned image PDFs      │     │  Born-digital, 100% text     │`

`   │  → OCR pipeline          │     │  → zero OCR needed           │`

`   │  → 70-90% accuracy       │     │  → 100% character accuracy   │`

`   │  → manual QA on every    │     │                              │`

`   │    number                │     │  BUT every page is /Rotate90 │`

`   └──────────────────────────┘     │  with a 90° text matrix.     │`

`                                    │  Read naively, rows and      │`

`          RISK: visible             │  columns interleave into     │`

`          You know OCR is           │  plausible-looking garbage.  │`

`          lossy, so you check.      │                              │`

`                                    │  RISK: INVISIBLE             │`

`                                    │  It extracts "successfully"  │`

`                                    │  and returns wrong numbers.  │`

`                                    └──────────────────────────────┘`

` ``` `

``Every NIRF submission PDF is landscape with `/Rotate 90`, and each text run carries a 90-degree transform. The axis that looks like "x" in the file is the page's vertical axis on screen. Cluster on the wrong one — which is what a default `page.get_text()` call does — and you get output like this, taken from the real IIT Bombay 2025 file:``

` ``` `

`1430 78 410`

`No. of students No. of students`

`2018-19 selected for Higher selected for Higher`

`83 154 259`

` ``` `

`Numbers with no labels, labels with no numbers, and two adjacent tables merged into single lines. Nothing errors. Nothing looks obviously broken until you check a value by hand.`

`Honouring the rotation, the same page reads:`

` ``` `

`Academic Year | 2023-24 | 2022-23 | 2021-22 | 2020-21 | 2019-20 | 2018-19`

`UG [4 Years Program(s)] | 1161 | 1059 | 1039 | 1030 | - | -`

`UG [5 Years Program(s)] | 80 | 182 | 202 | 211 | 178 | -`

`PG [2 Year Program(s)] | 1558 | 1543 | - | - | - | -`

` ``` `

``Clean, aligned, fully recoverable. **The fix is roughly ten lines of code. The cost of not knowing is a dataset that is confidently wrong.** This belongs in `CLAUDE.md` as a prohibition on day one, because a code generator writing a PDF extractor will not honour page rotation by default.``

`---`

`## 2. What the documents actually are`

`Measured directly, not estimated:`

`| Document | Pages | Text chars | Images | Rotation | Text layer | OCR needed |`

`|---|---|---|---|---|---|---|`

`| IITB 2025 Overall (NIRF portal) | 4 | 9,741 | 0 | 90° | full | no |`

`| IITB 2024 Overall | 4 | 8,965 | 0 | 90° | full | no |`

`| IITB 2023 Overall | 4 | 8,382 | 0 | 90° | full | no |`

`| IITB 2020 Overall | 3 | 7,043 | 0 | 90° | full | no |`

`| IITB 2025 Engineering | 3 | 7,807 | 0 | 90° | full | no |`

`| **Sandip 2026 Overall (own site)** | 10 | 20,292 | 0 | 90° | full | no |`

`| **Sandip 2025 Overall (own site)** | 13 | 25,738 | 0 | 90° | full | no |`

`| **Sandip 2024 Overall (own site)** | 10 | 20,684 | 0 | 90° | full | no |`

`| Sandip AICTE Mandatory Disclosure 2020-21 | 34 | 47,395 | 16 | 0° | partial | pages 22–25 only |`

`| Sandip AICTE Mandatory Disclosure 2024-25 | 25 | 33,774 | 16 | 0° | partial | some |`

`| Sandip NAAC SSR Cycle 1 | 106 | 186,350 | 106 | 0° | mostly | some |`

`Two things fall out of this table.`

`**The NIRF form is stable across six years and across institution types.** 2020 through 2026, IIT Bombay and Sandip, Overall and Engineering categories — identical structure, identical rotation, zero images. One parser handles all of them. This is the strongest de-risking result of the investigation: the India side is not thirty bespoke scrapers, it is one form parsed many times.`

`**The AICTE/NAAC documents are the mixed-mode case.** Sandip's Mandatory Disclosure is 34 pages of extractable text with four scanned pages spliced in at positions 22–25 (96, 88, 76 and 407 characters against 2 to 4 images each — almost certainly photographed approval letters). The per-page text-to-image ratio is a cheap, reliable detector: any page under ~200 characters with images present goes to the OCR path, everything else does not. That is a concrete pipeline rule, not a guess.`

`---`

`## 3. The acquisition surface is much better than the seed list suggested`

`The seed list was organised one page per KPI domain and, as noted earlier, missed the highest-value documents entirely. Three discoveries change the crawling strategy.`

`### 3.1 NIRF publishes for every ranked institution, in one place`

`` `nirfindia.org` hosts the submission PDFs at a fully predictable path: ``

` ``` `

`https://www.nirfindia.org/nirfpdfcdn/{year}/pdf/{Category}/{InstitutionID}.pdf`

`                                                            └── IR-O-U-0306  (IIT Bombay, Overall, University)`

`                                                                IR-O-C-41520 (Sandip SITRC, Overall, College)`

` ``` `

`Counting only the top-100 list of each category for 2025: **601 PDF links, 537 unique institution IDs.** Each one is a 3-to-13 page born-digital form in the same layout. There is no crawling problem here at all — there is a list of URLs and a parser.`

`### 3.2 Institutions publish the *unabridged* submission on their own sites`

`This one inverts a planning assumption.`

``Sandip is a NIRF **participant but not ranked**, so `nirfindia.org` publishes no PDF for them. Their own site does — for 2026, 2025, 2024 and 2021, across Overall, Engineering, Management and SDG categories.``

`And their copy is **longer and richer than IIT Bombay's published copy**:`

`| | IIT Bombay 2025 Overall (NIRF portal) | Sandip 2025 Overall (own site) |`

`|---|---|---|`

`| Pages | 4 | 13 |`

`| Institution-level data | yes | yes |`

`| IPR / patents block | **absent** | present |`

`| NAAC accreditation block | **absent** | present (CGPA 3.11) |`

`| PG medical block | absent | present |`

``| Faculty information | one number: `833` | **full 190-row annexure** |``

`| Distinct metric concepts | 56 | **72** |`

`The demo narrative planned around *"Sandip will show more blanks than IIT Bombay, and that's the strategic finding"* is **wrong on the facts, and the true version is better.** Sandip publishes more of its own data than IIT Bombay does, because NIRF abridges what it republishes while the institution posts the raw submission. The honest framing for the president is: *"our own file is more complete than the public file for IIT Bombay — the gap isn't that we publish less, it's that nobody has ever put the two side by side."*`

`### 3.3 WordPress sites hand you a complete document index for free`

``Sandip's site runs WordPress. That means `/wp-json/wp/v2/media?search=nirf` returns a JSON list of every matching uploaded file. No crawling, no link-following, no frontier management — one request returns the whole document inventory. That single call surfaced 28 NIRF-related files including four years of submissions that are not linked from any obvious navigation page.``

``This is worth a dedicated check in the source registry: for each institution, test for `/wp-json/wp/v2/media` before writing a crawler. A large share of Indian private-college sites are WordPress.``

`### 3.4 MIT's equivalent is HTML, not PDF`

`` `ir.mit.edu` publishes the **Common Data Set** as HTML tables, sections A through J, with prior years in the same format. CDS is a standardised cross-institution form used by most US universities — the structural analogue of NIRF. So both sides of the international comparison have a standardised self-disclosure instrument, and the harder-to-parse side is the Indian one. ``

` ``` `

`INDIA                                    UNITED STATES`

`─────                                    ─────────────`

`NIRF submission PDF                      Common Data Set`

`  · 3–13 pages                             · HTML tables`

`  · /Rotate 90, needs geometry             · sections A–J`

`  · one form, ~537 ranked institutions     · one form, most US universities`

`  · academic-year keyed                    · academic-year keyed`

`        │                                        │`

`        └──────────────┬─────────────────────────┘`

`                       ▼`

`          same normalisation target`

`       (university, kpi_code, year, source_id)`

` ``` `

`Section 21's country-agnostic design — KPI dictionary stays neutral, regulators resolve through per-country source registries — is vindicated by this. Adding the US is genuinely a config change: a new source registry pointing at CDS, mapping into the same dictionary.`

`---`

`## 4. Real metric yield, measured`

`The working estimate was 40–60 KPIs per NIRF PDF, made without opening one. The measured figure:`

`| Source | Distinct metric concepts | Atomic values (concept × year × programme) |`

`|---|---|---|`

`| IITB 2025 Overall | 56 | ~191 |`

`| Sandip 2025 Overall | 72 | ~165 institution-level + 1,900 faculty-annexure cells |`

`**72 distinct concepts, not 40–60.** The estimate was conservative. Domain coverage from a single document:`

`| Domain | Concepts | Notable |`

`|---|---|---|`

`| Financial | 13 | capex by 5 heads, opex by 3 heads, fee reimbursement by 4 sources |`

`| Student | 12 | gender, domicile, international, economic and social category |`

`| Academic | 11 | intake, on-time graduation, PhD output, EDP/MDP |`

`| Faculty | 11 | headcount plus 8 derivable from the annexure |`

`| Research | 8 | sponsored projects, consultancy, patents published/granted |`

`| Sustainability | 6 | genuinely discriminating — see below |`

`| Accreditation | 4 | NAAC validity window and CGPA |`

`| Placement | 3 | placed, median salary, higher studies |`

`| Infrastructure | 3 | accessibility provisions |`

`| Governance | 1 | grievance redressal cell |`

``Full per-metric detail is in `metric-inventory.csv`.``

`The sustainability block deserves a note because it is the one place the two institutions visibly diverge on a question neither can game: recycling infrastructure. IIT Bombay answers *"Comprehensive infrastructure (bins, awareness, collection systems)"*; Sandip answers *"No recycling infrastructure on campus"*. That is a real, self-declared, directly comparable gap — exactly the kind of finding the president is being asked to look at.`

`### Faculty annexure, extracted and verified`

`The 190-row Sandip faculty annexure parsed completely: serial numbers 1 through 190, no gaps, no duplicates. Derived values:`

`| Derived KPI | Value |`

`|---|---|`

`| Faculty rows | 190 |`

`| Gender split | 113 male / 77 female (40.5% female) |`

`| Designation mix | 161 Assistant / 20 Associate / 9 Professor |`

`| Share holding PhD | 25.3% (48 of 190) |`

`| Average age | 37.4 years |`

`| Average experience | 124.7 months (~10.4 years) |`

`| Marked "currently working: No" | 48 (25.3%) |`

``That last row is a **faculty turnover signal** — one of the KPIs whose `Benchmark_Direction` is genuinely "Lower", and one of the eleven the Excel has shifted into the wrong column. It is derivable here because the annexure carries a Leaving Date per person.``

`Two honest caveats. The PhD share and the not-currently-working share are both 48/190 — that is coincidence, not a parsing bug, but it is the kind of coincidence worth re-checking on another institution before anyone quotes it. And the denominator for "share holding PhD" is a modelling decision, not an extraction: all 190 rows, or only the 142 still employed? The dictionary has to say.`

`---`

`## 5. What one physical document costs to map`

``This is the number the engagement's shape depends on. Ten values were mapped end to end, with evidence spans; the full record is in `mapping-sample.csv`.``

`**Machine cost is negligible.** Fetch, parse and full text extraction of the 4-page IIT Bombay file: **572 milliseconds**, including network. The 13-page Sandip file with its 190-row annexure: comparable. Extraction is not the bottleneck and never will be.`

`**The cost is entirely in the mapping decisions**, and they concentrate in a small number of recurring patterns. Of ten values mapped, six required a judgement that a generic extractor would get wrong:`

`| # | Pattern | Why it costs time | Recurs? |`

`|---|---|---|---|`

`| 2 | Year not printed on the block | "Current" tables carry no year; the year comes from the document title | every document, every "current" block |`

`| 3 | Column identified only by position | Headers wrap across five physical lines; header text can't be matched to a column without geometry | every wide table |`

`| 4 | Digits and words disagree | See below — the important one | rare but decisive |`

`| 5 | Three different year keys in one physical row | Placement rows carry intake year, lateral-entry year and graduation year side by side | every placement block |`

`| 8 | Calendar year vs academic year | The IPR block is calendar-keyed; everything else is academic-keyed | every document with IPR |`

`| 10 | Derived, not printed | Free-text qualifications; any taxonomy is a mapping decision | every annexure |`

`Each pattern is a **one-time cost per pattern, then near-zero per document**, because the form is stable across years and institutions. That is the finding that decides the schedule. The work is not 137 sources × N hours. It is roughly a dozen structural patterns solved once, plus a thin per-institution tail for the non-NIRF documents.`

`**Realistic revised shape:** the NIRF-derived core — 537 ranked institutions, 72 concepts, six years — is closer to two to three weeks of careful work than to months, because it is one parser. The months go into the long tail: institutions with no NIRF submission, the AICTE/NAAC documents with their scanned pages and per-branch rather than institution-level granularity, and the per-country registries. The earlier ~60 person-day figure still looks right in total, but it is now clear that it is **back-loaded into the messy tail, not the standardised core** — which means a credible, populated, multi-institution demo is available very early.`

`---`

`## 6. The finding that justifies the entire evidence chain`

`Sandip's own NIRF 2025 submission, page 1, UG 4-year placement block, 2021-22:`

` ``` `

`Median salary of placed graduates:   3750000(Three Lakh Seventy Five Thousand)`

`                                     └──┬───┘└──────────────┬──────────────────┘`

`                                     37,50,000          3,75,000`

`                                     thirty-seven        three lakh`

`                                     lakh fifty          seventy-five`

`                                     thousand            thousand`

`                              THESE DIFFER BY A FACTOR OF 10`

` ``` `

`The two adjacent years in the same table read ₹5.2 lakh and ₹5.5 lakh. So the words are right and the digits carry a stray zero.`

`A digits-only parser — which is what every reasonable person writes first — reports **Sandip's median UG salary at ₹37.5 lakh against IIT Bombay's ₹19.6 lakh**, and produces a benchmarking table in which Sandip beats IIT Bombay on graduate salary by nearly two to one.`

`That table would be shown to a college president. It would be wrong. And nothing in the pipeline would flag it, because 3750000 is a perfectly well-formed number sitting in exactly the right cell.`

`This is the demo. Not a claim about rigour — a live example, in the president's own institution's file, of the number a careless system reports and the number the evidence chain catches. It answers *"why can't you just scrape it?"* in one screen, without a single technical term.`

`The defence is already in the document: NIRF's form requires the amount in both digits and words, so every financial field carries its own checksum. The cross-check must be typo-tolerant, though — Sandip's 2021-22 sponsored research words read *"Twenty Lakh Thirty Eighty Thousand Nine Hundred"* against digits of 2,038,900, where the digits are correct and the words contain a typo. So the rule is: **disagreement raises a flag for human review, it never auto-resolves in either direction.**`

`---`

`## 7. Schema consequences`

`Four things the investigation confirmed or changed.`

``**`KPI_Code` as primary key — confirmed, unchanged.**``

``**Identity as `(university_code, kpi_code, year, source_id)` — now demonstrated, not just argued.** Faculty headcount for Sandip 2025 arrives two ways from two sources: IIT Bombay's file states a total (`833`) with no annexure; Sandip's file has a 190-row annexure and no stated total. Same KPI, different derivation, different confidence. Without `source_id` in the key, one silently overwrites the other and there is no way to show the president where a number came from.``

``**Never UPDATE, always INSERT with a new `run_id` — confirmed.** Sandip republishes the same document path across years, and the 2024 and 2026 files differ in page count from 2025. Values will move. History has to survive.``

``**Raw and normalized side by side — now non-negotiable, and for a new reason.** The raw cell `3750000(Three Lakh Seventy Five Thousand)` is the only thing that lets anyone adjudicate the conflict. If the pipeline stores only `3750000`, the evidence for the error is gone.``

`One addition the investigation forces:`

``**`year` cannot be a bare integer.** A single NIRF document contains three different time semantics — academic year (most blocks), calendar year (IPR/patents), and a validity window with explicit dates (NAAC accreditation). Storing all three as an integer silently mixes periods. The value rows need a period type alongside the period value.``

`---`

`## 8. What is still unknown`

`The three source documents are not in the project folder, so two things could not be done:`

``1. **The 229 KPI codes could not be matched.** The 72 concepts found are real and inventoried, but which of them correspond to which `KPI_Code`, and how many of the 229 a NIRF submission can populate, needs the dictionary xlsx. Dropping it into the folder makes this a short follow-up.``

``2. **The `Benchmark_Direction` corruption could not be re-verified against the live file** for the same reason.``

`Two things worth checking before iteration 1 is scoped finally:`

`- **Rank-band institutions (101–300).** Those list pages use a different filename convention than the ones probed here, so the 537 figure is a floor, not a ceiling.`

`- **Whether MIT's CDS HTML is stable across years** or is re-templated annually. The 2025-26 page was confirmed; earlier years were listed but not opened.`

`---`

`## 9. Recommended change to the iteration 1 plan`

`| | Original plan | Revised on evidence |`

`|---|---|---|`

`| Universities | Sandip, IIT Bombay, MIT | unchanged — the choice holds up well |`

`| Primary source | scrape institutional web pages | **NIRF submission PDFs + MIT CDS**; web pages are the fallback, not the plan |`

`| Expected yield | 120–180 values | **~190 values per NIRF document per institution**, so 400+ is realistic across three institutions and two years |`

`| Sandip's role | "shows more blanks — strategic finding" | **richer than IIT Bombay's public file** — reframe the narrative |`

``| Biggest technical risk | scanned PDFs needing OCR | **page rotation silently scrambling rows** — solved, must be locked into `CLAUDE.md` |``

`| Demo centrepiece | click a number, source page opens | **the ₹37.5 lakh vs ₹3.75 lakh discrepancy**, live, in our own file |`

`| Crawling strategy | per-domain page crawl | predictable URL pattern + WordPress media API; crawler only for the tail |`

`The evidence chain stays non-negotiable and the thin-vertical-slice approach stays right. Nothing in the investigation argues against either — the salary discrepancy is the strongest argument for both that the engagement could have hoped for, and it came out of the client's own institution's file on the first document opened.`

`---`

`## Sources`

`- [IIT Bombay NIRF submissions index](https://www.iitb.ac.in/national-institutional-ranking-framework-nirf) — 9 years × 5 categories`

`- [IIT Bombay 2025 Overall submission (NIRF portal)](https://www.nirfindia.org/nirfpdfcdn/2025/pdf/Overall/IR-O-U-0306.pdf)`

`- [NIRF India Rankings 2025 — Overall](https://www.nirfindia.org/Rankings/2025/OverallRanking.html)`

`- [Sandip SITRC 2025 Overall NIRF submission](https://sitrc.sandipfoundation.org/wp-content/uploads/2025/02/NIRF-Report-2025_Overall.pdf)`

`- [Sandip SITRC AICTE Mandatory Disclosure 2020-21](https://sitrc.sandipfoundation.org/wp-content/uploads/2021/11/Mandatory-Disclosure-2020-21.pdf)`

`- [Sandip SITRC NAAC SSR Cycle 1](https://sitrc.sandipfoundation.org/wp-content/uploads/2023/10/NAAC_SSR_SITRC_Cycle-1.pdf)`

`- [MIT Institutional Research](https://ir.mit.edu/) and [MIT Common Data Set 2025-26](https://ir.mit.edu/projects/2025-26-common-data-set/)`