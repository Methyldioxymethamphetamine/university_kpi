"""Unit tests for classify/'s routing logic -- the char/image threshold and
the mixed-mode aggregation rule (P6 in notes/methodology.md's pattern
catalogue). No PDF/HTML fixtures needed; these operate on the small,
crafted inputs the routing functions actually consume.
"""
from __future__ import annotations

from classify import sniff
from classify.html_profile import HtmlProfile
from classify.labels import (
    HTML_TABLE,
    JSON_API,
    OFFICE_DOC,
    PAGE_CHAR_THRESHOLD,
    PDF_DIGITAL,
    PDF_MIXED,
    PDF_SCAN,
    UNKNOWN,
    classify_artifact_label,
    classify_page,
    classify_pdf_document,
)
from classify.pdf_profile import PageProfile


def test_page_char_threshold_boundary():
    assert classify_page(chars=PAGE_CHAR_THRESHOLD, images=5) == "digital"
    assert classify_page(chars=PAGE_CHAR_THRESHOLD - 1, images=1) == "scan"


def test_low_chars_without_images_is_not_a_scan():
    # A near-blank digital page (e.g. a divider) is not a scanned page --
    # there is nothing to OCR.
    assert classify_page(chars=0, images=0) == "digital"


def test_all_digital_pages_yield_pdf_digital():
    pages = [PageProfile(page_no=i, chars=2000, images=0, rotation=90) for i in range(1, 5)]
    label, per_page = classify_pdf_document(pages)
    assert label == PDF_DIGITAL
    assert per_page == ["digital"] * 4


def test_all_scan_pages_yield_pdf_scan():
    pages = [PageProfile(page_no=i, chars=10, images=1, rotation=0) for i in range(1, 4)]
    label, _ = classify_pdf_document(pages)
    assert label == PDF_SCAN


def test_some_scan_pages_yield_pdf_mixed():
    pages = [
        PageProfile(page_no=1, chars=2000, images=0, rotation=0),
        PageProfile(page_no=2, chars=5, images=1, rotation=0),
    ]
    label, per_page = classify_pdf_document(pages)
    assert label == PDF_MIXED
    assert per_page == ["digital", "scan"]


def test_html_with_table_is_html_table():
    profile = HtmlProfile(chars=1000, images=2, has_table=True)
    assert classify_artifact_label(sniff.HTML, html_profile=profile) == HTML_TABLE


def test_html_without_table_is_unknown():
    profile = HtmlProfile(chars=1000, images=2, has_table=False)
    assert classify_artifact_label(sniff.HTML, html_profile=profile) == UNKNOWN


def test_json_is_json_api():
    assert classify_artifact_label(sniff.JSON) == JSON_API


def test_docx_is_office_doc():
    assert classify_artifact_label(sniff.DOCX) == OFFICE_DOC


def test_unrecognised_mime_is_unknown():
    assert classify_artifact_label("application/x-nonsense") == UNKNOWN
    assert classify_artifact_label(None) == UNKNOWN


def test_sniff_pdf_magic_bytes():
    assert sniff.sniff_mime(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj") == sniff.PDF


def test_sniff_html_doctype():
    assert sniff.sniff_mime(b"<!doctype html>\n<html><body>hi</body></html>") == sniff.HTML


def test_sniff_json_object_and_array():
    assert sniff.sniff_mime(b'{"a": 1}') == sniff.JSON
    assert sniff.sniff_mime(b"[1, 2, 3]") == sniff.JSON


def test_sniff_unrecognised_bytes_returns_none():
    assert sniff.sniff_mime(b"\x00\x01\x02garbage") is None


def test_sniff_ignores_leading_whitespace_and_bom():
    assert sniff.sniff_mime(b"\xef\xbb\xbf   <!doctype html><html></html>") == sniff.HTML
