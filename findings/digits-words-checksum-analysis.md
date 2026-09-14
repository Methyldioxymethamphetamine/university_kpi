# The digits-vs-words checksum: how general is it?

**Question asked:** the ₹37.5 lakh discrepancy in Sandip's file was
found by hand. If the NIRF form requires amounts in both digits and
words, every financial field carries its own built-in checksum. Is that
systematic enough to become a pipeline validation rule?

**Answer: yes, and it fires more often than expected.**

------------------------------------------------------------------------

## What was measured

Fourteen NIRF submission PDFs: ten institutions from the 2025 Overall
top-100 list (sampled at ranks 1, 2, 3, 5, 10, 20, 30, 50, 75, 100) plus
four Sandip submissions from the institution's own site (2024, 2025 and
2026 Overall, and 2025 Engineering).

Every `digits(words)` pair was extracted by rebuilding wrapped table
cells geometrically --- the words routinely continue onto two or three
further lines of the same cell, so a line-by-line reader splits them and
finds nothing. The word form was then parsed into a number with an
Indian-numbering parser (lakh / crore / hundred, with scale-absorption
so `One Thousand Four Hundred Sixty Crore` resolves to 1460 crore rather
than 1000 + 460).

         pairs found                                    418

            │

            ├── word form unparseable                    18   ← the checker must ABSTAIN here
            │     ├── misspelling                        16     "Sevety", "Hundered", "Eiight",
            │     │                                             "Twentyone", "Thous and"
            │     └── spoken idiom                        2     "eight fifty six" meaning 856

            │

            └── comparable                              400
                  ├── agree                             389    97.25%
                  └── DISAGREE                           11     2.75%

Every one of the 11 was checked by hand against the raw PDF text runs.
None is an artifact of the extractor or the parser.

------------------------------------------------------------------------

## Coverage: the checksum is dense, not occasional

                                                       pairs per document   documents
  ---------------------------------------------------- -------------------- -----------
  NIRF portal copies (10 institutions, 2025 Overall)   28 -- 37             10
  Sandip own-site copies (3 years + 1 category)        24 -- 27             4

Every financial field in the form carries it --- capital expenditure
across five heads, operational expenditure across three, sponsored
research, consultancy, EDP earnings, and every median salary. That is
roughly **30 self-checking fields per document**, covering the entire
Financial domain and the single most politically sensitive number in the
whole exercise (median graduate salary).

------------------------------------------------------------------------

## Rate by institution

  Institution                             comparable pairs   disagreements
  ------------------------------------- ------------------ ---------------
  IIT Bombay (IR-O-U-0306)                              29               0
  5 other ranked institutions                          156               0
  IR-O-U-0220                                           28               1
  IR-O-U-0304                                           32               1
  IR-O-U-0500                                           30               1
  IR-O-U-0272                                           28               2
  *ten ranked institutions, subtotal*                *303*     *5 (1.65%)*
  **Sandip (4 documents)**                          **97**   **6 (6.19%)**

Four of the ten ranked institutions have at least one financial figure
whose digits and words disagree. Sandip's rate is **6.2%**, more than
three times the ranked-institution rate --- which is itself a finding
worth reporting, and one that only this cross-check can produce.

------------------------------------------------------------------------

## The three disagreements that matter

**1. The ₹37.5 lakh error is not a one-off.**

       Sandip 2025 Overall, p1:  3750000(Three Lakh Seventy Five Thousand)
       Sandip 2024 Overall, p1:  3750000(Three Lakh Seventy Five Thousand)
                                 └───┬───┘└──────────────┬───────────────┘
                                  37,50,000           3,75,000

The same cell carries the same 10× error in two consecutive submissions.
It is copied forward between years, so it will keep appearing until
someone notices. The neighbouring years read ₹5.2 lakh and ₹5.5 lakh, so
the words are right and the digits carry a stray zero.

**2. Sandip's Engineering submission is wrong by ₹53 crore.**

       173860605 (Seventy Crore Thirty Eight Lakh Sixty Thousand Six hundred Five)
       └───┬───┘  └──────────────────────┬──────────────────────────────────────┘
       17.39 crore                   70.39 crore

Verified as a single unmodified text run in the PDF. A leading digit
appears to have been lost or transposed. This is an expenditure figure
--- it would flow straight into cost-per-student.

**3. `999 (Zero)`.**

Literally that, in Sandip's 2024 Overall submission, page 3. Checked at
raw-item level; it is not an extraction artifact. It is the clearest
possible illustration that these forms are typed by hand and never
machine-validated.

Full detail for all 11 is in `checksum-disagreements.csv`.

------------------------------------------------------------------------

## The abstention rule matters as much as the check

18 of 418 word forms could not be parsed, and **every one of them would
have become a false accusation** under a naive implementation:

  ------------------------------------------------------------------------------
  Cause                                n Example                What a naive
                                                                checker does
  ---------------- --------------------- ---------------------- ----------------
  Misspelling                         16 `Sevety Eight Lakh`,   rejects the
                                         `Six Hundered`,        token, calls it
                                         `Eiight Lakh`,         a mismatch
                                         `Twentyone Crores`,    
                                         `Forty Thous and`      

  Spoken idiom                         2 `eight fifty six` for  parses as 8+50+6
                                         856, `seven thirty`    = 64, calls it a
                                         for 730                mismatch
  ------------------------------------------------------------------------------

During development this parser produced **9** mismatches before the
scale-absorption bug and the idiom detector were added. Four of those
nine were the parser's fault, not the document's.

Had those been reported to a client as data-quality defects, the report
itself would have been the defective artifact.

So the rule has three outcomes, not two:

       digits == words          →  CONFIRMED      raise confidence above a single-source read
       digits != words          →  CONFLICTING    flag, retain both, never auto-resolve
       words unparseable        →  UNVERIFIED     neither confirm nor accuse

------------------------------------------------------------------------

## Recommendation

Make this a first-class validation rule, not a demo anecdote.

1.  **Run it on every monetary field at extraction time.** It costs
    nothing --- the word form is already inside the same cell you are
    parsing.

2.  **Store the outcome in `authentication_status`.** A digits/words
    agreement is the cheapest corroboration available anywhere in this
    project: two independent renderings of the same figure, typed by the
    same institution, in the same document. It upgrades a single-source
    value from "one source said so" to "the institution wrote it twice
    and both agree."

3.  **Never auto-resolve.** Neither side is reliably right. In case 1
    the words are correct; in case 2 the words are correct; in the
    ₹500-apart case it is genuinely unknowable without a third source.

4.  **Abstain on unparseable word forms.** Misspellings are common
    enough (16 in 418) that a strict parser is a liability.

5.  **Extend the pattern.** The same form carries a separate
    `Amount Received in Words` row beneath
    `Total Amount Received (Amount in Rupees)` for sponsored research,
    consultancy and EDP earnings. Same check, different geometry.

There is a fourth use, beyond validation. The disagreement rate is
itself a measurable signal about how carefully an institution compiles
its returns --- 0% at IIT Bombay, 6.2% at Sandip. That is a defensible,
evidence-backed institutional-quality observation that no individual
number could support.
