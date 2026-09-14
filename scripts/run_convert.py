#!/usr/bin/env python3
"""Convert every classified artifact whose label iteration 1 handles, then
self-verify by RE-READING docs/ from disk (P-10 discipline: the check must
open what was actually written, not trust the in-memory run).

Usage:
    python scripts/run_convert.py

Exits non-zero if any docling.json is missing/unparseable for a converted
artifact, or if any doc item is missing page_no/bbox on a pdf_* artifact
(html_table artifacts have no page/bbox concept -- see NOTE in
scripts/run_convert.py:self_verify -- so they are reported separately and do
not trip the exit code), or if the P1 regression check failed.
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from convert.artifact import ConversionSkipped, convert_artifact  # noqa: E402
from classify.artifact import iter_manifest_shas  # noqa: E402
from classify.labels import HTML_TABLE, PDF_DIGITAL, PDF_MIXED, PDF_SCAN  # noqa: E402

PDF_LABELS = {PDF_DIGITAL, PDF_MIXED, PDF_SCAN}


def run_convert() -> list[tuple[str, str, str | None]]:
    """Returns (sha256, outcome, detail) where outcome is one of
    'converted' / 'skipped' / 'error'."""
    results = []
    for sha256 in iter_manifest_shas():
        try:
            convert_artifact(sha256)
            results.append((sha256, "converted", None))
        except ConversionSkipped as exc:
            results.append((sha256, "skipped", str(exc)))
        except Exception as exc:  # noqa: BLE001 -- reported, not swallowed
            results.append((sha256, "error", f"{type(exc).__name__}: {exc}"))
    return results


def self_verify(results: list[tuple[str, str, str | None]]) -> int:
    print("=== P2B convert self-verification (re-read from disk) ===")

    converted = [sha for sha, outcome, _ in results if outcome == "converted"]
    skipped = [(sha, detail) for sha, outcome, detail in results if outcome == "skipped"]
    errored = [(sha, detail) for sha, outcome, detail in results if outcome == "error"]

    print(f"artifacts converted: {len(converted)}")
    print(f"artifacts skipped (out of iteration-1 scope): {len(skipped)}")
    print(f"artifacts errored: {len(errored)}")
    for sha, detail in errored:
        print(f"  ERROR {sha}: {detail}")

    label_dist: Counter = Counter()
    missing_or_unparseable = []
    items_without_prov_pdf = 0
    items_without_prov_html = 0
    zero_text_pages = []
    p1_regression_failed = []

    for sha256 in converted:
        manifest_path = REPO_ROOT / "docs" / sha256[:8] / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        label = manifest["classify"]["label"]
        label_dist[label] += 1

        docling_json_path = REPO_ROOT / "docs" / sha256[:8] / "docling.json"
        if not docling_json_path.exists():
            missing_or_unparseable.append((sha256, "missing"))
            continue
        try:
            doc = json.loads(docling_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            missing_or_unparseable.append((sha256, f"unparseable: {exc}"))
            continue

        is_pdf = label in PDF_LABELS
        for item in doc.get("texts", []) + doc.get("tables", []) + doc.get("pictures", []):
            prov = item.get("prov") or []
            has_prov = bool(prov) and all(p.get("page_no") is not None and p.get("bbox") is not None for p in prov)
            if not has_prov:
                if is_pdf:
                    items_without_prov_pdf += 1
                else:
                    items_without_prov_html += 1

        if is_pdf:
            n_pages = manifest["convert"]["n_pages"]
            text_by_page = {p: 0 for p in range(1, n_pages + 1)}
            for item in doc.get("texts", []):
                for p in item.get("prov") or []:
                    page_no = p.get("page_no")
                    text_len = len(item.get("text", ""))
                    if page_no in text_by_page:
                        text_by_page[page_no] += text_len
            for page_no, total_chars in text_by_page.items():
                if total_chars == 0:
                    zero_text_pages.append(f"{sha256[:8]}/page{page_no:03d}")

        regression = manifest["convert"].get("p1_regression_check")
        if regression and regression["status"] != "PASS":
            p1_regression_failed.append((sha256, regression))

    print(f"label distribution (converted only): {dict(label_dist)}")
    print(f"pages with zero extracted text (pdf_* only): {len(zero_text_pages)}")
    for p in zero_text_pages:
        print(f"  - {p}")
    print(f"docling.json missing or unparseable: {len(missing_or_unparseable)}")
    for sha, why in missing_or_unparseable:
        print(f"  - {sha}: {why}")
    print(f"doc items lacking page_no/bbox (pdf_* labels -- HARD FAILURE gate): {items_without_prov_pdf}")
    # NOTE: html_table artifacts (MIT's Common Data Set) have no page/bbox
    # concept -- Docling's HTML backend produces prov=[] for every item,
    # confirmed empirically (docling==2.127.0, this session). That is
    # inherent to HTML, not a defect, so it is reported for visibility but
    # does NOT trip the exit code the way a PDF item missing provenance
    # would -- a PDF losing page_no/bbox is exactly CLAUDE.md's rotation
    # failure in a new costume; an HTML doc never having it is not.
    print(f"doc items lacking page_no/bbox (html_table labels -- reported only, not gated): {items_without_prov_html}")
    print(f"P1 regression check failures: {len(p1_regression_failed)}")
    for sha, regression in p1_regression_failed:
        print(f"  - {sha}: {regression}")

    hard_failure = bool(missing_or_unparseable) or items_without_prov_pdf > 0 or bool(p1_regression_failed) or bool(errored)
    print("SELF-VERIFICATION: " + ("FAIL" if hard_failure else "PASS"))
    return 1 if hard_failure else 0


if __name__ == "__main__":
    results = run_convert()
    sys.exit(self_verify(results))
