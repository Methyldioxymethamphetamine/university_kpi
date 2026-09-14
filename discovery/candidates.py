"""Propose (label, value, page, bbox) -> kpi_code candidates for a document
that fingerprint/matcher.py could not match to any known profile.

PROMPTS.md P2E: "discovery/ propose (label, value, page, bbox) -> kpi_code
candidates." Every candidate carries its top-3 scored suggestions, visible
in full -- there is no threshold anywhere in this module that accepts a
mapping on its own (P-13). Scoring is plain token overlap against the real
229-row KPI dictionary (`discovery/kpi_dictionary.py`,
`registry/client-docs/kpi_dictionary_v2.xlsx`), the same transparent,
re-runnable technique notes/methodology.md Sec7.3 used for the parameters
join, chosen there for the same reason it is chosen here: "every match
carries a score the reader can audit."

**Scores against the REAL, corrected 229-row dictionary as of this
session** (`kpi_dictionary_v2.xlsx` -- 43 cells corrected from the original,
read-back verified, changelog in its own sheet). Supersedes both
`derived/kpi_dictionary_partial.yaml` (a 24-code stopgap built only because
this file did not exist in the repo yet -- see that file's own superseded
note) and the original `DOC-20260901-WA0019.xlsx` (229/229 rows marked
"Higher", including the three rank KPIs where that is inverted --
never load this one, see discovery/kpi_dictionary.py's own warning).

A suggestion whose kpi_code is one of the dictionary's CONTESTABLE codes
(currently S10, A09 -- a direction a different analyst could reasonably
invert) carries `contestable=True` here, unconditionally, regardless of
score or whether a reviewer later confirms it -- so a CONTESTABLE match can
never silently read as an ordinary PARTIAL or CONFIRMED one downstream.

Candidate generation reuses extract/docling_source.py + extract/values.py's
existing generic cell-role logic (column 0 / header-flagged = label,
everything else = value) -- the same convention P2C already applies to
every artifact, MIT included. That convention is not NIRF-specific; P2E is
allowed to read cells and PROPOSE a kpi_code from them (that is this
phase's whole purpose), it just cannot auto-accept one (P-13).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from discovery.kpi_dictionary import KpiEntry, load_kpi_dictionary_v2
from extract.docling_source import TableCell, iter_table_cells

REPO_ROOT = Path(__file__).resolve().parent.parent

_TOKEN_RE = re.compile(r"[a-z]+")


def _tokens(s: str) -> set[str]:
    return set(_TOKEN_RE.findall(s.lower()))


@dataclass(frozen=True)
class KpiSuggestion:
    kpi_code: str
    kpi_label: str
    score: float  # Jaccard overlap of label tokens, visible always (P-13)
    contestable: bool  # True iff this KPI's own Benchmark_Direction is flagged CONTESTABLE in v2_Note


@dataclass(frozen=True)
class Candidate:
    sha256: str
    item_id: str
    page_no: int | None
    bbox: dict | None
    label: str
    value: str
    suggestions: list[KpiSuggestion] = field(default_factory=list)

    @property
    def best(self) -> KpiSuggestion | None:
        return self.suggestions[0] if self.suggestions else None


def _score(label_tokens: set[str], kpi_tokens: set[str]) -> float:
    if not label_tokens or not kpi_tokens:
        return 0.0
    inter = len(label_tokens & kpi_tokens)
    union = len(label_tokens | kpi_tokens)
    return round(inter / union, 3) if union else 0.0


def suggest_kpi_codes(label: str, dictionary: dict[str, KpiEntry], top_n: int = 3) -> list[KpiSuggestion]:
    label_tokens = _tokens(label)
    scored = []
    for code, entry in dictionary.items():
        kpi_tokens = _tokens(entry.label)
        s = _score(label_tokens, kpi_tokens)
        if s > 0:
            scored.append(KpiSuggestion(code, entry.label, s, entry.contestable))
    scored.sort(key=lambda x: (-x.score, x.kpi_code))
    return scored[:top_n]


def _candidate_label(cell: TableCell) -> str:
    parts = [p for p in (cell.row_label, cell.column_label) if p]
    return " ".join(parts).strip()


def generate_candidates(sha256: str, docling_doc: dict) -> list[Candidate]:
    """Every non-label cell in the document becomes a candidate -- this is
    deliberately unfiltered (no pre-selection of "likely" fields), because
    filtering before scoring would silently drop the fields a real reviewer
    might have accepted (the same complaint P-13's own commentary makes
    about tuning the join threshold instead of reviewing every row)."""
    dictionary = load_kpi_dictionary_v2()  # raises DictionaryConsistencyError if the file doesn't match its own claimed shape
    cells = iter_table_cells(sha256, docling_doc)
    candidates = []
    for cell in cells:
        if cell.is_column_header or cell.is_row_header or cell.col_index == 0:
            continue
        if not cell.text.strip():
            continue
        label = _candidate_label(cell)
        if not label:
            continue
        suggestions = suggest_kpi_codes(label, dictionary)
        candidates.append(
            Candidate(
                sha256=sha256, item_id=cell.item_id, page_no=cell.page_no, bbox=cell.bbox,
                label=label, value=cell.text, suggestions=suggestions,
            )
        )
    return candidates
