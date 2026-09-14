"""End-to-end test against all 8 fixtures loaded into Postgres.

Verifies:
1. Every row lands in Postgres with a non-null domain.
2. ORPHAN rows persist with kpi_code = NULL and mapping_status = 'ORPHAN'.
3. Read-back verification matches exact line count.
4. Reports final counts across the 8 fixtures.
"""
from __future__ import annotations

import json
from pathlib import Path

import psycopg
import pytest

from db.loader import DEFAULT_DSN, load_run_to_postgres
from extract.pipeline import extract_artifact, write_run

ALL_8_FIXTURES_SHAS = [
    "4532b6fe8887117d52cad6691b22be564df961a5b3695bbf1943990cf4b65985",  # IR-E-C-16604 (Sri Sivasubramaniya Nadar College of Engineering)
    "0676de4fd02591dc2770300eacf6cd8d818c137dda195a8253899edf81d0c8d4",  # IR-E-C-36995 (Sri Krishna College of Engineering and Technology)
    "b74c0a4d4d0486c23a5ebd9d15631922707ef311544c1d9cae04f787f3258cb1",  # IR-E-I-1074 (Indian Institute of Technology Delhi)
    "31cd3945c7705f0342979267bc3de0e22126cf08a3d10cd1110e7c30862c351f",  # IR-E-I-1480 (Thapar Institute of Engineering and Technology)
    "a02f3395add211b119b691b4189e6d4e1bce5e8de492ebdd8d049eb2863b6731",  # IR-E-U-0391 (Birla Institute of Technology & Science - Pilani)
    "4a7048dcbc040a44f4ec2fc8469552aa0fa747f977b72df213d122cf0357b936",  # IR-E-U-0456 (Indian Institute of Technology Madras)
    "d2c9d5c22ad556adeb2f45764644df2bd6513a91f5ea4f62a9401dddb5e17445",  # IR-O-U-0306_2024 (Indian Institute of Technology Bombay 2024)
    "e9a1d469ba17262f052948f22d8a15b6f4c37a4646af72efea77e0a7e0b1e019",  # IR-O-U-0306_2025 (Indian Institute of Technology Bombay 2025)
]


def test_8_fixtures_end_to_end_postgres():
    try:
        conn = psycopg.connect(DEFAULT_DSN)
        conn.close()
    except Exception as exc:
        pytest.skip(f"Postgres not accessible at {DEFAULT_DSN}: {exc}")

    manifests = []
    for sha in ALL_8_FIXTURES_SHAS:
        m_path = Path("docs") / sha[:8] / "manifest.json"
        assert m_path.exists(), f"Manifest for fixture {sha[:8]} not found in docs/"
        manifests.append(json.loads(m_path.read_text(encoding="utf-8")))

    import uuid
    # Run extraction on all 8 fixtures
    results = [extract_artifact(m) for m in manifests]
    assert len(results) == 8
    run_id = f"test_8_fixtures_{uuid.uuid4().hex[:8]}"

    values_path, checksums_path = write_run(run_id, results)
    assert values_path.exists()
    assert checksums_path.exists()

    # Load into Postgres
    report = load_run_to_postgres(run_id, values_path, checksums_path)

    # 1. Assert row count matches
    assert report["total_inserted"] == report["jsonl_count"]
    assert report["total_inserted"] == 1507

    # 2. Assert zero null domains
    assert report["null_domain_count"] == 0, f"Found {report['null_domain_count']} null domain rows"

    # 3. Assert orphan rows persisted with NULL kpi_code
    with psycopg.connect(DEFAULT_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*)
                FROM value
                WHERE run_id = %s AND kpi_code IS NULL AND mapping_status = 'ORPHAN'
                """,
                (run_id,),
            )
            orphan_count = cur.fetchone()[0]
            assert orphan_count > 0, "No orphan rows found in Postgres"
            assert orphan_count == report["status_distribution"].get("ORPHAN", 0)

            # Check that an orphan concept specifically exists in DB
            cur.execute(
                """
                SELECT raw_value, section, domain
                FROM value
                WHERE run_id = %s AND kpi_code IS NULL AND domain = 'FIN'
                LIMIT 3
                """,
                (run_id,),
            )
            sample_orphans = cur.fetchall()
            assert sample_orphans, "Expected orphan rows in FIN domain"

            # 4. Assert ANOMALY rows are separated from ORPHAN
            assert report["status_distribution"].get("ANOMALY") == 8, (
                f"Expected 8 ANOMALY rows, got {report['status_distribution'].get('ANOMALY')}"
            )
            assert report["status_distribution"].get("ORPHAN") == 805, (
                f"Expected 805 genuine ORPHAN rows, got {report['status_distribution'].get('ORPHAN')}"
            )

            # Confirm 0676de4f Table 4 rows are retagged as ANOMALY with reason
            cur.execute(
                """
                SELECT raw_value, mapping_status, anomaly_reason, confidence
                FROM value
                WHERE run_id = %s AND sha256 LIKE '0676de4f%%' AND item_id LIKE '%%/tables/4:%%'
                """,
                (run_id,),
            )
            t4_rows = cur.fetchall()
            assert len(t4_rows) == 8, f"Expected 8 Table 4 rows, found {len(t4_rows)}"
            for raw_val, status, reason, conf in t4_rows:
                assert status == "ANOMALY"
                assert reason == "continuation_column_count_mismatch"
                assert float(conf) == 0.0

    # Print summary of report
    print("\n8 Fixtures Verification Summary:")
    print(f"  Total rows inserted: {report['total_inserted']}")
    print(f"  Status distribution: {report['status_distribution']}")
    print(f"  Domain distribution: {report['domain_distribution']}")
    print(f"  Anomaly count: {report['anomaly_count']}")
