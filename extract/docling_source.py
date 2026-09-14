"""Read table-grid cells out of docs/<sha8>/docling.json.

This is the PRIMARY source of both value rows and digits(words) checksum
pairs -- see extract/pdf_geometry.py's module docstring for why: Docling's
TableFormer already reassembles a wrapped cell into one contiguous
`cell["text"]` string, with page_no + bbox from the table's own `prov`.
[VERIFIED, this session, on both IIT Bombay documents currently converted.]

Geometry only, no label-text mapping (P-14): a cell's ROLE (value vs. label)
is read from Docling's own `column_header` / `row_header` flags, which come
from TableFormer's layout model, not from matching any cell's text against a
KPI dictionary. No kpi_code is assigned anywhere in this module -- P2C is
forbidden from mapping/profile work.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"

# Academic-year-shaped column header, e.g. "2023-24". [ASSUMED] fitted on
# IIT Bombay's NIRF forms; a calendar-year-only source (plain "2024") would
# need a second pattern -- left unrecognised (period_type=None) rather than
# guessed, consistent with P-9 ("never store year as a bare integer" cuts
# both ways: never *invent* a period_type either).
_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}-\d{2,4}$")
_CALENDAR_YEAR_RE = re.compile(r"^(19|20)\d{2}$")


@dataclass(frozen=True)
class TableCell:
    sha256: str
    table_ref: str  # docling self_ref, e.g. "#/tables/3"
    row_index: int
    col_index: int
    text: str
    is_column_header: bool
    is_row_header: bool
    page_no: int | None
    bbox: dict | None
    row_label: str | None  # grid[row][0].text, for human context only
    column_label: str | None  # grid[header_row][col].text, for human context only
    period_type: str | None
    period_value: str | None

    @property
    def item_id(self) -> str:
        return f"{self.sha256}:{self.table_ref}:r{self.row_index}c{self.col_index}"


def _classify_period(column_label: str | None) -> tuple[str | None, str | None]:
    if column_label is None:
        return None, None
    label = column_label.strip()
    if _ACADEMIC_YEAR_RE.match(label):
        return "academic_year", label
    if _CALENDAR_YEAR_RE.match(label):
        return "calendar_year", label
    return None, None


def load_docling_json(sha256: str) -> dict | None:
    path = DOCS_ROOT / sha256[:8] / "docling.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def iter_table_cells(sha256: str, docling_doc: dict) -> list[TableCell]:
    """Every cell of every table, tagged with its role. Does not filter
    header/label cells out -- callers decide what to do with each role
    (extract/values.py skips them for value rows but extract/checksums.py
    scans every cell regardless of role, since a digits(words) pattern must
    never be missed just because TableFormer's layout model happened to
    flag that particular cell as a header)."""
    cells: list[TableCell] = []
    for table in docling_doc.get("tables", []):
        table_ref = table.get("self_ref", "?")
        prov = table.get("prov") or []
        page_no = prov[0].get("page_no") if prov else None
        grid = table.get("data", {}).get("grid", [])
        if not grid:
            continue

        header_rows = [ri for ri, row in enumerate(grid) if row and all(c.get("column_header") for c in row)]
        header_row_idx = header_rows[0] if len(header_rows) == 1 else None

        for ri, row in enumerate(grid):
            row_label = row[0].get("text") if row else None
            for ci, cell in enumerate(row):
                column_label = None
                if header_row_idx is not None and ri != header_row_idx and ci < len(grid[header_row_idx]):
                    column_label = grid[header_row_idx][ci].get("text")
                period_type, period_value = _classify_period(column_label)
                bbox = cell.get("bbox")
                cells.append(
                    TableCell(
                        sha256=sha256,
                        table_ref=table_ref,
                        row_index=ri,
                        col_index=ci,
                        text=cell.get("text", ""),
                        is_column_header=bool(cell.get("column_header")),
                        is_row_header=bool(cell.get("row_header")),
                        page_no=page_no,
                        bbox=bbox,
                        row_label=row_label,
                        column_label=column_label,
                        period_type=period_type,
                        period_value=period_value,
                    )
                )
    return cells
