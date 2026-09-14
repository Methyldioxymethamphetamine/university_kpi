"""Convert one classified artifact through Docling, per PROMPTS.md P2B.
Only runs for labels iteration 1 needs; everything else is left as a
classify-only manifest row (label + page records already written by
classify/artifact.py), which is the whole point of "unknown" being a work
queue, not a failure.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from classify.artifact import DOCS_ROOT, find_raw_path, manifest_path
from classify.labels import HTML_TABLE, PDF_DIGITAL, PDF_MIXED, PDF_SCAN
from convert.assets import extract_assets
from convert.docling_wrapper import convert_to_docling_document, save_document_json
from convert.regression import GOLDEN_SHA256, P1RegressionError, assert_check_b

CONVERTIBLE_LABELS = {PDF_DIGITAL, PDF_MIXED, PDF_SCAN, HTML_TABLE}


class ConversionSkipped(Exception):
    """Not an error -- raised for a document whose label iteration 1 does
    not convert, so the caller can record why without treating it as a
    failure."""


def convert_artifact(sha256: str) -> dict:
    manifest = json.loads(manifest_path(sha256).read_text(encoding="utf-8"))
    classify_record = manifest.get("classify")
    if classify_record is None:
        raise RuntimeError(f"sha256={sha256} has no classify record -- run scripts/run_classify.py first")

    label = classify_record["label"]
    if label not in CONVERTIBLE_LABELS:
        raise ConversionSkipped(f"label={label!r} is not in iteration 1's convert scope: {CONVERTIBLE_LABELS}")

    raw_path = find_raw_path(sha256)
    if raw_path is None:
        raise FileNotFoundError(f"no raw file found for sha256={sha256}")

    document = convert_to_docling_document(raw_path)

    doc_dir = DOCS_ROOT / sha256[:8]
    out_json = doc_dir / "docling.json"
    save_document_json(document, out_json)  # P-2: save_as_json() only

    written_assets = extract_assets(document, doc_dir / "assets")

    convert_record = {
        "docling_json": str(out_json.relative_to(DOCS_ROOT.parent)),
        "n_pages": len(document.pages),
        "n_texts": len(document.texts),
        "n_tables": len(document.tables),
        "n_pictures": len(document.pictures),
        "assets_extracted": len(written_assets),
        "converted_at": datetime.now(timezone.utc).isoformat(),
    }

    if sha256 == GOLDEN_SHA256:
        try:
            match = assert_check_b(document, sha256=sha256)
            convert_record["p1_regression_check"] = {"status": "PASS", **match}
        except P1RegressionError as exc:
            convert_record["p1_regression_check"] = {"status": "FAIL", "error": str(exc)}
            _write_convert_block(sha256, convert_record)
            raise

    _write_convert_block(sha256, convert_record)
    return convert_record


def _write_convert_block(sha256: str, convert_record: dict) -> None:
    path = manifest_path(sha256)
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    doc["convert"] = convert_record
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
