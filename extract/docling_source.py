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
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"

# Academic-year-shaped column header, e.g. "2023-24". [ASSUMED] fitted on
# IIT Bombay's NIRF forms; a calendar-year-only source (plain "2024") would
# need a second pattern -- left unrecognised (period_type=None) rather than
# guessed, consistent with P-9 ("never store year as a bare integer" cuts
# both ways: never *invent* a period_type either).
from extract.sections import detect_table_sections

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
    section: str | None = None
    sub_block: str | None = None
    anomaly_reason: str | None = None

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


_KNOWN_SUBHEADERS = {
    "utilised amount",
    "annual operational expenditure",
    "annual capital expenditure on academic activities and resources (excluding expenditure on buildings)",
    "no. of ph.d students graduated (including integrated ph.d)",
}


def iter_table_cells(sha256: str, docling_doc: dict) -> list[TableCell]:
    """Every cell of every table, tagged with its role and detected section.
    Does not filter header/label cells out -- callers decide what to do with
    each role."""
    cells: list[TableCell] = []
    table_sections = detect_table_sections(docling_doc)

    # Track column labels across table splits: (section, sub_block) -> (src_table_ref, n_cols, col_labels)
    prev_col_labels_by_sec: dict[tuple[str | None, str | None], tuple[str, int, list[str | None]]] = {}

    for table in docling_doc.get("tables", []):
        table_ref = table.get("self_ref", "?")
        sec_tag = table_sections.get(table_ref)
        section = sec_tag.section_label if sec_tag else None
        sub_block = sec_tag.sub_block if sec_tag else None

        prov = table.get("prov") or []
        page_no = prov[0].get("page_no") if prov else None
        grid = table.get("data", {}).get("grid", [])
        if not grid:
            continue

        n_cols = len(grid[0]) if grid else 0
        header_rows = [ri for ri, row in enumerate(grid) if row and all(c.get("column_header") for c in row)]
        header_row_idx = header_rows[0] if len(header_rows) == 1 else None

        col_labels: list[str | None] | None = None
        table_anomaly_reason: str | None = None
        if header_row_idx is not None:
            col_labels = [c.get("text") for c in grid[header_row_idx]]
            if section and section != "UNMATCHED":
                prev_col_labels_by_sec[(section, sub_block)] = (table_ref, n_cols, col_labels)
        else:
            # Continuation table across a page break (Docling split the table,
            # leaving subsequent pages without an explicit header row).
            # Require exact n_cols match and recognized section to prevent silent misalignment.
            key = (section, sub_block)
            if section and section != "UNMATCHED" and key in prev_col_labels_by_sec:
                src_ref, src_n_cols, src_labels = prev_col_labels_by_sec[key]
                if n_cols == src_n_cols:
                    col_labels = src_labels
                else:
                    logger.warning(
                        "Continuation table column count mismatch: %s (%d cols) vs source %s (%d cols) under %s; refusing silent positional alignment",
                        table_ref, n_cols, src_ref, src_n_cols, key,
                    )
                    table_anomaly_reason = "continuation_column_count_mismatch"

        for ri, row in enumerate(grid):
            # Check if this row is a sub-header row (e.g. 'Utilised Amount', PhD subheaders)
            non_empty_texts = [c.get("text", "").strip() for c in row if c.get("text", "").strip()]
            is_sub_header_row = False
            if non_empty_texts:
                first_lower = non_empty_texts[0].lower()
                if len(set(t.lower() for t in non_empty_texts)) == 1 and first_lower in _KNOWN_SUBHEADERS:
                    is_sub_header_row = True
                elif any(c.get("column_header") for c in row) and all(c.get("column_header") or not c.get("text", "").strip() for c in row):
                    is_sub_header_row = True

            row_label = row[0].get("text") if row else None
            for ci, cell in enumerate(row):
                is_ch = (
                    bool(cell.get("column_header"))
                    or is_sub_header_row
                    or (header_row_idx is not None and ri == header_row_idx)
                )
                column_label = None
                if not is_ch and col_labels and ci < len(col_labels):
                    column_label = col_labels[ci]
                period_type, period_value = _classify_period(column_label)
                bbox = cell.get("bbox")
                cells.append(
                    TableCell(
                        sha256=sha256,
                        table_ref=table_ref,
                        row_index=ri,
                        col_index=ci,
                        text=cell.get("text", ""),
                        is_column_header=is_ch,
                        is_row_header=bool(cell.get("row_header")),
                        page_no=page_no,
                        bbox=bbox,
                        row_label=row_label,
                        column_label=column_label,
                        period_type=period_type,
                        period_value=period_value,
                        section=section,
                        sub_block=sub_block,
                        anomaly_reason=table_anomaly_reason,
                    )
                )
    return cells
