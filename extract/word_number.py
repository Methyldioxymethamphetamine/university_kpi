"""Indian-numbering (lakh/crore) word-to-number parser.

Ported from the JS prototype in notes/methodology.md Sec6.3, which went
through two documented failed versions before this shape:

  V1 bug #1 (scale mis-absorption): "One Thousand Four Hundred Sixty Crore"
  parsed as 1000 + 460*crore instead of (1000+460)*crore = 1460 crore.
  Reported two false defects with ratios 3.17x / 2.61x -- caught because
  those ratios don't match any real transcription-error shape.

  V1 bug #2 (spoken idiom): "eight fifty six" (a unit 1-9 immediately
  followed by a tens word, no "hundred" between) is spoken English for 856,
  not 8+50+6=64. This ALMOST SHIPPED: it produced deltas of 693 and 792 on
  nine-figure numbers, which is exactly the shape of a real data-entry typo.
  It was caught only by hand-verifying every disagreement before reporting
  (P-11), not by the parser itself.

FUNCTIONAL REQUIREMENT (P2C, non-negotiable): this module's self_test() MUST
run and pass before this parser is used against any real document. See
scripts/run_extract.py, which calls self_test() first and stops if it fails
(PROMPTS.md P2C STOP CONDITION).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

ONES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9,
}
TEENS = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
HUNDRED = "hundred"

# Indian numbering scales. [VERIFIED against the six known-good pairs in
# notes/methodology.md Sec6.3 -- see self_test() below.] "crore"/"lakh"
# plural forms and "thousand" are normalised in _tokenize().
SCALES = {"thousand": 1_000, "lakh": 100_000, "crore": 10_000_000}

# Tokens that carry no numeric value and are dropped rather than rejected.
# "only" and "and" are filler words the NIRF form's amount-in-words
# convention uses routinely (e.g. "...Seventy Nine Only", "...Hundred and
# Seventy Nine"); dropping them is not the same as correcting a misspelling
# -- a genuine misspelling (e.g. "Sevety", "Hundered") is left unrecognised
# on purpose, so it abstains (UNVERIFIED) rather than silently "fixing"
# itself into a number that might be wrong.
_FILLER = {"only", "and", "rupees", "rs"}

_PLURAL_SCALE = {"crores": "crore", "lakhs": "lakh", "thousands": "thousand"}

_TOKEN_RE = re.compile(r"[a-zA-Z]+")


@dataclass(frozen=True)
class ParseResult:
    value: int | None
    abstain_reason: str | None  # None | "idiom" | "unparseable"


def _tokenize(words: str) -> list[str]:
    toks = [t.lower() for t in _TOKEN_RE.findall(words)]
    out = []
    for t in toks:
        t = _PLURAL_SCALE.get(t, t)
        if t in _FILLER:
            continue
        out.append(t)
    return out


def _has_idiom(toks: list[str]) -> bool:
    """A unit 1-9 immediately followed by a tens word, with no 'hundred'
    between, is spoken English ("eight fifty six" = 856), not composed
    arithmetic. [VERIFIED] does not false-trigger on any of the six known
    pairs (hand-traced in the P2C build session -- e.g. "Four Hundred
    Sixty" never puts a bare ONES token directly before a TENS token,
    because "hundred" sits between them)."""
    for i in range(len(toks) - 1):
        if toks[i] in ONES and toks[i + 1] in TENS:
            return True
    return False


def parse_words_to_number(words: str) -> ParseResult:
    """Returns a ParseResult. Never guesses: an unrecognised token or a
    spoken-idiom shape abstains (value=None) rather than returning a
    best-effort number. Callers must treat value=None as UNVERIFIED, not as
    a mismatch (P-7 / the three-state rule)."""
    toks = _tokenize(words)
    if not toks:
        return ParseResult(None, "unparseable")

    if _has_idiom(toks):
        return ParseResult(None, "idiom")

    result = 0
    cur = 0
    prev_scale = 0  # sentinel: "no scale absorbed yet" -- see module docstring
    any_token = False

    for t in toks:
        if t in ONES:
            cur += ONES[t]
            any_token = True
        elif t in TEENS:
            cur += TEENS[t]
            any_token = True
        elif t in TENS:
            cur += TENS[t]
            any_token = True
        elif t == HUNDRED:
            cur = (cur or 1) * 100
            any_token = True
        elif t in SCALES:
            s = SCALES[t]
            if s >= prev_scale:
                # Scale absorption: a larger-or-equal scale multiplies
                # EVERYTHING accumulated so far, not just the current group.
                # This is the fix for V1 bug #1.
                result = (result + cur) * s
            else:
                result += cur * s
            prev_scale = s
            cur = 0
            any_token = True
        else:
            # Unrecognised token: misspelling ("Sevety", "Hundered",
            # "Eiight", "Twentyone", "Thous and" split across a line break)
            # or genuinely not a number word. Do not guess at a correction.
            return ParseResult(None, "unparseable")

    if not any_token:
        return ParseResult(None, "unparseable")
    return ParseResult(result + cur, None)


# ---------------------------------------------------------------------------
# Self-test -- the six known-good pairs from notes/methodology.md Sec6.3.
# MUST be run and MUST pass before this parser touches a real document.
# ---------------------------------------------------------------------------

KNOWN_GOOD_PAIRS: list[tuple[str, int]] = [
    ("Eight Hundred Fifty Two Crore Thirty Nine Lakh Seventy Five Thousand One Hundred and One", 8523975101),
    ("One Thousand Four Hundred Sixty Crore Twenty Six Lakh Fifty Two Thousand One Hundred Seventy Three", 14602652173),
    ("Three Hundred Nine Crores Sixteen Lakhs Fifty Nine Thousand Four Hundred and Seventy Nine Only", 3091659479),
    ("Ninety One Lakhs Seventy Seven Thousand Six Hundred Twenty Five Only", 9177625),
    ("Twenty Lakhs Only", 2000000),
    ("Eighteen Lakhs Eighty Thousand", 1880000),
]

# Regression cases for the two bugs V1 shipped, so a future edit that
# reintroduces either one fails loudly here rather than in a real report.
_IDIOM_ABSTAIN_CASES = ["Eight Fifty Six", "Seven Thirty"]
_MISSPELLING_ABSTAIN_CASES = ["Sevety Eight Lakh", "Six Hundered", "Eiight Lakh Twentyone"]


@dataclass(frozen=True)
class SelfTestReport:
    passed: bool
    known_good: list[dict]
    idiom_abstentions: list[dict]
    misspelling_abstentions: list[dict]

    def all_rows(self) -> list[dict]:
        return self.known_good + self.idiom_abstentions + self.misspelling_abstentions


def self_test() -> SelfTestReport:
    known_good_rows = []
    ok = True
    for words, expected in KNOWN_GOOD_PAIRS:
        got = parse_words_to_number(words)
        row_ok = got.value == expected
        ok = ok and row_ok
        known_good_rows.append({"words": words, "expected": expected, "got": got.value, "ok": row_ok})

    idiom_rows = []
    for words in _IDIOM_ABSTAIN_CASES:
        got = parse_words_to_number(words)
        row_ok = got.value is None and got.abstain_reason == "idiom"
        ok = ok and row_ok
        idiom_rows.append({"words": words, "got": got.value, "abstain_reason": got.abstain_reason, "ok": row_ok})

    misspelling_rows = []
    for words in _MISSPELLING_ABSTAIN_CASES:
        got = parse_words_to_number(words)
        row_ok = got.value is None and got.abstain_reason == "unparseable"
        ok = ok and row_ok
        misspelling_rows.append(
            {"words": words, "got": got.value, "abstain_reason": got.abstain_reason, "ok": row_ok}
        )

    return SelfTestReport(
        passed=ok, known_good=known_good_rows, idiom_abstentions=idiom_rows, misspelling_abstentions=misspelling_rows
    )


if __name__ == "__main__":
    report = self_test()
    for row in report.all_rows():
        print(row)
    print("SELF-TEST:", "PASS" if report.passed else "FAIL")
