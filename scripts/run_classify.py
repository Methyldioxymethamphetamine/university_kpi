#!/usr/bin/env python3
"""Classify every acquired artifact (docs/*/manifest.json), then self-verify.

Usage:
    python scripts/run_classify.py

Exits non-zero if self-verification finds a raw file missing for a manifest,
or a classify record that failed to write.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from classify.artifact import classify_artifact, iter_manifest_shas  # noqa: E402


def run_classify() -> list[tuple[str, dict | None, str | None]]:
    """Returns (sha256, classify_record_or_None, error_or_None) per artifact."""
    results = []
    for sha256 in iter_manifest_shas():
        try:
            record = classify_artifact(sha256)
            results.append((sha256, record, None))
        except Exception as exc:  # noqa: BLE001 -- reported, not swallowed
            results.append((sha256, None, f"{type(exc).__name__}: {exc}"))
    return results


def self_verify(results: list[tuple[str, dict | None, str | None]]) -> int:
    print("=== P2B classify self-verification ===")
    print(f"artifacts classified: {len(results)}")

    label_dist: Counter = Counter()
    zero_text_pages = []
    errors = []
    for sha256, record, error in results:
        if error is not None:
            errors.append((sha256, error))
            continue
        label_dist[record["label"]] += 1
        pages_dir = REPO_ROOT / "docs" / sha256[:8] / "pages"
        for page_file in sorted(pages_dir.glob("*.json")):
            import json

            page = json.loads(page_file.read_text(encoding="utf-8"))
            if (page.get("chars") or 0) == 0:
                zero_text_pages.append(f"{sha256[:8]}/{page_file.name}")

    print(f"label distribution: {dict(label_dist)}")
    print(f"pages with zero extracted text: {len(zero_text_pages)}")
    for p in zero_text_pages:
        print(f"  - {p}")
    print(f"classify errors: {len(errors)}")
    for sha256, error in errors:
        print(f"  - {sha256}: {error}")

    if errors:
        print("SELF-VERIFICATION: FAIL (classify errors present)")
        return 1
    print("SELF-VERIFICATION: PASS")
    return 0


if __name__ == "__main__":
    results = run_classify()
    sys.exit(self_verify(results))
