"""The digits/words checksum: three states, not two (P-7).

    digits == words        -> CONFIRMED
    digits != words        -> CONFLICTING   flag, retain both, never resolve
    words unparseable       -> UNVERIFIED    neither confirm nor accuse

There is no else-branch. build_checksum_row() is a total function over
{CONFIRMED, CONFLICTING, UNVERIFIED} with no fourth path and no fallthrough
that could turn "words unparseable" into "mismatch" -- that specific
collapse is what turned 18 of 418 word forms into false accusations in the
version this phase reimplements (notes/methodology.md Sec6.3).

Scans EVERY cell of every table for the digits(words) pattern, regardless of
Docling's column_header/row_header flags -- a checksum-relevant cell must
never be missed because a layout model mis-flagged it as a label.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from extract.docling_source import TableCell
from extract.word_number import parse_words_to_number

CONFIRMED = "CONFIRMED"
CONFLICTING = "CONFLICTING"
UNVERIFIED = "UNVERIFIED"

DIGITS_WORDS_RE = re.compile(r"(\d[\d,]{2,})\s*\(([^()]{4,220}?)\)")


@dataclass(frozen=True)
class ChecksumRow:
    sha256: str
    item_id: str
    page_no: int | None
    bbox: dict | None
    raw_value: str  # the whole "3750000(Three Lakh Seventy Five Thousand)" string, verbatim (P-6)
    raw_digits: str
    raw_words: str
    digits_value: int
    words_value: int | None
    abstain_reason: str | None
    state: str

    def __post_init__(self) -> None:
        if not self.sha256 or not self.item_id:
            raise ValueError(f"refusing to build a checksum row without sha256+item_id: {self!r}")
        if self.state not in (CONFIRMED, CONFLICTING, UNVERIFIED):
            raise ValueError(f"invalid checksum state {self.state!r} -- three states only, P-7")
        # The one invariant that must never break: UNVERIFIED iff the words
        # side abstained. An abstention can never produce CONFLICTING (that
        # would be an accusation with no evidence), and CONFIRMED/CONFLICTING
        # can never be reached without an actual parsed words_value.
        if (self.words_value is None) != (self.state == UNVERIFIED):
            raise ValueError(
                f"UNVERIFIED/abstain invariant broken: words_value={self.words_value!r} state={self.state!r} -- P-7 violation"
            )


def _determine_state(digits_value: int, words_value: int | None) -> str:
    if words_value is None:
        return UNVERIFIED
    if digits_value == words_value:
        return CONFIRMED
    return CONFLICTING


def build_checksum_row(cell: TableCell) -> ChecksumRow | None:
    """Returns None if this cell has no digits(words) pattern at all --
    that is not a checksum outcome, it's simply not a checksum-shaped cell."""
    m = DIGITS_WORDS_RE.search(cell.text)
    if m is None:
        return None

    raw_digits = m.group(1)
    raw_words = m.group(2).strip()
    digits_value = int(raw_digits.replace(",", ""))
    parsed = parse_words_to_number(raw_words)

    state = _determine_state(digits_value, parsed.value)

    return ChecksumRow(
        sha256=cell.sha256,
        item_id=cell.item_id,
        page_no=cell.page_no,
        bbox=cell.bbox,
        raw_value=cell.text,
        raw_digits=raw_digits,
        raw_words=raw_words,
        digits_value=digits_value,
        words_value=parsed.value,
        abstain_reason=parsed.abstain_reason,
        state=state,
    )


def build_checksum_rows(cells: list[TableCell]) -> list[ChecksumRow]:
    rows = []
    for cell in cells:
        row = build_checksum_row(cell)
        if row is not None:
            rows.append(row)
    return rows
