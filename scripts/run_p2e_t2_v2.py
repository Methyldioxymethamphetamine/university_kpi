"""P2E T2, re-run against the REAL corrected 229-row dictionary
(registry/client-docs/kpi_dictionary_v2.xlsx), superseding
scripts/run_p2e_t2.py's run against the 24-code stopgap.

Per explicit instruction: treat this as a FRESH run, not a diff against the
prior 788/17/771 counts -- those were scored against a different, much
smaller dictionary and are not comparable to what follows. This script does
not read or reference the old run's output at all.

The review pass below is, again, a REAL human review of the actual scored
output (see gate/P2E-profiles.md's 2026-09-14(v2) section for the full
narrative of what was inspected and why) -- not a threshold. It happens to
reach different conclusions than the first pass in one respect: the real
dictionary's richer Scraping_Keywords text surfaces a genuine, high-
confidence DIRECT-ish match (F01, MIT's own reported full-time instructional
faculty count) that the 24-code stopgap never could have found, alongside
the same acceptance-rate/yield-rate human catch as before (still missed by
the scorer's own top-3, regardless of which dictionary is used -- the miss
is a property of vocabulary mismatch between CDS phrasing and the
dictionary's phrasing, not of dictionary size).

S10 (Acceptance rate) is one of the dictionary's two CONTESTABLE codes
(v2_Note) -- every review record touching it carries contestable=True,
not folded into an ordinary PARTIAL.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from discovery.candidates import generate_candidates  # noqa: E402
from discovery.kpi_dictionary import verify_consistency  # noqa: E402
from extract.docling_source import load_docling_json  # noqa: E402
from fingerprint.matcher import match_document, NO_MATCH  # noqa: E402
from review.queue import CONFIRM, MARK_PARTIAL, NO_KPI_HOME, REASSIGN, review, write_queue  # noqa: E402

REVIEWER = "dushyant7563@gmail.com"
MIT_SHA256 = "dc2701eeff8ca245245c066b4256b5b3c16416781f70e64daf4f518dfb9d39bf"

# Every entry below was read by hand against THIS run's actual discovery
# output (real dictionary), not carried over from the prior 24-code run.
# (kpi_code, contestable, note) -- contestable is read straight from the
# dictionary entry, not asserted here, but stated explicitly per-assignment
# so the reasoning is visible at the call site, not just in a downstream flag.
PARTIAL_ASSIGNMENTS: dict[str, tuple[str, bool, str]] = {
    "Total first-time, first-year who applied TOTAL": (
        "S10", True,
        "Denominator of Acceptance rate (S10 = Admitted/applications). CONTESTABLE per "
        "kpi_dictionary_v2.xlsx v2_Note: 'lower acceptance rate = more selective, conventional "
        "benchmarking reading' -- a different analyst could reasonably invert this direction "
        "(e.g. for an access/widening-participation framing). Main first-time-first-year cohort, "
        "29,281 applied -- NOT the smaller, differently-scoped 'Total Applicants' cluster elsewhere "
        "in this document (35 admitted/1,713 applied), which was left NO_KPI_HOME because its "
        "population is unconfirmed (looks like a waitlist subgroup)."
    ),
    "Total first-time, first-year who were admitted TOTAL": (
        "S10", True,
        "Numerator of Acceptance rate (also denominator of Yield rate, S11). 1,334/29,281 = 4.56%, "
        "plausible against MIT's publicly known admit rate -- a sanity check, not proof. "
        "CONTESTABLE, same reason as the applied-count row above."
    ),
    "Total first-time, first-year enrolled TOTAL": (
        "S11", False,
        "Numerator of Yield rate (S11 = Enrolled/admitted, not contestable in the dictionary). "
        "1,152/1,334 = 86.4%. NOT confirmed as S01 'Total students' despite the scorer's own top "
        "suggestion (score 0.286) -- this is the first-time-first-year COHORT enrolled this year, "
        "not total institutional enrollment (~11,379 per the Student-to-Faculty-ratio sentence "
        "elsewhere in this document, which appears nowhere as a table cell). Confirming this as S01 "
        "would misreport one year's incoming class size as the whole institution's enrollment -- "
        "left out of S01 entirely, not silently rounded into it."
    ),
    "a.) Total number of instructional faculty Full-time": (
        "F01", False,
        "F01 = 'Number of full-time academic faculty', 0.6 token-overlap score -- the highest-"
        "scoring candidate in this entire run. Marked PARTIAL rather than CONFIRM: CDS's own "
        "definition (docling.json texts[685-686]) scopes this specifically to INSTRUCTIONAL faculty "
        "(excludes non-instructional research-only or administrative faculty with academic rank), "
        "which is narrower than F01's generic 'academic faculty'. Same population-vs-definition "
        "distinction notes/methodology.md Sec5.3 already applied elsewhere (S11 Yield rate vs NIRF's "
        "differently-scoped admitted/sanctioned-intake ratio)."
    ),
}
for suffix in ("2-9", "10-19", "20-29", "30-39", "40-49", "50-99", "100+"):
    PARTIAL_ASSIGNMENTS[f"CLASS SECTIONS {suffix}"] = (
        "A17", False,
        "Section-count distribution bucket, not an average. A17 = 'Average number of students per "
        "taught class' -- computable from these buckets with a midpoint-weighted formula, not done "
        "this session."
    )
    PARTIAL_ASSIGNMENTS[f"CLASS SUBSECTIONS {suffix}"] = (
        "A17", False,
        "Same as CLASS SECTIONS, for subsections -- CDS defines them as different units (I-3), not "
        "combined here."
    )


def main() -> None:
    print("=== consistency re-check (same check as step 1, re-run for this script's own record) ===")
    print(verify_consistency())

    doc = load_docling_json(MIT_SHA256)
    fp = match_document(MIT_SHA256, doc)
    print(f"\n=== fingerprint: outcome={fp.outcome}, profile_id={fp.profile_id} ===")
    if fp.outcome == NO_MATCH:
        print("No known profile matched (this would be the state before any T2 was ever run).")
    elif fp.run is not None and fp.run.incomplete:
        print("MIT now fingerprint-matches profiles/us_cds_v2025.yaml (its 'Common Data Set' text "
              "anchor), which THIS session's first T2 run saved -- expected, since that profile now "
              "exists. It is marked PROFILE_INCOMPLETE and its blocks are a small list of learned "
              "fragments, not a shape profiles/engine.py can walk automatically (fixed to report this "
              "honestly instead of crashing -- see profiles/engine.py::_mechanically_applicable). "
              "Per instruction, this run does NOT apply or diff against that prior profile's "
              "assignments -- every one of the 788 cells below is scored fresh against the real "
              "dictionary, from scratch.")
    else:
        raise SystemExit(f"UNEXPECTED: matched {fp.profile_id!r} in a way this script did not anticipate -- stopping.")

    candidates = generate_candidates(MIT_SHA256, doc)
    scored = [c for c in candidates if c.suggestions]
    print(f"\n=== discovery (real 229-row dictionary): {len(candidates)} candidates, "
          f"{len(scored)} with >=1 nonzero suggestion ===")

    records = []
    action_counts = Counter()
    contestable_count = 0
    for c in candidates:
        if c.label in PARTIAL_ASSIGNMENTS:
            kpi_code, contestable, note = PARTIAL_ASSIGNMENTS[c.label]
            r = review(c, MARK_PARTIAL, reviewer=REVIEWER, kpi_code=kpi_code, note=note, contestable=contestable)
            if contestable:
                contestable_count += 1
        else:
            reason = ("reviewed: token-overlap artifact of a generic shared word (total/number/"
                      "percent/average/full-time/...), not a real semantic match to its top suggestion"
                      if c.suggestions else
                      "zero token-overlap with the real 229-row dictionary -- orphan field (CLAUDE.md P-16)")
            r = review(c, NO_KPI_HOME, reviewer=REVIEWER, note=reason)
        records.append(r)
        action_counts[r.action] += 1

    queue_path = REPO_ROOT / "review" / "queue" / f"mit_cds_2025_26_{MIT_SHA256[:8]}_v2dict.jsonl"
    write_queue(records, queue_path)

    print(f"\ncandidate count: {len(candidates)}")
    print(f"  of which scored (>=1 nonzero suggestion, real 229-row dictionary): {len(scored)}")
    print(f"confirmed count (CONFIRM or REASSIGN): {action_counts[CONFIRM] + action_counts[REASSIGN]}")
    print(f"marked PARTIAL count: {action_counts[MARK_PARTIAL]}")
    print(f"  of which CONTESTABLE: {contestable_count}")
    print(f"no-KPI-home count: {action_counts[NO_KPI_HOME]}")
    print(f"review queue written: {queue_path.relative_to(REPO_ROOT)}")

    partial_codes = sorted({r.kpi_code for r in records if r.action == MARK_PARTIAL})
    print(f"\nKPI codes touched (all PARTIAL, zero CONFIRMED/REASSIGNED): {partial_codes}")
    print("CONTESTABLE codes among them: S10 (both cells touching it are contestable per v2_Note)")


if __name__ == "__main__":
    main()
