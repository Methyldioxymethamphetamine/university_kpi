"""Build value rows (values.jsonl) from docling table cells.

P-6: raw_value is the cell text verbatim, always, even when it is a
digits(words) compound -- normalized_value never substitutes for it.

P-8: "-" (dash), "" (empty) and "0" (zero) are three different things and
must not collapse into each other.

P-9: period_type travels with period_value on every row (both are None,
together, when the column header isn't year-shaped -- never invented).

Citation: a value row without sha256 + item_id is rejected at construction
time (raises), per PROMPTS.md P2C ("A value without a citation is not a
value; reject it at write time.").
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from extract.docling_source import TableCell

EMPTY = "EMPTY"
DASH = "DASH"
ZERO = "ZERO"
NUMBER = "NUMBER"
TEXT = "TEXT"

_DASH_RE = re.compile(r"^-+$")
_LEADING_NUMBER_RE = re.compile(r"^\s*(\d[\d,]*(?:\.\d+)?)")
_PURE_NUMBER_RE = re.compile(r"^\s*\d[\d,]*(?:\.\d+)?\s*$")
_HAS_WORD_FORM_RE = re.compile(r"\d[\d,]{2,}\s*\([^()]{4,220}?\)")


@dataclass(frozen=True)
class ValueRow:
    sha256: str
    item_id: str
    page_no: int | None
    bbox: dict | None
    table_ref: str
    row_index: int
    col_index: int
    row_label: str | None
    column_label: str | None
    period_type: str | None
    period_value: str | None
    raw_value: str
    dash_state: str
    normalized_value: float | None
    has_word_form: bool

    def __post_init__(self) -> None:
        # Citation-required-at-write-time: a value without sha256 + item_id
        # is not a value (PROMPTS.md P2C). Enforced here, not just at the
        # jsonl-writer, so nothing upstream can construct an uncited row.
        if not self.sha256 or not self.item_id:
            raise ValueError(f"refusing to build a value row without sha256+item_id: {self!r}")


def _classify(raw: str) -> tuple[str, float | None]:
    stripped = raw.strip()
    if stripped == "":
        return EMPTY, None
    if _DASH_RE.match(stripped):
        return DASH, None
    if _PURE_NUMBER_RE.match(stripped):
        n = float(stripped.replace(",", ""))
        return (ZERO, 0.0) if n == 0 else (NUMBER, n)
    # Not pure-numeric and not dash/empty: either plain text, or a
    # digits(words) compound. For the compound case, normalized_value is
    # the DIGITS reading only -- a mechanical parse of the leading numeric
    # token, never a words-vs-digits judgment (P-7: that judgment lives in
    # checksums.jsonl, never here).
    m = _LEADING_NUMBER_RE.match(stripped)
    if m:
        return TEXT, float(m.group(1).replace(",", ""))
    return TEXT, None


def build_value_row(cell: TableCell) -> ValueRow | None:
    """Returns None for a cell that is a label, not a value (a column
    header or a row header, per Docling's own layout flags -- P-14: role
    comes from geometry/layout, not from matching the cell's text)."""
    if cell.is_column_header or cell.is_row_header:
        return None
    if cell.col_index == 0:
        # Column 0 is treated as row-label context, not a value, even when
        # TableFormer didn't flag it row_header (observed: it often isn't --
        # see gate/P2C-extract.md). This is a geometric convention (first
        # column = label), not a text match.
        return None

    dash_state, normalized_value = _classify(cell.text)
    has_word_form = bool(_HAS_WORD_FORM_RE.search(cell.text))

    return ValueRow(
        sha256=cell.sha256,
        item_id=cell.item_id,
        page_no=cell.page_no,
        bbox=cell.bbox,
        table_ref=cell.table_ref,
        row_index=cell.row_index,
        col_index=cell.col_index,
        row_label=cell.row_label,
        column_label=cell.column_label,
        period_type=cell.period_type,
        period_value=cell.period_value,
        raw_value=cell.text,
        dash_state=dash_state,
        normalized_value=normalized_value,
        has_word_form=has_word_form,
    )


def build_value_rows(cells: list[TableCell]) -> list[ValueRow]:
    rows = []
    for cell in cells:
        row = build_value_row(cell)
        if row is not None:
            rows.append(row)
    return rows
