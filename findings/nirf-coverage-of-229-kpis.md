# What a NIRF submission can actually populate of the 229 KPIs

Companion to `kpi-to-nirf-mapping.csv`, which carries the per-code
detail.

**Important first:** the dictionary's own `NIRF_Mapping` column cannot
do this job. It reads `TLR / GO` for all 36 Academic KPIs, `RP` for all
32 Research KPIs, and so on --- it maps *domains* to NIRF's five scoring
pillars, not KPIs to form fields. This mapping was therefore built from
the forms themselves, field by field, against the 72 metric concepts
inventoried from the IIT Bombay and Sandip 2025 Overall submissions.

------------------------------------------------------------------------

## The three numbers

       229 KPI codes in the dictionary
        │
        ├── 13  DIRECT    the value is printed in the form as-is
        ├── 16  DERIVED   computable from two or more printed institution-level values
        │        └─────►  29  populatable from a single NIRF submission
        │
        ├──  6  ANNEXURE  only from the faculty annexure in the institution-published copy
        │        └─────►  +6  added by Sandip's 190-row annexure
        │
        ├── 12  PARTIAL   NIRF carries a weaker form — a boolean or ordinal where the KPI wants a
        │                 number, or a near-synonym with a different definition
        │
        └── 182 NONE      not obtainable from a NIRF submission at any strength

  -----------------------------------------------------------------------
  Question asked                      Answer
  ----------------------------------- -----------------------------------
  How many of the 229 can a single    **29** (13 direct + 16 derived)
  NIRF submission populate?           

  How many does the Sandip faculty    **6**
  annexure add?                       

  How many are unreachable from NIRF  **182**
  entirely?                           
  -----------------------------------------------------------------------

Accepting the 12 PARTIAL substitutions --- each of which needs an
explicit dictionary decision, because it changes what the KPI means ---
takes coverage to **47 of 229 (21%)** and leaves 182 unreachable either
way.

------------------------------------------------------------------------

## Coverage by domain

  -----------------------------------------------------------------------------------------
  Domain                KPIs    DIRECT   DERIVED   ANNEXURE   PARTIAL      NONE   reachable
  ---------------- --------- --------- --------- ---------- --------- --------- -----------
  FAC Faculty             18         1         1          6         0        10     **44%**

  STU Student             24         4         4          0         3        13     **33%**

  RES Research            32         5         1          0         1        25         19%

  FIN Financial           16         0         3          0         1        12         19%

  PLC Placement           19         1         2          0         0        16         16%

  X Cross-cutting         16         2         0          0         1        13         12%

  ACA Academic            36         0         4          0         1        31         11%

  INT                     12         0         1          0         0        11          8%
  International                                                                 

  INF                     22         0         0          0         1        21      **0%**
  Infrastructure                                                                

  GOV Governance          18         0         0          0         1        17      **0%**

  ESG                     16         0         0          0         3        13      **0%**
  Sustainability                                                                
  -----------------------------------------------------------------------------------------

Three domains --- Infrastructure, Governance, Sustainability, 56 KPIs
between them --- are at zero. NIRF asks about all three, but every
question is a checklist or a yes/no where the dictionary wants a
measured quantity. `ESG07 Waste recycling rate` wants a percentage; NIRF
asks *"What is the level of recycling infrastructure available on your
campus?"* and offers `Comprehensive infrastructure` /
`No recycling infrastructure on campus`. Genuinely informative --- IIT
Bombay and Sandip give opposite answers --- but it is not a rate.

Faculty is the strongest domain, and only because of the annexure. From
the NIRF-portal copy alone, Faculty coverage drops from 44% to 11%.

------------------------------------------------------------------------

## The mapping runs both ways, and the other direction is worse

       72 NIRF concepts found in the forms
            │
            ├── 33  have a home in the 229-KPI dictionary
            └── 39  have NO KPI code at all

More than half of what NIRF collects has nowhere to go in the
dictionary. Among the orphans: the entire capital-expenditure breakdown
(library, laboratory equipment, workshops, studios, other assets ---
five separate heads), the entire operational-expenditure breakdown, all
of consultancy (projects, clients, amount), all of executive/management
development programmes, lateral-entry admissions, the four-way split of
fee reimbursement by funding source, and every Indian Knowledge System
question.

**So the dictionary and the best available Indian source overlap on less
than half of each other.** That is the single most useful number to put
in front of the president, because it turns an unanswerable question ---
*"can you collect all 229?"* --- into a concrete one: *"the dictionary
asks for 229 things; the national standardised form supplies 29 of them
directly and 39 things nobody asked for. Which list do we trust?"*

------------------------------------------------------------------------

## What this means for iteration 1

The earlier estimate of 120--180 populated values across three
institutions is confirmed and probably conservative, but it needs
restating in the dictionary's own terms:

  -----------------------------------------------------------------------
  value                               
  ----------------------------------- -----------------------------------
  KPI codes populatable per           29 (35 with annexure)
  institution-year from NIRF          

  Institutions × years for iteration  3 × 2
  1                                   

  **Populated KPI-code × institution  **\~175--210**
  × year rows**                       

  Coverage against the 229            **13% strict, 21% with partial
                                      substitutions**
  -----------------------------------------------------------------------

That 13% is not a failure and should not be presented as one. It is the
measured answer to Open Question 2 in the v2 spec --- *"what coverage
rate counts as success?"* --- which until now had no number attached to
it at all. **229/229 was never achievable from public Indian sources,
and now there is evidence for exactly how far short it falls and why.**

The remaining 182 split into three groups that need different answers
from the client:

  ------------------------------------------------------------------------------------
  Group                                   n (approx) What is needed
  --------------------- ---------------------------- ---------------------------------
  Available from other                          \~60 Scopus/OpenAlex for R01--R10,
  public sources                                     QS/THE for X01--X04, AISHE for
                                                     some student figures

  Available only from                           \~80 These are internal-governance and
  the institution                                    internal-finance KPIs. No public
  itself                                             source exists for anyone,
                                                     anywhere.

  Unmeasurable as                               \~40 `CQI_Closure_Rate`,
  defined                                            `Revenue_Diversification_Index`
                                                     (no formula),
                                                     `Data_driven_decision_making` (%
                                                     of decisions)
  ------------------------------------------------------------------------------------

The middle group is the important one. KPIs like
`G05 Academic audit coverage`, `G14 SLA compliance` or
`FIN11 Operating margin` are not hard to find --- they are not published
by anybody. A benchmarking system cannot compare institutions on numbers
that only each institution's own registrar holds. That is a scoping
conversation, not an engineering problem.
