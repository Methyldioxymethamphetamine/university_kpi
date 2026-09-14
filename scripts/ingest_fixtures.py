#!/usr/bin/env python3
"""Ingest all 8 NIRF test fixtures into raw/ and convert to docs/<sha8>/docling.json.

Ensures all 8 fixtures are first-class converted artifacts available to
the extraction pipeline.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from acquire import manifestlog
from acquire.storage import raw_path, sha256_of, write_once
from classify.artifact import classify_artifact
from convert.artifact import convert_artifact

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

VERIFIED_FIXTURE_NAMES = {
    "IR-E-C-16604": "Sri Sivasubramaniya Nadar College of Engineering",
    "IR-E-C-36995": "Sri Krishna College of Engineering and Technology",
    "IR-E-I-1074": "Indian Institute of Technology Delhi",
    "IR-E-I-1480": "Thapar Institute of Engineering and Technology",
    "IR-E-U-0391": "Birla Institute of Technology & Science - Pilani",
    "IR-E-U-0456": "Indian Institute of Technology Madras",
    "IR-O-U-0306": "Indian Institute of Technology Bombay",
}


def ingest_fixture(pdf_path: Path) -> str:
    content = pdf_path.read_bytes()
    sha256 = sha256_of(content)
    inst_code = pdf_path.stem.replace("_2024", "").replace("_2025", "")
    inst_name = VERIFIED_FIXTURE_NAMES.get(inst_code, f"Fixture {inst_code}")

    # 1. Raw storage
    out_raw = raw_path(sha256, "application/pdf")
    is_new = write_once(out_raw, content)

    # 2. Manifest
    run_entry = {
        "run_id": "fixture_ingest",
        "url": f"fixture://{pdf_path.name}",
        "http_status": 200,
        "content_type": "application/pdf",
        "content_length": len(content),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    manifestlog.append_run(
        sha256=sha256,
        source_id=f"nirf_{inst_code.lower()}",
        institution_code=inst_code,
        institution_name=inst_name,
        country="IN",
        canonical_url=f"fixture://{pdf_path.name}",
        period_type="academic_year",
        period_value=None,
        run_entry=run_entry,
    )

    # 3. Classify
    classify_artifact(sha256)

    # 4. Convert
    convert_artifact(sha256)

    return sha256


def main() -> None:
    pdf_files = sorted(FIXTURES_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} fixtures in {FIXTURES_DIR}")
    for p in pdf_files:
        sha = ingest_fixture(p)
        print(f"  {p.name:22} -> sha256={sha[:8]}...")


if __name__ == "__main__":
    main()
