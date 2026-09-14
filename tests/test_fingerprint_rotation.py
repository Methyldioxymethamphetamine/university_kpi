"""Tests enforcing page rotation in fingerprint matching (M1 fix).

CLAUDE.md / gate/P4-review.md M1:
The NIRF profile declares `page_rotation: 90`. Previously, `fingerprint_matches()`
skipped the rotation check because docling.json pages lacked rotation metadata,
allowing an unrotated document (rotation=0) with the NIRF text anchor to match.

This test verifies that:
1. A real PDF with page rotation = 90 matches `nirf_submission_v2020_2026`.
2. A non-rotated PDF (page rotation = 0) with the identical text anchor is REJECTED
   by `fingerprint_matches()`.
3. An un-annotated document (missing page_rotation) is REJECTED when rotation is required.
4. Profiles with `page_rotation: null` (e.g. US CDS HTML) match regardless of rotation.
"""
from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
import pytest

from classify.artifact import find_raw_path
from classify.pdf_profile import profile_pdf
from convert.docling_wrapper import convert_to_docling_document, save_document_json
from convert.regression import GOLDEN_SHA256
from profiles.engine import fingerprint_matches, load_profile


def test_nirf_profile_matches_rotated_pdf():
    """Real IIT Bombay PDF has /Rotate 90 on all pages and matches NIRF profile."""
    raw_path = find_raw_path(GOLDEN_SHA256)
    if raw_path is None:
        pytest.skip(f"Golden fixture sha256={GOLDEN_SHA256} not found under raw/")

    profile = load_profile("nirf_submission_v2020_2026")
    assert profile["fingerprint"]["page_rotation"] == 90

    # Profile the raw PDF to get per-page rotation
    page_profiles = profile_pdf(raw_path)
    page_rotations = {p.page_no: p.rotation for p in page_profiles}
    assert all(r == 90 for r in page_rotations.values())

    # Convert with Docling and enrich with rotation
    doc = convert_to_docling_document(raw_path)
    out_path = Path("/tmp/test_iitb_rotated_docling.json")
    save_document_json(doc, out_path, page_rotations=page_rotations)

    import json

    docling_doc = json.loads(out_path.read_text(encoding="utf-8"))

    # Assert rotation is present in pages metadata
    assert docling_doc["pages"]["1"]["page_rotation"] == 90

    # Assert fingerprint matches
    assert fingerprint_matches(profile, docling_doc) is True


def test_nirf_profile_rejects_unrotated_pdf(tmp_path: Path):
    """An unrotated PDF (rotation=0) with the NIRF text anchor must NOT match

    the NIRF profile because page_rotation: 90 is enforced.
    """
    raw_path = find_raw_path(GOLDEN_SHA256)
    if raw_path is None:
        pytest.skip(f"Golden fixture sha256={GOLDEN_SHA256} not found under raw/")

    profile = load_profile("nirf_submission_v2020_2026")
    assert profile["fingerprint"]["page_rotation"] == 90

    # Create an unrotated copy of the PDF (all pages set to rotation=0)
    pdf = pdfium.PdfDocument(str(raw_path))
    for page in pdf:
        page.set_rotation(0)
    unrotated_pdf_path = tmp_path / "iitb_unrotated.pdf"
    pdf.save(str(unrotated_pdf_path))
    pdf.close()

    # Confirm via pypdfium2 profile_pdf that rotation is 0
    page_profiles = profile_pdf(unrotated_pdf_path)
    page_rotations = {p.page_no: p.rotation for p in page_profiles}
    assert all(r == 0 for r in page_rotations.values())

    # Convert via Docling and enrich with rotation=0
    doc = convert_to_docling_document(unrotated_pdf_path)
    out_json = tmp_path / "unrotated_docling.json"
    save_document_json(doc, out_json, page_rotations=page_rotations)

    import json

    docling_doc = json.loads(out_json.read_text(encoding="utf-8"))

    # Verify that text anchor is still present in the document
    texts = [t.get("text", "") for t in docling_doc.get("texts", [])]
    assert any("IR-O-U-0306" in t for t in texts)
    assert docling_doc["pages"]["1"]["page_rotation"] == 0

    # The critical assertion: fingerprint MUST NOT match because rotation is 0 != 90
    assert fingerprint_matches(profile, docling_doc) is False


def test_fingerprint_rejects_missing_rotation_metadata():
    """If docling_doc pages lack page_rotation / rotation, a profile declaring

    page_rotation: 90 must reject it rather than silently passing.
    """
    profile = load_profile("nirf_submission_v2020_2026")
    dummy_doc = {
        "texts": [
            {
                "text": "Institute Name: Test Institute [IR-O-U-0001]",
                "prov": [{"page_no": 1, "bbox": {}}],
            }
        ],
        "pages": {
            "1": {"page_no": 1, "size": {"width": 842.0, "height": 595.0}}
            # Note: no page_rotation or rotation
        },
    }
    assert fingerprint_matches(profile, dummy_doc) is False


def test_fingerprint_matches_when_rotation_is_null():
    """Profiles with page_rotation: null (e.g. US CDS HTML) should match

    without requiring page rotation.
    """
    cds_profile = load_profile("us_cds_v2025")
    assert cds_profile["fingerprint"]["page_rotation"] is None

    dummy_doc = {
        "texts": [
            {
                "text": "Common Data Set 2024-2025",
                "prov": [{"page_no": 1}],
            }
        ],
        "pages": {
            "1": {"page_no": 1, "size": {"width": 800.0, "height": 600.0}, "page_rotation": None}
        },
    }
    assert fingerprint_matches(cds_profile, dummy_doc) is True
