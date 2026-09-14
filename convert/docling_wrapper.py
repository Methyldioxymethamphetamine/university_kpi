"""Docling conversion, save_as_json() only (P-2). Builds one DocumentConverter
per process (model loading is the expensive part) and exposes a single
convert_to_json() entry point used for every label convert/ handles.

OCR is explicitly disabled ([OPEN], not [ASSUMED] -- this is a real gap, not
a fitted constant). Iteration 1's three institutions produced no pdf_scan or
pdf_mixed artifact (IIT Bombay is pdf_digital per P1 CHECK B; MIT is HTML;
Sandip's PDF was never acquired -- blocked by robots.txt, gate/P2A-acquire.md
Sec3). Enabling OCR would mean shipping an unverified code path no acquired
document exercises. With OCR off, a genuinely scanned page still gets
converted -- Docling does not skip it -- but its extracted text comes back
empty, which the self-verification step (scripts/run_convert.py) surfaces as
"pages with zero extracted text" rather than hiding it behind a silently
wrong OCR guess. Turning OCR on is future work once a real pdf_scan/pdf_mixed
artifact exists to verify against.
"""
from __future__ import annotations

import json
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.document import DoclingDocument

_PDF_OPTIONS = PdfPipelineOptions()
_PDF_OPTIONS.do_ocr = False  # [OPEN] see module docstring
_PDF_OPTIONS.generate_picture_images = True  # docs/<sha8>/assets/, "none skipped"

_converter: DocumentConverter | None = None


def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        _converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=_PDF_OPTIONS)}
        )
    return _converter


def convert_to_docling_document(raw_path: Path) -> DoclingDocument:
    """Docling guesses format from the bytes themselves (filetype/magic-byte
    detection, see docling/datamodel/document.py._guess_format), not from
    `raw_path`'s extension -- consistent with classify/sniff.py's own rule
    of never trusting an extension. No format is forced here; classify/'s
    label already gated *whether* to call this function at all."""
    result = _get_converter().convert(str(raw_path))
    return result.document


def enrich_docling_json_with_rotation(
    out_path: Path, page_rotations: dict[int, int | None]
) -> None:
    """Enrich docling.json's pages with page_rotation (and rotation) metadata,
    matching how size is stored in docling.json's pages dict.
    """
    if not out_path.exists():
        return
    with open(out_path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    pages = doc.get("pages", {})
    for p_no, rot in page_rotations.items():
        key = str(p_no)
        if key in pages:
            pages[key]["page_rotation"] = rot
            pages[key]["rotation"] = rot
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)


def save_document_json(
    document: DoclingDocument,
    out_path: Path,
    page_rotations: dict[int, int | None] | None = None,
) -> None:
    """P-2: save_as_json() only. If you are tempted to add
    export_to_markdown()/export_to_html() here, don't -- tests/test_p2_no_lossy_export.py
    fails the build if either call appears anywhere under convert/."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    document.save_as_json(out_path)
    if page_rotations:
        enrich_docling_json_with_rotation(out_path, page_rotations)

