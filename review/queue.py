"""The review queue: every discovery candidate, its top-3 scored suggestions
(always visible), and the action a human reviewer took.

PROMPTS.md P2E: "review/ the queue: candidate, top-3 suggestions WITH SCORES
VISIBLE, actions = confirm / re-assign / mark PARTIAL / no-KPI-home."

FORBIDDEN, per P-13 and PROMPTS.md P2E's own FORBIDDEN list: no function in
this module accepts a mapping on the strength of a score alone. Every
ReviewRecord below is written by a caller that read the candidate's label,
value and (when relevant) neighbouring cells and made a judgment --
scripts/run_p2e_t2.py's own comments are that judgment's paper trail, not
just its output.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from discovery.candidates import Candidate

CONFIRM = "CONFIRM"          # candidate's own top suggestion is correct
REASSIGN = "REASSIGN"        # correct kpi_code, but NOT the top (or any) suggestion -- reviewer's own call
MARK_PARTIAL = "MARK_PARTIAL"  # a related, weaker-form value; needs a formula/definition decision, not a value copy
NO_KPI_HOME = "NO_KPI_HOME"  # reviewed and rejected -- either a false-positive score, or a genuine orphan (P-16 doc_item)

ACTIONS = (CONFIRM, REASSIGN, MARK_PARTIAL, NO_KPI_HOME)


@dataclass(frozen=True)
class ReviewRecord:
    sha256: str
    item_id: str
    label: str
    value: str
    top_suggestions: list[tuple[str, float]]  # always stored, even for NO_KPI_HOME -- P-13: visible always
    action: str
    kpi_code: str | None
    contestable: bool  # True iff kpi_code's own Benchmark_Direction is CONTESTABLE (dictionary v2_Note) -- an
                        # orthogonal flag, never folded into `action`, so a CONTESTABLE match can never read
                        # as an ordinary CONFIRM/PARTIAL downstream (per explicit instruction: don't let the
                        # ambiguity get silently absorbed into a normal classification)
    reviewer: str
    reviewed_at: str
    note: str

    def __post_init__(self) -> None:
        if self.action not in ACTIONS:
            raise ValueError(f"unknown review action {self.action!r}")
        if self.action in (CONFIRM, REASSIGN, MARK_PARTIAL) and not self.kpi_code:
            raise ValueError(f"{self.action} requires a kpi_code")
        if self.action == NO_KPI_HOME and self.kpi_code:
            raise ValueError("NO_KPI_HOME must not carry a kpi_code")
        if self.action == NO_KPI_HOME and self.contestable:
            raise ValueError("NO_KPI_HOME carries no kpi_code, so it cannot be CONTESTABLE either")


def review(
    candidate: Candidate, action: str, *, reviewer: str, kpi_code: str | None = None,
    note: str = "", contestable: bool = False,
) -> ReviewRecord:
    return ReviewRecord(
        sha256=candidate.sha256,
        item_id=candidate.item_id,
        label=candidate.label,
        value=candidate.value,
        top_suggestions=[(s.kpi_code, s.score) for s in candidate.suggestions],
        action=action,
        kpi_code=kpi_code,
        contestable=contestable,
        reviewer=reviewer,
        reviewed_at=datetime.now(timezone.utc).isoformat(),
        note=note,
    )


def write_queue(records: list[ReviewRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(asdict(r), sort_keys=True) + "\n")


def read_queue(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
