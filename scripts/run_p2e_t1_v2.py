"""P2E T1, re-run after the 2026-09-14 (v4) fingerprint fix
(profiles/nirf_submission_v2020_2026.yaml, fingerprint/matcher.py).

PROMPTS.md EXPECT: fingerprint hit, profile applies, ~29 values with
citations, 28-37 digits/words pairs checked, ZERO human input, seconds.

Unlike the original 2026-09-14 T1 entry (gate/P2E-profiles.md Sec3), which
could only test IIT Bombay's 2024 vs 2025 (same institution, different
year -- Sandip was still robots-blocked), this re-run has all 4 acquired
pdf_digital artifacts available: 2x IIT Bombay, 2x Sandip -- a genuine
second INSTITUTION, not just a second document. Compares every one against
P2C's own hand-written extraction (values/run=20260914T132113Z, the run
that includes both Sandip documents), same byte-identical methodology as
scripts/run_p2e_proof.py.
"""
from __future__ import annotations

import glob
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from extract.docling_source import load_docling_json  # noqa: E402
from fingerprint.matcher import match_document, MATCHED  # noqa: E402

VALUES_ROOT = REPO_ROOT / "values"

ARTIFACTS = {
    "IITB 2025": "e9a1d469ba17262f052948f22d8a15b6f4c37a4646af72efea77e0a7e0b1e019",
    "IITB 2024": "d2c9d5c22ad556adeb2f45764644df2bd6513a91f5ea4f62a9401dddb5e17445",
    "Sandip 2025": "2dcda6d8d43734464af3cd85cdac9af8d4cd41f00773aaf7fc5c7c7fba516eaf",
    "Sandip 2024": "27dafb4b6b7da5878f2cb0d266e26a9a659ba370b1e533baf19a8db96bba5047",
}

FIELDS_V = ["sha256", "item_id", "page_no", "bbox", "row_label", "column_label",
            "period_type", "period_value", "raw_value", "dash_state",
            "normalized_value", "has_word_form"]
FIELDS_C = ["sha256", "item_id", "page_no", "bbox", "raw_value", "raw_digits",
            "raw_words", "digits_value", "words_value", "abstain_reason", "state"]


def _latest_run_dir() -> Path:
    return Path(sorted(glob.glob(str(VALUES_ROOT / "run=*")))[-1])


def main() -> None:
    run_dir = _latest_run_dir()
    p2c_values = [json.loads(l) for l in (run_dir / "values.jsonl").read_text().splitlines() if l.strip()]
    p2c_checksums = [json.loads(l) for l in (run_dir / "checksums.jsonl").read_text().splitlines() if l.strip()]

    print(f"=== T1 re-run (post fingerprint-fix), against {run_dir.name} ===\n")

    t0 = time.monotonic()
    all_ok = True
    for label, sha256 in ARTIFACTS.items():
        doc = load_docling_json(sha256)
        fp = match_document(sha256, doc)
        matched = fp.outcome == MATCHED and fp.profile_id == "nirf_submission_v2020_2026"

        p2c_v = sorted((r for r in p2c_values if r["sha256"] == sha256), key=lambda r: r["item_id"])
        p2c_c = sorted((r for r in p2c_checksums if r["sha256"] == sha256), key=lambda r: r["item_id"])
        eng_v = sorted((asdict(r) for r in fp.run.value_rows), key=lambda r: r["item_id"]) if fp.run else []
        eng_c = sorted((asdict(r) for r in fp.run.checksum_rows), key=lambda r: r["item_id"]) if fp.run else []

        diffs = 0
        for a, b in zip(p2c_v, eng_v):
            if any(a.get(f) != b.get(f) for f in FIELDS_V):
                diffs += 1
        for a, b in zip(p2c_c, eng_c):
            if any(a.get(f) != b.get(f) for f in FIELDS_C):
                diffs += 1
        len_ok = len(p2c_v) == len(eng_v) and len(p2c_c) == len(eng_c)
        ok = matched and len_ok and diffs == 0
        all_ok = all_ok and ok

        band_ok = 28 <= len(eng_c) <= 37
        print(f"{label} ({sha256[:8]}): fingerprint={'MATCHED' if matched else fp.outcome} | "
              f"value_rows={len(eng_v)} | checksum_rows={len(eng_c)} "
              f"({'within 28-37' if band_ok else 'OUTSIDE 28-37'}) | "
              f"byte-identical to P2C={'yes' if (len_ok and diffs == 0) else f'NO ({diffs} field diffs)'}")

    elapsed = time.monotonic() - t0
    print(f"\nelapsed: {elapsed:.3f}s for all 4 documents, zero human input")
    print(f"\nT1 (all 4 pdf_digital artifacts, cross-institution): {'PASS' if all_ok else 'FAIL'}")


if __name__ == "__main__":
    main()
