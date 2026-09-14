"""Per-page structural profile for a PDF, via pypdfium2 -- the tool P1's
CHECK B already verified against a known rotation value (CLAUDE.md stack
table). Mirrors the P1-era diagnostic described in notes/methodology.md
Sec2.4/2.9 ("page count, whether a text layer exists, how much text, how many
images"), now built as a reusable module instead of a one-off script.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium


@dataclass(frozen=True)
class PageProfile:
    page_no: int  # 1-indexed, matches Docling's page_no convention
    chars: int
    images: int
    rotation: int


def profile_pdf(path: Path) -> list[PageProfile]:
    """Open the PDF and, for every page, count text-layer characters and
    embedded image objects, and read the page rotation -- without invoking
    Docling. This is deliberately the same library and the same kind of
    per-object walk P1's CHECK B used to independently confirm rotation, so
    classify/'s numbers and convert/'s eventual Docling numbers are produced
    by two different code paths, not one path asserting against itself.
    """
    pdf = pdfium.PdfDocument(str(path))
    try:
        profiles = []
        for i, page in enumerate(pdf):
            textpage = page.get_textpage()
            chars = textpage.count_chars()
            n_images = sum(
                1 for obj in page.get_objects() if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE
            )
            rotation = page.get_rotation()
            profiles.append(PageProfile(page_no=i + 1, chars=chars, images=n_images, rotation=rotation))
        return profiles
    finally:
        pdf.close()


def render_page_png(path: Path, page_no: int, out_path: Path, scale: float = 1.5) -> None:
    """Render one page (1-indexed) to PNG for click-through, honouring
    rotation -- pypdfium2's render() bakes the page's declared rotation into
    the output bitmap, so a /Rotate 90 page comes out right-side-up, matching
    what CHECK B already established about this document's rotation."""
    pdf = pdfium.PdfDocument(str(path))
    try:
        page = pdf[page_no - 1]
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pil_image.save(out_path)
    finally:
        pdf.close()
