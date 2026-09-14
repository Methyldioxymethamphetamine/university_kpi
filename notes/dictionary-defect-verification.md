`# Excel defect verification`

``Every claim below was checked against `DOC-20260901-WA0019.xlsx` (sheet `KPI_Dictionary`,``

`229 data rows, 38 columns). The original file was never opened for writing.`

`**Summary: four of five claims confirmed exactly. One is confirmed in effect but wrong about`

`the mechanism, and the real mechanism is worse.**`

`| # | Claim | Verdict |`

`|---|---|---|`

``| 1 | `Benchmark_Direction` = "Higher" on all 229 rows | ✅ **Confirmed** — 229/229 |``

``| 2 | 11 "Lower" values shifted one column left into `Formula` | ⚠️ **Partly** — there are **10**, and it is not a shift |``

``| 3 | `Formula` also holds 3 stray `Data_Type` values | ✅ **Confirmed** — and they mark a *second, separate* defect |``

``| 4 | `Priority_12M` constant at P2 | ✅ **Confirmed** — 229/229 |``

`| 5 | Nine columns constant per domain, not per KPI | ✅ **Confirmed** — exactly nine |`

``| 6 | `Scraping_Keywords` = `Sub_Parameter + Variable_Name + Definition` | ✅ **Confirmed** — 229/229 exact |``

``| 7 | `Formula` empty on 212 of 229 rows | ✅ **Confirmed** — 212 empty, 17 populated |``

`---`

``## 1. `Benchmark_Direction` — confirmed``

` ``` `

`   Benchmark_Direction, original file`

`   ─────────────────────────────────────`

`   'Higher'   229    ████████████████████  100%`

` ``` `

``One distinct value across all 229 rows, including `A25 Dropout rate`, `F14 Faculty turnover`,``

`` `S21 Reported serious incidents`, `I14 Security incidents`, `ESG03 Scope 1 emissions`, ``

`` `ESG04 Scope 2 emissions` and `ESG05 Water consumption/student`. ``

``The consequence stands as stated: `Data_Schema` defines `Gap` as *"benchmark minus institution,``

`direction adjusted."* A Phase 2 engine reading this file recommends increasing dropout and`

`emissions.`

`---`

`## 2. The "11 Lower values shifted one column left" claim — two corrections`

`` `Formula` holds 17 non-empty values. They are three different things: ``

`| What it actually is | n | Values |`

`|---|---|---|`

``| Genuine formulas (keep) | **4** | `Students/FTE faculty`, `Publications/FTE faculty`, `Citations/FTE faculty`, `Faculty/Student` |``

``| Benchmark directions (move) | **10** | `Lower` × 9, `Lower absolute variance` × 1 |``

``| Data types (separate defect) | **3** | `integer` × 3 |``

`` **Correction (a): ten, not eleven.** Nine rows read `Lower`, one reads `Lower absolute variance` ``

`(FIN14 Budget variance). 4 + 10 + 3 = 17.`

``**Correction (b): it is not a shift, and not one column.** `Formula` is three columns left of``

`` `Benchmark_Direction`: ``

` ``` `

`   ... │ Unit │ Data_Type │ Formula │ Scraping_Keywords │ Primary_Source │ Benchmark_Direction │ ...`

`                            ▲                                                   ▲`

`                            └──────────────── three columns ────────────────────┘`

` ``` `

``On all ten rows `Unit` and `Data_Type` are **correct**. Only `Formula` holds the wrong thing.``

`So this is a mis-targeted write — whoever built the file put the non-default direction in the`

``wrong column and left `Benchmark_Direction` at a blanket `Higher` — not a row that slid sideways.``

`The distinction matters for the repair: a shift would be fixed by moving a whole row's cells; a`

`mis-targeted write is fixed cell by cell, and only the ten affected rows are touched.`

`### 2.1 The more serious finding: ten is not the full set`

`Restoring only the ten recoverable values still leaves the dictionary inverted on eight more`

`KPIs whose direction was never recorded *anywhere* in the file:`

`| KPI | Variable | Unit | Why it is Lower | In the file? |`

`|---|---|---|---|---|`

``| `A09` | Review frequency | years | shorter interval between curriculum reviews is better | never marked |``

``| `A17` | Average class size | students/class | smaller is the quality signal | never marked |``

``| `A18` | **Student-faculty ratio** | ratio | students per faculty — fewer is better | never marked, and it *has* a genuine formula |``

``| `S10` | Acceptance rate | % | selectivity — lower is more selective | never marked |``

``| `P15` | Career counsellor ratio | ratio | students per professional — fewer is better | never marked |``

``| `X03` | **QS rank** | rank | rank 1 beats rank 200 | never marked |``

``| `X04` | **THE rank** | rank | same | never marked |``

``| `X05` | **NIRF rank** | rank | same | never marked |``

`The three rank KPIs are the sharpest. As the file stands — and as it would still stand after a`

`repair that only moved the ten recoverable values — the dictionary asserts that a *higher* QS`

``rank number is better. Any gap calculation on `X03`, `X04` or `X05` comes out backwards.``

`` `A18` deserves its own note: it is one of the four rows with a real formula ``

``(`Students/FTE faculty`), so it looks well-formed and would pass a completeness check, while``

`being directionally inverted.`

`### 2.2 Three that were not guessed`

``| KPI | Variable | Why it is left as `Context` |``

`|---|---|---|`

``| `FIN02` | Tuition revenue share | High tuition dependence is a concentration risk, but `FIN05` already measures diversification. Risk metric or scale metric? |``

``| `FIN07` | Cost/student | Reads as resourcing (higher better) in QS/THE, as efficiency (lower better) in a cost review |``

``| `FIN10` | Faculty cost/revenue | A sustainability band, not a monotonic direction |``

``And three have no direction at all: `G01` Governance structure, `X06` NAAC status,``

`` `X08` ISO 21001 status — all categorical. ``

`---`

``## 3. The 3 `integer` values are a second, different defect``

``The three rows are `A01`, `A02`, `A03`. Compare `A01` with `A04`, which is structurally``

`identical and correct:`

` ``` `

`        Definition                              Unit                           Data_Type   Formula`

`  A04   Number of interdisciplinary programmes  count                          integer     —          ✅`

`  A01   Number of undergraduate programmes      Number of active UG programmes  count      integer    ❌`

`                                                └──── inserted ────┘            └── shifted right ──┘`

` ``` `

``An extra label was inserted at `Unit`, pushing `Unit → Data_Type` and `Data_Type → Formula`.``

``So this defect corrupts **three columns on each of three rows**, not just `Formula`. Nine cells.``

``Two consequences that the `Formula`-only reading misses:``

``- **`Unit` is wrong on A01–A03**, holding a prose restatement of `Definition` instead of `count`.``

``- **`count` is not a valid data type.** It appears as a `Data_Type` on exactly these three rows``

``and nowhere else. Once repaired, `Data_Type` has four clean values and the phantom disappears:``

` ``` `

`   Data_Type        original      v2`

`   ───────────────────────────────────`

`   numeric               150     150`

`   integer                57      60`

`   boolean                16      16`

`   text                    3       3`

`   count                   3       0     ← was a leaked Unit`

` ``` `

`---`

``## 4. `Priority_12M` — confirmed``

`` `P2` on all 229 rows, against a `Priority_Framework` sheet that defines four tiers and is ``

`otherwise unreferenced.`

`**Not corrected in v2.** The right priorities are a client decision and cannot be recovered from`

`the file. Guessing them would manufacture authority the data does not have. The column is left`

`as it is and documented as unpopulated.`

`---`

`## 5. Nine columns constant per domain — confirmed exactly`

`| Column | distinct values across 229 rows | distinct within any one domain |`

`|---|---|---|`

``| `Primary_Source` | 11 | 1 |``

``| `QS_Mapping` | 11 | 1 |``

``| `NIRF_Mapping` | 11 | 1 |``

``| `NAAC_Mapping` | 11 | 1 |``

``| `NBA_Mapping` | 10 | 1 |``

``| `AICTE_Mapping` | 11 | 1 |``

``| `UGC_Mapping` | 11 | 1 |``

``| `ISO_21001_Mapping` | **1** | 1 |``

``| `Best_Practice_To_Check` | 11 | 1 |``

`Exactly nine. Each carries one value per domain and therefore encodes 11 facts, not 229.`

`` `ISO_21001_Mapping` reads the literal string `ISO 21001` on every row — zero information. ``

``There is a practical consequence for the NIRF mapping work: `NIRF_Mapping` reads `TLR / GO` for``

``all 36 Academic KPIs, `RP` for all 32 Research KPIs, and so on. It maps domains to NIRF's five``

`scoring pillars. **It cannot be used to route a KPI to a NIRF form field**, which is why the`

``mapping in `kpi-to-nirf-mapping.csv` had to be built from the forms themselves.``

`---`

``## 6. `Scraping_Keywords` — confirmed, and worse than "redundant"``

``All 229 rows match `f"{Sub_Parameter}, {Variable_Name}, {Definition}"` **exactly**, character for``

`character. Tokenised, the number of rows contributing *any* token not already present in those`

`three fields is **zero**.`

`It is not merely low-value. It is a derived column presented as a source of search terms, and a`

`pipeline that trusts it will search for the dictionary's own prose rather than the vocabulary`

`institutions actually use. Real NIRF field labels read`

`` `Median salary of placed graduates per annum(Amount in Rs.)` — nothing like ``

`` `Salary, Median salary, Median annual compensation of placed graduates`. ``

`---`

`## 7. Empty columns — confirmed, with a count correction`

`**17** columns are 100% empty, not 14:`

` ``` `

`   University_Name · Country · Data_Year · Raw_Value · Normalized_Value ·`

`   Benchmark_Value · Gap · Target_12M · Responsible_Office · Evidence_URL ·`

`   Evidence_Type · Confidence · Best_Practice_Flag · Implementation_Cost ·`

`   Implementation_Complexity · Implementation_Time · Action_Recommendation`

` ``` `

`The phase boundary argument is unchanged and still holds — these are analysis and instance`

`fields, not dictionary fields — but the count in the earlier note was low by three.`

``One more: `QS_Mapping` is empty on 16 rows. Those 16 are exactly the `X` cross-cutting domain,``

`which is consistent rather than defective.`

`---`

`` ## What was repaired in `kpi_dictionary_v2.xlsx` ``

``43 cell changes, all logged in the workbook's `CHANGELOG_v2` sheet and traceable per row via``

``two added columns, `Benchmark_Direction_Source` and `v2_Note`.``

`| Change | Rows | Cells |`

`|---|---|---|`

``| Direction recovered from `Formula`, `Formula` cleared | 10 | 20 |``

`| Direction assigned in v2 (never recorded in the original) | 8 | 8 |`

``| Direction marked `Context` — client decision needed | 3 | 3 |``

``| Direction marked `N/A` — categorical | 3 | 3 |``

``| Inserted-cell shift repaired on A01–A03 (`Unit`, `Data_Type`, `Formula`) | 3 | 9 |``

`Resulting distribution:`

` ``` `

`   Benchmark_Direction, v2`

`   ──────────────────────────────────────────`

`   Higher                     205   ██████████████████  89.5%`

`   Lower                       17   ██                   7.4%`

`   Lower (absolute variance)    1                        0.4%`

`   Context                      3                        1.3%`

`   N/A                          3                        1.3%`

` ``` `

`` `Formula` now holds four values, all of them formulas. Deliberately **not** changed: ``

`` `Priority_12M`, `Scraping_Keywords`, and the nine domain-constant columns — each is documented ``

`in the workbook's README rather than silently rebuilt.`