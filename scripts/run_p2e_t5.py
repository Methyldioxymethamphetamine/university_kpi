"""PROMPTS.md P2E, T5: Same URL twice.
EXPECT: identical sha256, no new raw/ file, new manifest row, no new value
rows unless content changed.

Two independent checks, both against real re-runs, not asserted from
memory:

  1. A genuine second live fetch of the T3 fixture URL (swarthmore.edu),
     right now -- reusing the exact fetch_and_store() path scripts/
     run_p2e_t3.py already used once. Confirms sha256/raw-file/manifest-row
     behaviour at the acquisition layer P2E sits downstream of.

  2. Running profiles/engine.py's fingerprint+extraction TWICE over the
     same already-converted sha256 (IIT Bombay 2025, e9a1d469) and diffing
     the two runs field-for-field. This is the P2E-layer half of the test:
     confirms the profile engine is a pure function of docling.json, so
     re-processing an unchanged artifact can never mint duplicate or
     differing value/checksum rows on its own.
"""
from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from extract.docling_source import load_docling_json  # noqa: E402
from profiles.engine import run_profile  # noqa: E402
import scripts.run_p2e_t3 as t3  # noqa: E402

IITB_2025_SHA256 = "e9a1d469ba17262f052948f22d8a15b6f4c37a4646af72efea77e0a7e0b1e019"


def check_1_live_refetch() -> bool:
    print("=== T5 check 1: live re-fetch of the T3 URL ===")
    raw_root = REPO_ROOT / "raw" / "sha256"
    before_files = set(p for p in raw_root.rglob("*") if p.is_file())
    sha256 = t3.fetch_and_store()
    after_files = set(p for p in raw_root.rglob("*") if p.is_file())
    new_files = after_files - before_files

    manifest_path = REPO_ROOT / "docs" / sha256[:8] / "manifest.json"
    import json
    manifest = json.loads(manifest_path.read_text())
    run_ids = [r["run_id"] for r in manifest["runs"]]

    print(f"sha256: {sha256[:8]}...")
    print(f"new raw/ files created by this fetch: {len(new_files)} (expected 0)")
    print(f"manifest run entries so far: {run_ids} (expected >=2 identical-URL entries after two runs)")
    ok = len(new_files) == 0 and run_ids.count("p2e-t3") >= 2
    print(f"check 1: {'PASS' if ok else 'FAIL'}")
    return ok


def check_2_extraction_determinism() -> bool:
    print("\n=== T5 check 2: re-processing the same sha256 is deterministic, no duplication ===")
    doc = load_docling_json(IITB_2025_SHA256)
    run_a = run_profile("nirf_submission_v2020_2026", IITB_2025_SHA256, doc)
    run_b = run_profile("nirf_submission_v2020_2026", IITB_2025_SHA256, doc)

    va = [asdict(r) for r in run_a.value_rows]
    vb = [asdict(r) for r in run_b.value_rows]
    ca = [asdict(r) for r in run_a.checksum_rows]
    cb = [asdict(r) for r in run_b.checksum_rows]

    print(f"run A: {len(va)} value rows, {len(ca)} checksum rows")
    print(f"run B: {len(vb)} value rows, {len(cb)} checksum rows")
    identical = va == vb and ca == cb
    print(f"run A == run B, field for field: {identical}")
    print(f"check 2: {'PASS' if identical else 'FAIL'}")
    return identical


def main() -> None:
    ok1 = check_1_live_refetch()
    ok2 = check_2_extraction_determinism()
    print(f"\nT5: {'PASS' if ok1 and ok2 else 'FAIL'}")


if __name__ == "__main__":
    main()
