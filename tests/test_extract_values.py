"""P-6 (raw verbatim), P-8 (empty/dash/zero distinct), P-9 (period_type
travels with period_value), and citation-required-at-write-time."""
from __future__ import annotations

import pytest

from extract.docling_source import TableCell
from extract.values import DASH, EMPTY, NUMBER, TEXT, ZERO, ValueRow, build_value_row


def _cell(text: str, *, row=1, col=1, is_col_hdr=False, is_row_hdr=False, sha256="deadbeef", table_ref="#/tables/0", period_type=None, period_value=None):
    return TableCell(
        sha256=sha256,
        table_ref=table_ref,
        row_index=row,
        col_index=col,
        text=text,
        is_column_header=is_col_hdr,
        is_row_header=is_row_hdr,
        page_no=1,
        bbox={"l": 0, "t": 0, "r": 1, "b": 1, "coord_origin": "TOPLEFT"},
        row_label="Some Row",
        column_label="2023-24",
        period_type=period_type,
        period_value=period_value,
    )


def test_p8_empty_dash_zero_are_distinct_states():
    assert build_value_row(_cell("")).dash_state == EMPTY
    assert build_value_row(_cell("-")).dash_state == DASH
    assert build_value_row(_cell("0")).dash_state == ZERO
    assert build_value_row(_cell("42")).dash_state == NUMBER

    assert build_value_row(_cell("")).normalized_value is None
    assert build_value_row(_cell("-")).normalized_value is None
    assert build_value_row(_cell("0")).normalized_value == 0.0
    assert build_value_row(_cell("42")).normalized_value == 42.0


def test_p6_raw_value_preserved_verbatim_for_digits_words_compound():
    row = build_value_row(_cell("3750000(Three Lakh Seventy Five Thousand)"))
    assert row.raw_value == "3750000(Three Lakh Seventy Five Thousand)"
    assert row.dash_state == TEXT
    assert row.has_word_form is True
    # normalized_value is the mechanical digit reading, not a judgment --
    # the digits/words conflict itself is checksums.jsonl's job, not this row's.
    assert row.normalized_value == 3750000.0


def test_p9_period_type_travels_with_period_value():
    row = build_value_row(_cell("100", period_type="academic_year", period_value="2023-24"))
    assert row.period_type == "academic_year"
    assert row.period_value == "2023-24"

    row_unknown = build_value_row(_cell("100", period_type=None, period_value=None))
    assert row_unknown.period_type is None
    assert row_unknown.period_value is None


def test_header_and_label_cells_produce_no_value_row():
    assert build_value_row(_cell("2023-24", is_col_hdr=True)) is None
    assert build_value_row(_cell("Some Label", col=0)) is None
    assert build_value_row(_cell("Some Row Header", is_row_hdr=True)) is None


def test_citation_required_at_write_time():
    with pytest.raises(ValueError):
        ValueRow(
            sha256="",
            item_id="",
            page_no=1,
            bbox=None,
            table_ref="#/tables/0",
            row_index=0,
            col_index=1,
            row_label=None,
            column_label=None,
            period_type=None,
            period_value=None,
            raw_value="42",
            dash_state=NUMBER,
            normalized_value=42.0,
            has_word_form=False,
        )
