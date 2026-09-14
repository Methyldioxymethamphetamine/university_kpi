"""P1 CHECK B, ported into a permanent assertion (PROMPTS.md P2B: "Port CHECK
B from Phase 1 into the test suite as a permanent assertion, run on every
conversion of a NIRF document... the single most important line of defence
in the repo").

This checks one specific, known-correct row from IIT Bombay's 2025 Overall
NIRF PDF (sha256 e9a1d469..., the exact document gate/P1-spike.md's CHECK B
verified against). It is intentionally not generalised to "any NIRF PDF" --
the expected row's values (1161/1059/1039/1030) belong to this one document;
a different year's report legitimately contains different numbers. What this
buys: if Docling's model version changes and rotation/table-segmentation
handling regresses on this exact, previously-verified document, conversion
fails loudly instead of silently producing plausible-looking wrong output --
which is CLAUDE.md's defining risk.
"""
from __future__ import annotations

from docling_core.types.doc.document import DoclingDocument

GOLDEN_SHA256 = "e9a1d469ba17262f052948f22d8a15b6f4c37a4646af72efea77e0a7e0b1e019"

EXPECTED_HEADER = ["Academic Year", "2023-24", "2022-23", "2021-22", "2020-21", "2019-20", "2018-19"]
EXPECTED_ROW = ["UG [4 Years Program(s)]", "1161", "1059", "1039", "1030", "-", "-"]


class P1RegressionError(AssertionError):
    pass


def assert_check_b(document: DoclingDocument, *, sha256: str | None = None) -> dict:
    """Raises P1RegressionError if the known-good row cannot be found with
    correct, unambiguous label-to-value association. Returns the matched
    provenance dict on success. Does not eyeball -- same assertion shape as
    the original spike/check_b_assert.py, now importable instead of a
    throwaway script."""
    doc_dict = document.export_to_dict()
    matches = []
    for ti, table in enumerate(doc_dict.get("tables", [])):
        grid = table.get("data", {}).get("grid", [])
        for ri, row in enumerate(grid):
            texts = [cell.get("text", "") for cell in row]
            if texts == EXPECTED_ROW:
                header = [cell.get("text", "") for cell in grid[0]] if ri > 0 else None
                matches.append((ti, ri, header, table.get("prov")))

    if not matches:
        raise P1RegressionError(
            f"P1 regression: expected row {EXPECTED_ROW} not found in any table "
            f"(sha256={sha256}). Docling's rotation/table handling may have regressed."
        )
    ti, ri, header, prov = matches[0]
    if header != EXPECTED_HEADER:
        raise P1RegressionError(f"P1 regression: header mismatch, got {header}, expected {EXPECTED_HEADER}")
    if len(matches) != 1:
        raise P1RegressionError(f"P1 regression: row appears in {len(matches)} tables, ambiguous: {matches}")

    return {"table_index": ti, "row_index": ri, "header": header, "prov": prov}
