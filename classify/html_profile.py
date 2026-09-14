"""Structural profile for an HTML artifact: text length, image count, and
whether a <table> exists. Uses the stdlib html.parser rather than adding a
new dependency (bs4/lxml) -- CLAUDE.md's stack table does not list an HTML
parser, and Docling itself is the real HTML content reader (convert/); this
module only needs enough structure to route the document, the same job
classify/pdf_profile.py does for PDFs with pypdfium2 instead of Docling.

HTML has no page/rotation concept, so the whole document is treated as one
synthetic page (page_no=1, rotation=None) for uniformity with the PDF
per-page shape that docs/<sha8>/pages/NNN.json expects.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass(frozen=True)
class HtmlProfile:
    chars: int
    images: int
    has_table: bool


class _StructuralScan(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chars = 0
        self.images = 0
        self.has_table = False
        self._skip_depth = 0  # inside <script> or <style>

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag == "img":
            self.images += 1
        elif tag == "table":
            self.has_table = True

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag == "img":
            self.images += 1
        elif tag == "table":
            self.has_table = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.chars += len(data.strip())


def profile_html(data: bytes) -> HtmlProfile:
    text = data.decode("utf-8", errors="replace")
    scanner = _StructuralScan()
    scanner.feed(text)
    scanner.close()
    return HtmlProfile(chars=scanner.chars, images=scanner.images, has_table=scanner.has_table)
