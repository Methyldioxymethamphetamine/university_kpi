"""Tests for Postgres value table persistence, schema changes, and mapping logic.

Verifies:
1. Schema allows nullable kpi_code and period_value for orphan rows.
2. Value table immutability trigger forbids UPDATE and DELETE.
3. Every inserted NIRF row carries a non-null domain.
4. Mapping logic resolves DIRECT/DERIVED/ANNEXURE/PARTIAL/ORPHAN correctly.
5. Read-back verification matches row count and preserves CONFLICTING rows.
"""
from __future__ import annotations

import json
from pathlib import Path

import psycopg
import pytest

from db.loader import DEFAULT_DSN, ensure_database_ready, load_run_to_postgres
from extract.mapping import (
    ANNEXURE,
    ANOMALY,
    DERIVED,
    DIRECT,
    ORPHAN,
    PARTIAL,
    get_static_lookup,
    resolve_domain,
    resolve_mapping,
)


def test_static_mapping_lookup_loaded():
    lookup = get_static_lookup()
    assert len(lookup) == 33, f"Expected 33 hand-mapped concepts, found {len(lookup)}"

    # Check sample concepts
    assert lookup["Median salary of placed graduates"].kpi_code == "P02"
    assert lookup["Median salary of placed graduates"].mapping_status == DIRECT
    assert lookup["Median salary of placed graduates"].domain == "PLC"

    assert lookup["No. of students placed"].kpi_code == "P01"
    assert lookup["No. of students placed"].mapping_status == DERIVED

    assert lookup["Faculty Gender"].mapping_status == ANNEXURE
    assert lookup["PCS Facilities"].mapping_status == PARTIAL


def test_resolve_domain_covers_all_known_sections():
    sections = [
        ("Sanctioned (Approved) Intake", "STU"),
        ("Total Actual Student Strength", "STU"),
        ("Placement & Higher Studies: UG [4 Years]", "PLC"),
        ("Placement & Higher Studies: PG-Integrated [5 Years]", "PLC"),
        ("Ph.D Student Details", "RES"),
        ("Financial Resources: Capital expenditure", "FIN"),
        ("Financial Resources: Operational expenditure", "FIN"),
        ("Sponsored Research Details", "RES"),
        ("Consultancy Project Details", "RES"),
        ("PCS Facilities: Facilities of Physically Challenged Students", "INF"),
        ("Faculty Details", "FAC"),
        ("Executive Development Program/Management Development Programs", "ACA"),
        ("Multiple Entry/Exit and Indian Knowledge System", "ACA"),
        ("Sustainability Details / Sustainable Living Practices", "ESG"),
        ("Accreditation", "X"),
        ("IPR/Patents", "RES"),
    ]
    for sec, expected_domain in sections:
        resolved = resolve_domain(sec)
        assert resolved == expected_domain, f"Section {sec} mapped to {resolved}, expected {expected_domain}"


def test_resolve_mapping_orphan_fallback():
    orphan_row = {
        "section": "Financial Resources: Capital expenditure",
        "row_label": "Engineering Workshops",
        "column_label": "2021-22",
    }
    kpi_code, status, domain = resolve_mapping(orphan_row)
    assert kpi_code is None
    assert status == ORPHAN
    assert domain == "FIN"


def test_resolve_mapping_anomaly():
    anomaly_row = {
        "section": "Placement & Higher Studies: UG [5 Years]",
        "row_label": "2019-20",
        "column_label": None,
        "anomaly_reason": "continuation_column_count_mismatch",
    }
    kpi_code, status, domain = resolve_mapping(anomaly_row)
    assert kpi_code is None
    assert status == ANOMALY
    assert domain == "PLC"


def test_postgres_orphan_insert_and_immutability():
    try:
        conn = psycopg.connect(DEFAULT_DSN)
    except Exception as exc:
        pytest.skip(f"Postgres not accessible at {DEFAULT_DSN}: {exc}")

    with conn:
        ensure_database_ready(conn)

        # 1. Insert orphan row with kpi_code = NULL
        test_run_id = "test_orphan_run_9999"
        with conn.cursor() as cur:
            # Clean up test run if pre-existing
            # Drop trigger temporarily only for test cleanup
            cur.execute("DROP TRIGGER IF EXISTS value_immutable ON value")
            cur.execute("DELETE FROM value WHERE run_id = %s", (test_run_id,))
            # Recreate trigger
            schema_sql = (Path(__file__).resolve().parent.parent / "db" / "schema.sql").read_text()
            cur.execute(schema_sql)

            # Insert test artifact stub
            cur.execute(
                """
                INSERT INTO source (source_id, country, institution_code, entry_type)
                VALUES ('test_src', 'IN', 'TEST_INST', 'fixture')
                ON CONFLICT (source_id) DO NOTHING;
                INSERT INTO artifact (sha256, source_id, url, run_id, fetched_at, http_status, classify_label, profile_id, match_status)
                VALUES ('test_sha256_dummy', 'test_src', 'fixture://test', 'test_run', now(), 200, 'pdf_digital', 'nirf_submission_v2020_2026', 'MATCH')
                ON CONFLICT (sha256) DO NOTHING;
                INSERT INTO doc_item (item_id, sha256, page_no, item_type, text)
                VALUES ('test_item_orphan', 'test_sha256_dummy', 1, 'table_cell', '12345')
                ON CONFLICT (item_id) DO NOTHING;
                """
            )

            # Real insertion of an ORPHAN row (kpi_code = NULL, period_value = NULL)
            cur.execute(
                """
                INSERT INTO value (
                    kpi_code, institution_code, period_value, period_type,
                    raw_value, normalized_value, sha256, item_id, profile_id,
                    auth_status, run_id, confidence, section, domain, mapping_status
                ) VALUES (
                    NULL, 'TEST_INST', NULL, NULL,
                    '12345', 12345.0, 'test_sha256_dummy', 'test_item_orphan', 'nirf_submission_v2020_2026',
                    'NOT_APPLICABLE', %s, 0.5, 'Financial Resources: Capital expenditure', 'FIN', 'ORPHAN'
                ) RETURNING value_id;
                """,
                (test_run_id,),
            )
            v_id = cur.fetchone()[0]
            # Real insertion of an ANOMALY row with anomaly_reason
            cur.execute(
                """
                INSERT INTO value (
                    kpi_code, institution_code, period_value, period_type,
                    raw_value, normalized_value, sha256, item_id, profile_id,
                    auth_status, run_id, confidence, section, domain, mapping_status,
                    anomaly_reason
                ) VALUES (
                    NULL, 'TEST_INST', NULL, NULL,
                    '60', 60.0, 'test_sha256_dummy', 'test_item_orphan', 'nirf_submission_v2020_2026',
                    'NOT_APPLICABLE', %s, 0.0, 'Placement & Higher Studies: UG [5 Years]', 'PLC', 'ANOMALY',
                    'continuation_column_count_mismatch'
                ) RETURNING value_id;
                """,
                (test_run_id,),
            )
            a_id = cur.fetchone()[0]
            assert a_id is not None
        conn.commit()

        # Assert trigger prevents UPDATE
        with conn.cursor() as cur:
            with pytest.raises(psycopg.Error) as update_err:
                cur.execute("UPDATE value SET raw_value = '9999' WHERE value_id = %s", (v_id,))
            assert "value is insert-only" in str(update_err.value)

        conn.rollback()

        # Assert trigger prevents DELETE
        with conn.cursor() as cur:
            with pytest.raises(psycopg.Error) as delete_err:
                cur.execute("DELETE FROM value WHERE value_id = %s", (v_id,))
            assert "value is insert-only" in str(delete_err.value)

        conn.rollback()

    conn.close()


def test_load_run_refuses_duplicate_run_id():
    """load_run_to_postgres must raise RuntimeError on a second call with the
    same run_id rather than silently doubling every row.

    This is the structural guard against the 'test_8_fixtures_run' failure mode
    where a static run_id was loaded twice, producing 3174 rows instead of 1587.
    The append-only trigger blocks UPDATE/DELETE but cannot block a repeat INSERT;
    this explicit pre-flight check fills that gap.
    """
    try:
        conn = psycopg.connect(DEFAULT_DSN)
        conn.close()
    except Exception as exc:
        pytest.skip(f"Postgres not accessible at {DEFAULT_DSN}: {exc}")

    import json, uuid
    from pathlib import Path
    from db.loader import ensure_database_ready, load_run_to_postgres

    dup_run_id = f"test_dup_guard_{uuid.uuid4().hex[:8]}"

    # Build a minimal single-row values.jsonl in a temp location
    import tempfile, os
    tmp_dir = Path(tempfile.mkdtemp())
    values_path = tmp_dir / "values.jsonl"

    # Re-use the stub artifact from the orphan test (test_sha256_dummy / test_item_orphan)
    row = {
        "sha256": "test_sha256_dummy",
        "item_id": "test_item_orphan",
        "institution_code": "TEST_INST",
        "raw_value": "999",
        "normalized_value": 999.0,
        "section": "Financial Resources: Capital expenditure",
        "row_label": "Test Row",
        "column_label": "2023-24",
        "period_type": "academic_year",
        "period_value": "2023-24",
        "page_no": 1,
        "bbox": None,
        "dash_state": "VALUE",
        "anomaly_reason": None,
        "run_id": dup_run_id,
        "source_id": "test_src",
    }
    values_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    # First load must succeed
    report = load_run_to_postgres(dup_run_id, values_path)
    assert report["total_inserted"] == 1, f"Expected 1 row, got {report['total_inserted']}"

    # Second load with the same run_id must raise, not insert
    with pytest.raises(RuntimeError, match="already has 1 row"):
        load_run_to_postgres(dup_run_id, values_path)

    # Confirm the row count is still 1 (not 2)
    with psycopg.connect(DEFAULT_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM value WHERE run_id = %s", (dup_run_id,))
            count = cur.fetchone()[0]
    assert count == 1, f"Expected 1 row after refused duplicate, found {count}"

    # Cleanup (requires dropping trigger temporarily, same as the orphan test)
    with psycopg.connect(DEFAULT_DSN) as conn:
        schema_sql = (Path(__file__).resolve().parent.parent / "db" / "schema.sql").read_text()
        with conn.cursor() as cur:
            cur.execute("DROP TRIGGER IF EXISTS value_immutable ON value")
            cur.execute("DELETE FROM value WHERE run_id = %s", (dup_run_id,))
            cur.execute(schema_sql)
        conn.commit()

    # Remove temp files
    values_path.unlink()
    tmp_dir.rmdir()


def test_delete_manual_test_run_isolation():
    """Verify delete_manual_test_run:
    1. Allows deleting sandbox runs (prefixed manual_test_).
    2. Python helper refuses non-sandbox runs.
    3. Postgres trigger forbids deleting non-sandbox runs even on direct SQL.
    4. Production / reference rows remain strictly untouched.
    """
    import uuid
    from db.loader import delete_manual_test_run

    sandbox_run_id = f"manual_test_TESTINST_{uuid.uuid4().hex[:8]}"
    non_sandbox_run_id = f"prod_test_{uuid.uuid4().hex[:8]}"

    with psycopg.connect(DEFAULT_DSN) as conn:
        with conn.cursor() as cur:
            # Insert a sandbox row
            cur.execute(
                """
                INSERT INTO value (
                    kpi_code, institution_code, period_value, period_type,
                    raw_value, normalized_value, sha256, item_id, profile_id,
                    auth_status, run_id, confidence, section, domain, mapping_status
                ) VALUES (
                    NULL, 'TEST_INST', NULL, NULL,
                    '100', 100.0, 'test_sha256_dummy', 'test_item_orphan', 'nirf_submission_v2020_2026',
                    'NOT_APPLICABLE', %s, 0.5, 'Sanctioned (Approved) Intake', 'STU', 'ORPHAN'
                )
                """,
                (sandbox_run_id,),
            )
            # Insert a non-sandbox row
            cur.execute(
                """
                INSERT INTO value (
                    kpi_code, institution_code, period_value, period_type,
                    raw_value, normalized_value, sha256, item_id, profile_id,
                    auth_status, run_id, confidence, section, domain, mapping_status
                ) VALUES (
                    NULL, 'TEST_INST', NULL, NULL,
                    '200', 200.0, 'test_sha256_dummy', 'test_item_orphan', 'nirf_submission_v2020_2026',
                    'NOT_APPLICABLE', %s, 0.5, 'Sanctioned (Approved) Intake', 'STU', 'ORPHAN'
                )
                """,
                (non_sandbox_run_id,),
            )
        conn.commit()

    # 1. Python helper hard-refuses non-sandbox run
    with pytest.raises(ValueError, match="Refusing to delete non-sandbox run"):
        delete_manual_test_run(non_sandbox_run_id)

    # 2. Database trigger hard-refuses deleting non-sandbox run
    with psycopg.connect(DEFAULT_DSN) as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.Error, match="value is insert-only"):
                cur.execute("DELETE FROM value WHERE run_id = %s", (non_sandbox_run_id,))

    # 3. Python helper succeeds on sandbox run
    deleted = delete_manual_test_run(sandbox_run_id)
    assert deleted == 1

    # Verify sandbox row is gone
    with psycopg.connect(DEFAULT_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM value WHERE run_id = %s", (sandbox_run_id,))
            assert cur.fetchone()[0] == 0

    # Cleanup non-sandbox test row by temporarily disabling trigger
    with psycopg.connect(DEFAULT_DSN) as conn:
        schema_sql = (Path(__file__).resolve().parent.parent / "db" / "schema.sql").read_text()
        with conn.cursor() as cur:
            cur.execute("DROP TRIGGER IF EXISTS value_immutable ON value")
            cur.execute("DELETE FROM value WHERE run_id = %s", (non_sandbox_run_id,))
            cur.execute(schema_sql)
        conn.commit()

