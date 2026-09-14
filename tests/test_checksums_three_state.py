"""P-7: three states, not two. A synthetic CONFLICTING case is included
deliberately -- the real, currently-available documents (IIT Bombay 2024 +
2025) happen to have ZERO digits/words disagreements (see
gate/P2C-extract.md), so without a synthetic case the CONFLICTING path
would be unexercised by any test against real data."""
from __future__ import annotations

import pytest

from extract.checksums import CONFIRMED, CONFLICTING, UNVERIFIED, ChecksumRow, build_checksum_row
from extract.docling_source import TableCell


def _cell(text: str):
    return TableCell(
        sha256="deadbeef",
        table_ref="#/tables/0",
        row_index=1,
        col_index=1,
        text=text,
        is_column_header=False,
        is_row_header=False,
        page_no=1,
        bbox={"l": 0, "t": 0, "r": 1, "b": 1, "coord_origin": "TOPLEFT"},
        row_label="Median Salary",
        column_label="2024-25",
        period_type="academic_year",
        period_value="2024-25",
    )


def test_confirmed_when_digits_equal_words():
    row = build_checksum_row(_cell("1880000(Eighteen Lakhs Eighty Thousand)"))
    assert row.state == CONFIRMED
    assert row.digits_value == row.words_value == 1880000


def test_conflicting_retains_both_values_never_resolves():
    # The project's headline case, reconstructed synthetically since Sandip's
    # document is not acquired (gate/P2A-acquire.md Sec3; gate/P2C-extract.md).
    row = build_checksum_row(_cell("3750000(Three Lakh Seventy Five Thousand)"))
    assert row.state == CONFLICTING
    assert row.digits_value == 3750000
    assert row.words_value == 375000
    # Both raw strings survive verbatim -- neither side is discarded or picked as "correct".
    assert row.raw_digits == "3750000"
    assert row.raw_words == "Three Lakh Seventy Five Thousand"
    assert row.raw_value == "3750000(Three Lakh Seventy Five Thousand)"


def test_unverified_on_idiom_abstention_not_conflicting():
    row = build_checksum_row(_cell("64000(Eight Fifty Six)"))
    assert row.state == UNVERIFIED
    assert row.words_value is None
    assert row.abstain_reason == "idiom"


def test_unverified_on_misspelling_not_conflicting():
    row = build_checksum_row(_cell("100000(Six Hundered)"))
    assert row.state == UNVERIFIED
    assert row.words_value is None


def test_no_pattern_returns_none_not_a_checksum_outcome():
    assert build_checksum_row(_cell("plain text, no pattern here")) is None
    assert build_checksum_row(_cell("42")) is None


def test_invariant_cannot_construct_unverified_state_with_a_words_value():
    with pytest.raises(ValueError):
        ChecksumRow(
            sha256="deadbeef",
            item_id="deadbeef:#/tables/0:r1c1",
            page_no=1,
            bbox=None,
            raw_value="100(One Hundred)",
            raw_digits="100",
            raw_words="One Hundred",
            digits_value=100,
            words_value=100,
            abstain_reason=None,
            state=UNVERIFIED,
        )


def test_invariant_cannot_construct_conflicting_state_with_no_words_value():
    with pytest.raises(ValueError):
        ChecksumRow(
            sha256="deadbeef",
            item_id="deadbeef:#/tables/0:r1c1",
            page_no=1,
            bbox=None,
            raw_value="100(Sevety)",
            raw_digits="100",
            raw_words="Sevety",
            digits_value=100,
            words_value=None,
            abstain_reason="unparseable",
            state=CONFLICTING,
        )
