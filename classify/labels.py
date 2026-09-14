"""Routing labels. Recognise everything, handle only what iteration 1
needs (PROMPTS.md P2B) -- "unknown" is a first-class label and a work
queue, not a failure.
"""
from __future__ import annotations

from classify import sniff
from classify.html_profile import HtmlProfile
from classify.pdf_profile import PageProfile

PDF_DIGITAL = "pdf_digital"
PDF_MIXED = "pdf_mixed"
PDF_SCAN = "pdf_scan"
HTML_TABLE = "html_table"
JSON_API = "json_api"
OFFICE_DOC = "office_doc"
UNKNOWN = "unknown"

ALL_LABELS = (PDF_DIGITAL, PDF_MIXED, PDF_SCAN, HTML_TABLE, JSON_API, OFFICE_DOC, UNKNOWN)

# [ASSUMED] Fitted on ONE document: Sandip's Mandatory Disclosure PDF, during
# the P0-era structural diagnostic (notes/methodology.md P6 in the Sec9
# pattern catalogue: "Under ~200 extracted chars with images present -> OCR
# path"). Not re-fit here -- storing the raw (chars, images) pair per page
# alongside the derived label (see classify/artifact.py) means re-tuning this
# number later is a re-query over stored data, not a re-crawl. Confirmed or
# overturned by: running this threshold against a genuinely mixed-mode PDF
# once one is acquired (none of iteration 1's three institutions produced one
# so far -- IIT Bombay is fully digital per P1 CHECK B, 0 images/page).
PAGE_CHAR_THRESHOLD = 200


def classify_page(chars: int, images: int) -> str:
    """Per-page verdict: 'scan' iff the page looks like it needs OCR (P6:
    sparse or no extracted text AND at least one embedded image -- a text
    page that merely happens to be short, e.g. a title page, has no image
    and is not penalised). 'digital' otherwise."""
    if chars < PAGE_CHAR_THRESHOLD and images >= 1:
        return "scan"
    return "digital"


def classify_pdf_document(pages: list[PageProfile]) -> tuple[str, list[str]]:
    """Aggregate per-page verdicts into the document-level label, per P6
    ("Mixed-mode PDFs... decide per page")."""
    per_page = [classify_page(p.chars, p.images) for p in pages]
    if not per_page:
        return UNKNOWN, per_page
    scan_count = per_page.count("scan")
    if scan_count == 0:
        return PDF_DIGITAL, per_page
    if scan_count == len(per_page):
        return PDF_SCAN, per_page
    return PDF_MIXED, per_page


def classify_artifact_label(mime: str | None, *, html_profile: HtmlProfile | None = None) -> str:
    """Top-level MIME -> label routing for non-PDF artifacts. PDFs are
    handled by classify_pdf_document() above, since their label depends on
    per-page aggregation, not MIME alone."""
    if mime == sniff.PDF:
        raise ValueError("PDF routing goes through classify_pdf_document(), not this function")
    if mime == sniff.HTML:
        if html_profile is not None and html_profile.has_table:
            return HTML_TABLE
        # Recognised as HTML but has no <table> -- iteration 1 has no use
        # for a non-tabular HTML page (T3 in PROMPTS.md P2E exists precisely
        # to make sure a page like this yields zero values, not a guess).
        return UNKNOWN
    if mime == sniff.JSON:
        return JSON_API
    if mime in sniff.OFFICE_MIMES:
        return OFFICE_DOC
    return UNKNOWN
