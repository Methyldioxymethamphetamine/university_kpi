"""P2C STOP CONDITION: this must pass before the parser touches a real
document. Wraps extract.word_number.self_test() as pytest, plus explicit
regression tests for the two bugs V1 shipped (notes/methodology.md Sec6.3)."""
from __future__ import annotations

from extract.word_number import KNOWN_GOOD_PAIRS, parse_words_to_number, self_test


def test_self_test_passes():
    report = self_test()
    assert report.passed, report.all_rows()


def test_all_six_known_good_pairs_individually():
    for words, expected in KNOWN_GOOD_PAIRS:
        got = parse_words_to_number(words)
        assert got.value == expected, f"{words!r} -> {got.value}, expected {expected}"


def test_scale_absorption_ascending_scale_multiplies_running_total():
    # V1 bug: "One Thousand Four Hundred Sixty Crore" parsed as
    # 1000 + 460*crore instead of (1000+460)*crore.
    got = parse_words_to_number("One Thousand Four Hundred Sixty Crore")
    assert got.value == 1460 * 10_000_000


def test_idiom_abstains_instead_of_guessing():
    got = parse_words_to_number("Eight Fifty Six")
    assert got.value is None
    assert got.abstain_reason == "idiom"


def test_idiom_guard_does_not_false_trigger_on_hundred_between():
    # "Four Hundred Sixty" must NOT abstain -- "hundred" sits between the
    # ones and tens words, so this is composed arithmetic, not an idiom.
    got = parse_words_to_number("Four Hundred Sixty")
    assert got.value == 460
    assert got.abstain_reason is None


def test_misspelling_abstains_without_correction():
    got = parse_words_to_number("Six Hundered")
    assert got.value is None
    assert got.abstain_reason == "unparseable"


def test_plural_scale_words_and_filler_words():
    got = parse_words_to_number("Three Hundred Nine Crores Sixteen Lakhs Fifty Nine Thousand Four Hundred and Seventy Nine Only")
    assert got.value == 3091659479
