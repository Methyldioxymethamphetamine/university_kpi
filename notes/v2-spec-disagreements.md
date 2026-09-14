v2-spec-disagreements.md

# Where the evidence disagrees with `requirement-spec-v2-phase1.md`

v2 holds up well. Its domain counts, KPI totals, uniqueness claims and every "✅ Verified" marker except two were re-checked against the actual files and confirmed. What follows is only the disagreements and the gaps — six items, three of which change something that matters.

| **#v2 saysEvidence saysSeverity** |                                                                                 |                                                                                            |                                       |
| --------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------- |
| 1                                 | §3.3 — "The 11 'Lower' values sit one column left, in `Formula`"                | There are **10**, and `Formula` is **three** columns left, and it is not a shift           | Medium                                |
| 2                                 | §3.7 — "`Formula` holds 5 real formulas, 11 benchmark directions, 3 data types" | **4** formulas, **10** directions, **3** data types                                        | Low, but the arithmetic doesn't close |
| 3                                 | §3.3 — implies restoring the 11 fixes `Benchmark_Direction`                     | **8 more KPIs are inverted and were never marked anywhere**, including all three rank KPIs | **High**                              |
| 4                                 | §3.5 — "Replace with per-subparameter source mapping from Doc 3"                | Doc 3 routes **93%** of everything to "the university website"                             | **High**                              |
| 5                                 | §7/§8 — extraction ladder branches on "text layer present?"                     | Text layer present is **not sufficient**; page rotation silently scrambles rows            | **High**                              |
| 6                                 | §10.2 — cross-field validation examples                                         | Misses the digits/words checksum, which covers \~30 fields per document                    | Medium                                |

## 1 & 2. The `Formula` column arithmetic

v2 §3 correction 7 says `Formula` holds *"5 real formulas, 11 benchmark directions, 3 data types."* That totals 19, but `Formula` has 17 non-empty cells. The actual split:

| **v2actual**         |    |                                                                                                        |
| -------------------- | -- | ------------------------------------------------------------------------------------------------------ |
| Real formulas        | 5  | **4** — `Students/FTE faculty`, `Publications/FTE faculty`, `Citations/FTE faculty`, `Faculty/Student` |
| Benchmark directions | 11 | **10** — `Lower` ×9, `Lower absolute variance` ×1                                                      |
| Data types           | 3  | 3                                                                                                      |
| **Total**            | 19 | **17** ✓                                                                                               |

And §3 correction 3's *"one column left"* is wrong in a way that changes the repair. The column order is `Unit · Data_Type · Formula · Scraping_Keywords · Primary_Source · Benchmark_Direction` — `Formula` is three columns left of `Benchmark_Direction`, and on all ten affected rows `Unit` and `Data_Type` are correct. Nothing slid sideways; the value was written to the wrong column. Fix it cell by cell, not by shifting rows.

Separately, the three `integer` values are a **different defect on different rows** (A01–A03): an inserted label at `Unit` pushed `Unit → Data_Type → Formula`, corrupting nine cells, not three. v2 treats all 17 as one phenomenon. Detail in `defect-verification-report.md` §3.

---

## 3. Restoring the ten still leaves the dictionary inverted

This is the disagreement that matters most, because v2 §3.1 argues — correctly — that the direction defect is not cosmetic, then proposes a repair that would leave eight KPIs broken.

Eight lower-is-better KPIs have **no direction recorded anywhere in the file**, not in `Benchmark_Direction` and not in `Formula`. They are not recoverable; they have to be assigned.

```
   X03  QS rank      ─┐
   X04  THE rank      ├─ rank 1 beats rank 200.
   X05  NIRF rank    ─┘  As the file stands, and as it would still stand after
                         restoring the ten, the dictionary says higher is better.

   A18  Student-faculty ratio   ← has a real formula, so it looks well-formed
   A17  Average class size          while being directionally inverted
   A09  Review frequency (years)
   S10  Acceptance rate
   P15  Career counsellor ratio
```

`A18` is the trap. It is one of the four rows with a genuine `Formula` value, so any completeness check passes it, and it is a headline comparison metric.

v2's estimate of *"under one day"* for the correction still holds — `kpi_dictionary_v2.xlsx` took under an hour — but the scope is 18 directions plus 3 client decisions plus 3 categoricals, not 11 moves.

---

## 4. Doc 3's source mapping is not a usable replacement

v2 §3 correction 5 is right that `Primary_Source` is a domain label with 11 distinct values across 229 rows. The proposed action — *"Replace with per-subparameter source mapping from Doc 3"* — does not deliver what it promises.

Source frequency across the 160 themes in the parameters docx:

```
   "University official website / annual report / statutory disclosures"  148/160  ███████████████████  93%
   University Grants Commission                                            31/160  ████                 19%
   NIRF India                                                              27/160  ███                  17%
   National Assessment and Accreditation Council                           18/160  ██                   11%
   AISHE – Ministry of Education                                           16/160  ██                   10%
   All India Council for Technical Education                               14/160  ██                    9%
   ... 21 of the 34 directory entries appear on 3 themes or fewer
```

Every one of the 34 directory entries is an **organisation homepage** — `https://www.naac.gov.in/`, `https://www.ugc.gov.in/` — not a retrievable document. None of them returns a named university's data.

There is a further problem: **the two documents share no key.** Doc 3's "Subparameter" column holds numbered themes (`1.2 Student-Faculty Ratio`, `1.4 Retention, Progression and Dropout`); the Excel's `Sub_Parameter` holds different vocabulary at different granularity (`Faculty Ratio`, `Progression`, `Dropout`). The join has to be built by hand, not looked up. Built with token overlap inside each domain (see `IN_sources.yaml`), it routes **164 of 229** codes, 48 of them weakly, and leaves 65 unrouted — 16 of which are the entire `X` domain, which Doc 3 does not cover at all.

Swapping a domain-level boilerplate column for a theme-level boilerplate column is not progress. What actually routes is the three retrieval patterns confirmed by fetching: the NIRF PDF URL pattern, the WordPress media API, and the Common Data Set. Those are now in `IN_sources.yaml` under `verified_retrieval`, and `Primary_Source` should be replaced by them rather than by Doc 3.

---

## 5. The extraction ladder's PDF branch is incomplete

v2 §8 branches on *"Text layer present?"* — yes goes to Docling, no goes to OCR marked low quality. That is the right shape and the OCR isolation is right. But **a present text layer is not sufficient**, and the gap is silent.

Every NIRF submission is `/Rotate 90` with a 90° text matrix. Read without honouring it, the text layer is fully present, extraction reports success, and rows from adjacent tables interleave into output that looks plausible and is wrong. From the real IIT Bombay 2025 file:

```
   1430 78 410
   No. of students No. of students
   2018-19 selected for Higher selected for Higher
   83 154 259
```

No error is raised. Compare the OCR branch, where everyone already knows to distrust the output. This failure mode is more dangerous precisely because the ladder marks it as the high-confidence path.

Two consequences for v2:

- The ladder needs a rung between "text layer present" and "parse": **verify the page rotation is honoured**, on a known value, for whichever library is chosen.
- §9 selects Docling on merit, which is reasonable — but the rotation question is a property of the *documents*, not of the library, so it must be tested rather than assumed. In this investigation a rotation-aware geometric reconstruction parsed a 4-page submission in **572 ms** including network, with exact table recovery, so the fallback is cheap if Docling disappoints.

---

## 6. The digits/words checksum belongs in §10.2

v2 §10.2 lists four validation types and gives `UG + PG + Doctoral ≈ Total_Students` as the cross-field example. It misses a stronger one that the NIRF form supplies for free.

Every monetary field carries its value twice — digits and words, in the same cell: `1880000(Eighteen Lakhs Eighty Thousand)`. That is roughly **30 self-checking fields per document**, covering the entire Financial domain.

Measured across 14 submissions and 418 pairs: **400 comparable, 11 disagree (2.75%)**, four of ten ranked institutions affected, and Sandip at 6.2%. Full analysis in `checksum-analysis.md`.

v2 §10.3's warning about lakh/crore parsing is correct but one-sided — it guards the *normalisation* step. The checksum guards the *value itself*, and catches a class of error normalisation cannot see: a correctly-parsed number that is simply the wrong number.

It also needs a third outcome. 18 of 418 word forms were unparseable — 16 misspellings (`Sevety`, `Hundered`, `Eiight`, `Twentyone`, `Thous and`) and 2 spoken idioms (`eight fifty six` for 856). A two-state check would have reported every one as a defect. The rule must be **confirm / conflict / abstain**.

---

## Confirmed without change

For completeness, these v2 claims were re-verified and are exactly right:

- 229 KPI rows, `KPI_Code` unique across all of them, no duplicates
- `Variable_Name` has 224 distinct values across 229 rows — never usable as a key
- All eleven domain counts (ACA 36, RES 32, STU 24, INF 22, PLC 19, FAC 18, GOV 18, FIN 16, ESG 16, X 16, INT 12)
- `Benchmark_Direction` = `Higher` on 229/229
- `Priority_12M` = `P2` on 229/229
- `Primary_Source` has 11 distinct values; `ISO_21001_Mapping` has 1
- `Scraping_Keywords` is exactly `Sub_Parameter + Variable_Name + Definition` on 229/229, adding zero tokens
- `Formula` empty on 212 of 229
- Requirement docx §7 tables sum to 234 across 11 tables, against the Excel's 229 — Excel governs
- The source registry is India-only: no IPEDS, Common Data Set, HESA or OfS among the 34 entries

One small count correction: **17** columns are 100% empty, not 14. The phase-boundary argument is unaffected.

And one number v2 could not have known, which now answers its own Open Question 2: a NIRF submission populates **29 of the 229** directly, **35** with the faculty annexure, **47** if partial substitutions are accepted. 229/229 was never reachable.