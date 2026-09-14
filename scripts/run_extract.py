#!/usr/bin/env python3
"""Run P2C extraction: self-test the word parser FIRST (STOP CONDITION if it
fails), then extract values + checksums from every converted artifact, write
values/run={ts}/{values,checksums}.jsonl, and self-verify by RE-READING that
output from disk (P-10).

Usage:
    python scripts/run_extract.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from extract.checksums import CONFIRMED, CONFLICTING, UNVERIFIED  # noqa: E402
from extract.pipeline import run_extraction, write_run  # noqa: E402
from extract.word_number import self_test  # noqa: E402

SANDIP_SOURCE_ID = "sandip_sitrc_overall"
SANDIP_ACCEPTANCE_DIGITS = "3750000"
SANDIP_ACCEPTANCE_WORDS = "Three Lakh Seventy Five Thousand"


def print_self_test(report) -> bool:
    print("=== P2C word-parser self-test (must pass before any real document) ===")
    for row in report.all_rows():
        print(" ", row)
    print("SELF-TEST:", "PASS" if report.passed else "FAIL")
    return report.passed


def self_verify(values_path: Path, checksums_path: Path) -> int:
    print()
    print("=== P2C self-verification (re-read from disk) ===")

    value_rows = [json.loads(line) for line in values_path.read_text(encoding="utf-8").splitlines() if line]
    checksum_rows = [json.loads(line) for line in checksums_path.read_text(encoding="utf-8").splitlines() if line]

    print(f"value rows: {len(value_rows)}")
    dash_dist = Counter(r["dash_state"] for r in value_rows)
    print(f"dash_state distribution (P-8): {dict(dash_dist)}")
    period_present = sum(1 for r in value_rows if r["period_type"] is not None)
    print(f"value rows with period_type set (P-9): {period_present}/{len(value_rows)}")
    uncited_values = [r for r in value_rows if not r.get("sha256") or not r.get("item_id")]
    print(f"value rows missing sha256/item_id (must be 0): {len(uncited_values)}")

    print()
    print(f"checksum rows: {len(checksum_rows)}")
    state_dist = Counter(r["state"] for r in checksum_rows)
    for state in (CONFIRMED, CONFLICTING, UNVERIFIED):
        state_dist.setdefault(state, 0)
    print(f"three-state distribution (P-7): {dict(state_dist)}")
    uncited_checksums = [r for r in checksum_rows if not r.get("sha256") or not r.get("item_id")]
    print(f"checksum rows missing sha256/item_id (must be 0): {len(uncited_checksums)}")
    invariant_violations = [
        r for r in checksum_rows if (r["words_value"] is None) != (r["state"] == UNVERIFIED)
    ]
    print(f"rows where UNVERIFIED/abstain invariant is broken (must be 0): {len(invariant_violations)}")
    no_bbox = [r for r in checksum_rows if r.get("page_no") is None or r.get("bbox") is None]
    print(f"checksum rows missing page_no or bbox (must be 0 for pdf_* sources): {len(no_bbox)}")

    hard_failure = bool(uncited_values) or bool(uncited_checksums) or bool(invariant_violations)
    print("SELF-VERIFICATION: " + ("FAIL" if hard_failure else "PASS"))
    return 1 if hard_failure else 0


def report_cross_checks(results) -> None:
    print()
    print("=== P-11: cross-check every checksum-bearing pdf_* artifact against raw pypdfium2 text runs ===")
    any_checked = False
    for res in results:
        if res.cross_check is None:
            continue
        any_checked = True
        cc = res.cross_check
        status = "AGREE" if cc.agrees else "DISAGREE"
        print(f"  {res.sha256[:8]} ({res.label}): docling={cc.docling_pair_count} geometric={cc.geometric_pair_count} -> {status}")
        for pair in cc.docling_only:
            print(f"      docling-only (NOT independently confirmed): {pair}")
        for pair in cc.geometric_only:
            print(f"      geometric-only (NOT in docling table cells): {pair}")
    if not any_checked:
        print("  (no pdf_* artifact with checksum-shaped cells was available to cross-check)")


def report_acceptance_test(results) -> None:
    print()
    print("=== ACCEPTANCE TEST: Sandip 2025 Overall, 3750000 vs 'Three Lakh Seventy Five Thousand' ===")
    sandip_artifacts = [r for r in results if r.source_id == SANDIP_SOURCE_ID]
    if not sandip_artifacts:
        print("BLOCKED-PENDING-SANDIP")
        print("  Sandip's document was never acquired: gate/P2A-acquire.md Sec3 records that")
        print("  sitrc.sandipfoundation.org/robots.txt disallows '*.pdf' and '/pdf/', so the PDF")
        print("  cannot be fetched under this project's required ROBOTSTXT_OBEY=True. No")
        print(f"  artifact with source_id={SANDIP_SOURCE_ID!r} exists under raw/ or docs/.")
        print("  This acceptance test CANNOT be run end to end and is reported as BLOCKED, not")
        print("  as PASS or FAIL, and not substituted with a different document's conflict.")
        return

    for res in sandip_artifacts:
        match = next(
            (
                r
                for r in res.checksum_rows
                if r.raw_digits.replace(",", "") == SANDIP_ACCEPTANCE_DIGITS and r.raw_words == SANDIP_ACCEPTANCE_WORDS
            ),
            None,
        )
        if match and match.state == CONFLICTING:
            print(f"PASS -- {res.sha256[:8]}: CONFLICTING row emitted, digits={match.digits_value} words={match.words_value}")
        else:
            print(f"FAIL -- {res.sha256[:8]}: expected CONFLICTING row not found")


if __name__ == "__main__":
    report = self_test()
    if not print_self_test(report):
        print()
        print("STOP CONDITION: self-test failed on a known pair. Not running on real documents.")
        sys.exit(1)

    run_id, results = run_extraction()
    values_path, checksums_path = write_run(run_id, results)
    print()
    print(f"run_id: {run_id}")
    print(f"artifacts processed: {len(results)}")
    for res in results:
        if res.error:
            print(f"  ERROR {res.sha256[:8]}: {res.error}")

    exit_code = self_verify(values_path, checksums_path)
    report_cross_checks(results)
    report_acceptance_test(results)
    sys.exit(exit_code)
