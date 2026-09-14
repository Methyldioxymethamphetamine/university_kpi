"""P1 REGRESSION TEST (PROMPTS.md P2B, marked "the single most important
line of defence in the repo"). Ported from spike/check_b_assert.py /
gate/P1-spike.md CHECK B.

Runs Docling for real against the actual acquired IIT Bombay 2025 Overall
PDF (not a cached fixture) so a future Docling upgrade that regresses
rotation/table-segmentation handling is caught here, not discovered by a
plausible-but-wrong number reaching a demo.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from classify.artifact import find_raw_path
from convert.docling_wrapper import convert_to_docling_document
from convert.regression import GOLDEN_SHA256, assert_check_b

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_p1_check_b_regression():
    raw_path = find_raw_path(GOLDEN_SHA256)
    if raw_path is None:
        pytest.skip(
            f"golden fixture sha256={GOLDEN_SHA256} not present under raw/ -- "
            "run scripts/run_acquire.py first (P2A must have acquired IIT Bombay)."
        )

    document = convert_to_docling_document(raw_path)
    result = assert_check_b(document, sha256=GOLDEN_SHA256)

    assert result["header"] == [
        "Academic Year",
        "2023-24",
        "2022-23",
        "2021-22",
        "2020-21",
        "2019-20",
        "2018-19",
    ]
    prov = result["prov"][0]
    assert prov["page_no"] == 1
    assert prov["bbox"]["coord_origin"] == "BOTTOMLEFT"
