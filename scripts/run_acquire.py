#!/usr/bin/env python3
"""Run the acquisition crawl once, then self-verify (P-10, non-optional).

Usage:
    python scripts/run_acquire.py --run-id <id>

Exits non-zero if self-verification finds any mismatch between raw/ and the
manifests under docs/.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
import uuid
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def run_crawl(run_id: str) -> None:
    from scrapy.crawler import CrawlerProcess
    from scrapy.settings import Settings

    from acquire import settings as acquire_settings
    from acquire.spiders.sources import SourceSpider

    settings = Settings()
    settings.setmodule(acquire_settings)
    settings.set("JOBDIR", str(REPO_ROOT / "state" / run_id))

    process = CrawlerProcess(settings)
    process.crawl(SourceSpider, run_id=run_id)
    process.start()


def self_verify() -> int:
    """Re-open raw/ and every manifest; print the required distributions
    (file count, total bytes, distinct sha256 count, http_status
    distribution, any manifest row whose referenced file is missing).
    Any mismatch is a hard failure that exits non-zero."""
    raw_files = [Path(p) for p in glob.glob(str(REPO_ROOT / "raw/sha256/*/*/*")) if Path(p).is_file()]
    total_bytes = sum(p.stat().st_size for p in raw_files)
    sha_by_path = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in raw_files}
    disk_shas_by_prefix: dict[str, list[Path]] = {}
    for p in raw_files:
        disk_shas_by_prefix.setdefault(p.name.split(".")[0], []).append(p)

    manifests = []
    for mp in glob.glob(str(REPO_ROOT / "docs/*/manifest.json")):
        with open(mp, encoding="utf-8") as f:
            manifests.append(json.load(f))

    http_status_counter: Counter = Counter()
    missing_referenced_files = []
    hash_mismatches = []
    for doc in manifests:
        sha = doc["sha256"]
        for run in doc["runs"]:
            http_status_counter[run["http_status"]] += 1
        has_body_run = any(r["http_status"] != 304 for r in doc["runs"])
        matches = disk_shas_by_prefix.get(sha, [])
        if has_body_run and not matches:
            missing_referenced_files.append(sha)
        for p in matches:
            if sha_by_path[p] != sha:
                hash_mismatches.append(str(p))

    blocked = sorted(glob.glob(str(REPO_ROOT / "docs/_blocked/*.json")))

    print("=== P2A self-verification (P-10) ===")
    print(f"raw file count: {len(raw_files)}")
    print(f"raw total bytes: {total_bytes}")
    print(f"distinct sha256 (manifests under docs/): {len(manifests)}")
    print(f"distinct sha256 (filenames under raw/):  {len(disk_shas_by_prefix)}")
    print(f"http_status distribution (per run entry, all manifests): {dict(sorted(http_status_counter.items(), key=str))}")
    print(f"manifest sha256 with a body-bearing run but no raw file on disk: {missing_referenced_files}")
    print(f"raw files whose recomputed sha256 doesn't match their manifest: {hash_mismatches}")
    print(f"blocked/error attempts recorded (never silently skipped): {len(blocked)}")
    for b in blocked:
        print(f"  - {b}")

    ok = not missing_referenced_files and not hash_mismatches
    print("SELF-VERIFICATION:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    run_id = args.run_id or f"run-{uuid.uuid4().hex[:8]}"
    print(f"=== acquisition run: {run_id} ===")
    run_crawl(run_id)
    return self_verify()


if __name__ == "__main__":
    raise SystemExit(main())
