"""Tests for document structure section detection across NIRF fixtures.

Verifies:
1. All 8 test fixtures (6 Engineering PDFs + 2 Overall PDFs) have zero unmatched tables.
2. Every known section is detected where expected.
3. IR-E-C-16604 dynamically discovers the 'PG-Integrated [5 Years]' sub-block under
   'Placement & Higher Studies', which none of the other 7 fixtures have.
4. TableCell and ValueRow objects carry section and sub_block fields.
5. Unmatched tables are flagged/logged rather than silently swallowed.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from convert.docling_wrapper import convert_to_docling_document
from extract.docling_source import iter_table_cells
from extract.sections import detect_table_sections
from extract.values import build_value_rows

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

ALL_8_FIXTURES = [
    "IR-E-C-16604.pdf",
    "IR-E-C-36995.pdf",
    "IR-E-I-1074.pdf",
    "IR-E-I-1480.pdf",
    "IR-E-U-0391.pdf",
    "IR-E-U-0456.pdf",
    "IR-O-U-0306_2024.pdf",
    "IR-O-U-0306_2025.pdf",
]

CORE_EXPECTED_SECTIONS = {
    "Sanctioned (Approved) Intake",
    "Total Actual Student Strength",
    "Placement & Higher Studies",
    "Ph.D Student Details",
    "Financial Resources: Capital expenditure",
    "Financial Resources: Operational expenditure",
    "PCS Facilities: Facilities of Physically Challenged Students",
    "Faculty Details",
}


@pytest.mark.parametrize("fixture_name", ALL_8_FIXTURES)
def test_fixture_sections_and_zero_unmatched_tables(fixture_name: str):
    fixture_path = FIXTURES_DIR / fixture_name
    if not fixture_path.exists():
        pytest.skip(f"Fixture {fixture_name} not found in {FIXTURES_DIR}")

    doc = convert_to_docling_document(fixture_path)
    data = doc.export_to_dict()

    table_sections = detect_table_sections(data)
    assert len(table_sections) == len(data.get("tables", [])), (
        f"{fixture_name}: expected {len(data.get('tables', []))} tagged tables, got {len(table_sections)}"
    )

    # Assert ZERO unmatched tables
    unmatched = [t_ref for t_ref, tag in table_sections.items() if tag.section == "UNMATCHED"]
    assert not unmatched, f"{fixture_name} has unmatched tables: {unmatched}"

    # Assert core expected sections are present
    detected_sections = {tag.section for tag in table_sections.values()}
    missing_core = CORE_EXPECTED_SECTIONS - detected_sections
    # IR-E-I-1480 (Thapar) does not have a Ph.D Student Details table (institution has no PhD intake)
    if fixture_name == "IR-E-I-1480.pdf":
        missing_core -= {"Ph.D Student Details"}
    # IR-E-U-0391 does not have Sponsored Research Details
    assert not missing_core, f"{fixture_name} missing core sections: {missing_core}"


def test_ir_e_c_16604_dynamic_pg_integrated_sub_block():
    """IR-E-C-16604 has a 'PG-Integrated [5 Years]' sub-block under Placement & Higher Studies

    that none of the other 7 fixtures have. This must be dynamically captured.
    """
    fixture_path = FIXTURES_DIR / "IR-E-C-16604.pdf"
    if not fixture_path.exists():
        pytest.skip(f"Fixture IR-E-C-16604.pdf not found in {FIXTURES_DIR}")

    doc = convert_to_docling_document(fixture_path)
    data = doc.export_to_dict()
    table_sections = detect_table_sections(data)

    sub_blocks = {tag.sub_block for tag in table_sections.values() if tag.sub_block}
    assert "PG-Integrated [5 Years]" in sub_blocks, (
        f"IR-E-C-16604 failed to capture 'PG-Integrated [5 Years]' sub-block. Found: {sub_blocks}"
    )

    # Verify that none of the other 7 fixtures carry this sub-block
    for other_name in ALL_8_FIXTURES:
        if other_name == "IR-E-C-16604.pdf":
            continue
        other_path = FIXTURES_DIR / other_name
        if not other_path.exists():
            continue
        other_doc = convert_to_docling_document(other_path)
        other_sections = detect_table_sections(other_doc.export_to_dict())
        other_sub_blocks = {tag.sub_block for tag in other_sections.values() if tag.sub_block}
        assert "PG-Integrated [5 Years]" not in other_sub_blocks, (
            f"{other_name} unexpectedly had 'PG-Integrated [5 Years]'"
        )


def test_table_cell_and_value_row_carry_section_label():
    """Verify TableCell and ValueRow objects carry section and sub_block tags."""
    fixture_path = FIXTURES_DIR / "IR-E-C-16604.pdf"
    if not fixture_path.exists():
        pytest.skip("Fixture IR-E-C-16604.pdf not found")

    doc = convert_to_docling_document(fixture_path)
    data = doc.export_to_dict()

    cells = iter_table_cells("dummy_sha256", data)
    assert cells, "No cells extracted"

    # All cells from tables must carry a non-empty section
    assert all(c.section is not None for c in cells)

    # Value rows must carry section
    value_rows = build_value_rows(cells)
    assert value_rows, "No value rows extracted"
    assert all(r.section is not None for r in value_rows)

    # Specifically check the PG-Integrated sub-block cell and row
    pg_int_cells = [c for c in cells if c.sub_block == "PG-Integrated [5 Years]"]
    assert pg_int_cells, "Expected cells with sub_block == 'PG-Integrated [5 Years]'"
    assert any("PG-Integrated [5 Years]" in c.section for c in pg_int_cells)

    pg_int_rows = [r for r in value_rows if r.sub_block == "PG-Integrated [5 Years]"]
    assert pg_int_rows, "Expected value rows with sub_block == 'PG-Integrated [5 Years]'"


def test_unmatched_table_flagged_not_swallowed(caplog):
    """If a table occurs before any section header, it must be flagged with

    section='UNMATCHED' and logged, never silently dropped.
    """
    dummy_doc = {
        "body": {
            "children": [
                {"$ref": "#/tables/0"},
                {"$ref": "#/texts/0"},
                {"$ref": "#/tables/1"},
            ]
        },
        "texts": [
            {
                "self_ref": "#/texts/0",
                "label": "section_header",
                "text": "Faculty Details",
                "prov": [{"page_no": 1}],
            }
        ],
        "tables": [
            {
                "self_ref": "#/tables/0",
                "prov": [{"page_no": 1}],
                "data": {"grid": []},
            },
            {
                "self_ref": "#/tables/1",
                "prov": [{"page_no": 1}],
                "data": {"grid": []},
            },
        ],
    }

    with caplog.at_level(logging.WARNING):
        table_sections = detect_table_sections(dummy_doc)

    assert table_sections["#/tables/0"].section == "UNMATCHED"
    assert table_sections["#/tables/1"].section == "Faculty Details"
    assert "does not fall under any section header" in caplog.text
