"""Independent, raw-geometry digits(words) pair extraction via pypdfium2.

WHY THIS EXISTS ALONGSIDE docling_source.py, NOT INSTEAD OF IT:

notes/methodology.md Sec6.1 describes a cell-reassembly problem: word forms
wrap across two or three lines, and a line-by-line reader finds
"3750000(Three Lakh" with no closing bracket. That problem was real for the
ORIGINAL prototype, which read raw pdf.js text items directly (no table
structure model at all).

[VERIFIED, this session] In THIS pipeline, docs/<sha8>/docling.json's table
cells (Docling's TableFormer output) already carry the fully-reassembled
string, e.g. "1880000(Eighteen Lakhs Eighty Thousand)" as ONE cell.text
value, with page_no+bbox from the table's own prov. Checked directly against
58 such cells across IIT Bombay's 2024 and 2025 documents -- every one is a
complete, well-formed digits(words) string, not a truncated fragment. This
is also exactly what P1 CHECK B/C already established
(spike/check_c_citation_survival.py, gate/P1-spike.md): the digits(words)
cell survives Docling conversion as one contiguous string.

So docling_source.py is the PRIMARY extraction path for checksum pairs, not
this module. This module exists to satisfy P-11 ("hand-verify against the
raw text runs via pypdfium2") with an actually-independent second method,
not a second read of the same Docling output. [VERIFIED, this session]
pypdfium2's own textpage.get_rect() does NOT reassemble a wrapped cell either
-- dumping raw rects for the same 3 cells above reproduces the exact
fragmentation the methodology describes:

    '1880000(Eighteen'   (rect starting the cell)
    'Lakhs Eighty'         (wrapped continuation, same column)
    'Thousand)'             (wrapped continuation, same column)

So the cluster-by-column/read-down/break-on-vertical-gap algorithm PROMPTS.md
P2C mandates is implemented here, against raw pypdfium2 rects, and used as
the cross-check pipeline.py runs before ANY digits(words) row from
docling_source.py is written to checksums.jsonl.

TUNING CONSTANTS [ASSUMED]: COLUMN_GAP_TOLERANCE and MAX_VERTICAL_GAP were
fitted by inspecting raw rects for IIT Bombay 2025 Overall (sha256
e9a1d469...), pages 1-2. Within one wrapped cell, the left edge drifts by
up to ~0.9pt between lines (e.g. 220.2 -> 219.6) and the vertical gap
between lines is ~0.4-7pt; between two unrelated cells in adjacent columns,
the left edge jumps by >100pt and/or the vertical gap exceeds ~10pt. An
earlier version of this module bucketed columns by rounding
`left / 8` to a fixed grid, which put 220.2 and 219.6 in DIFFERENT buckets
(they straddle a rounding boundary) and silently dropped 4 of 29 known
digits(words) cells -- caught only because this module's own output was
cross-checked against docling_source.py's count before being trusted (the
check this module exists to perform, applied to itself). Fixed by chaining
on the GAP to the previous rect in sorted-by-left order instead of a fixed
grid, which tolerates the intra-cell drift without a boundary artifact. A
differently-typeset NIRF form would need these re-fit -- see
gate/P2C-extract.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium

# [ASSUMED] fitted on IIT Bombay 2025 Overall, pages 1-2 -- see module docstring.
COLUMN_GAP_TOLERANCE = 15.0
MAX_VERTICAL_GAP = 10.0

DIGITS_WORDS_RE = re.compile(r"(\d[\d,]{2,})\s*\(([^()]{4,220}?)\)")


@dataclass(frozen=True)
class GeometricPair:
    page_no: int
    digits: str
    words: str
    cluster_text: str


def _cluster_page(rects: list[tuple[float, float, float, float, str]]) -> list[str]:
    """rects: (top, left, bottom, right, text) as returned by pypdfium2's
    get_rect() for this page -- [VERIFIED, this session] this ordering
    already reads in document order (increasing 'top' = down the page) for
    this /Rotate 90 document; pypdfium2's high-level rect API returns
    rotation-corrected coordinates, unlike the raw PDF transform matrix the
    original browser-side prototype had to un-rotate by hand (see
    notes/methodology.md Sec2.5). Confirmed by reproducing the known golden
    row (UG [4 Years Program(s)] / 1161/1059/1039/1030) directly from these
    rects during the P2C build session.

    Groups into columns by CHAINING on left-coordinate gap (sorted by left,
    a new column starts when the gap from the previous rect's left exceeds
    COLUMN_GAP_TOLERANCE) rather than a fixed rounding grid -- a grid has
    boundary artifacts that split two rects of nearly-identical left into
    different buckets (see module docstring). Within each column, sorts by
    top-coordinate (down the page) and starts a new cluster whenever the gap
    to the previous rect's bottom exceeds MAX_VERTICAL_GAP -- the mandated
    "cluster by column start, read down, break on a large vertical gap"
    algorithm."""
    non_empty = [r for r in rects if r[4].strip()]
    non_empty.sort(key=lambda r: r[1])  # by left

    columns: list[list[tuple[float, float, float, float, str]]] = []
    for r in non_empty:
        if columns and (r[1] - columns[-1][-1][1]) <= COLUMN_GAP_TOLERANCE:
            columns[-1].append(r)
        else:
            columns.append([r])

    clusters = []
    for col_rects in columns:
        col_rects.sort(key=lambda r: r[0])  # by top, down the page
        buf: list[str] = []
        last_bottom: float | None = None
        for top, _left, bottom, _right, text in col_rects:
            if last_bottom is not None and (top - last_bottom) > MAX_VERTICAL_GAP:
                if buf:
                    clusters.append(" ".join(buf))
                buf = []
            buf.append(text.strip())
            last_bottom = bottom
        if buf:
            clusters.append(" ".join(buf))
    return clusters


def extract_pairs(pdf_path: Path) -> list[GeometricPair]:
    """Independent (from Docling) extraction of digits(words) pairs, by
    reading raw pypdfium2 text rects and reassembling wrapped cells
    geometrically. Used only as a cross-check -- see module docstring."""
    pairs: list[GeometricPair] = []
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        for page_idx, page in enumerate(pdf):
            page_no = page_idx + 1
            textpage = page.get_textpage()
            rects = []
            for i in range(textpage.count_rects()):
                rect = textpage.get_rect(i)
                text = textpage.get_text_bounded(*rect)
                top, left, bottom, right = rect
                rects.append((top, left, bottom, right, text))
            for cluster_text in _cluster_page(rects):
                normalised = re.sub(r"\s+", " ", cluster_text).strip()
                for m in DIGITS_WORDS_RE.finditer(normalised):
                    pairs.append(
                        GeometricPair(page_no=page_no, digits=m.group(1), words=m.group(2).strip(), cluster_text=normalised)
                    )
    finally:
        pdf.close()
    return pairs
