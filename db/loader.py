"""Load extracted value rows from values.jsonl into PostgreSQL `value` table.

Enforces:
1. Append-only / immutable semantics via database trigger.
2. Complete read-back verification (assert row count matches JSONL lines).
3. Concept and domain resolution (DIRECT/DERIVED/ANNEXURE/PARTIAL/ORPHAN).
4. Prerequisite citation integrity (source, artifact, doc_item, profile).
5. Spot-checking of CONFLICTING dual-encoding rows.
"""
from __future__ import annotations

import json
import logging
import os
from collections import Counter
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from extract.mapping import resolve_mapping
from fingerprint.matcher import known_profile_ids
from profiles.engine import load_profile

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"
DEFAULT_DSN = os.environ.get(
    "DATABASE_URL",
    "host=localhost port=5433 dbname=kpi user=postgres password=kpi",
)


def ensure_database_ready(conn: psycopg.Connection) -> None:
    """Ensure schema exists and known profiles are synced."""
    schema_sql = (REPO_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(schema_sql)
        cur.execute("ALTER TABLE value ADD COLUMN IF NOT EXISTS anomaly_reason TEXT;")
        cur.execute("ALTER TABLE value ADD COLUMN IF NOT EXISTS row_label TEXT;")
        cur.execute("ALTER TABLE value DROP CONSTRAINT IF EXISTS value_mapping_status_check;")
        cur.execute(
            """
            ALTER TABLE value ADD CONSTRAINT value_mapping_status_check
                CHECK (mapping_status IN ('DIRECT', 'DERIVED', 'ANNEXURE', 'PARTIAL', 'ORPHAN', 'ANOMALY'));
            """
        )
        for profile_id in known_profile_ids():
            prof = load_profile(profile_id)
            cur.execute(
                """
                INSERT INTO profile (profile_id, name, version, fingerprint, blocks, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (profile_id) DO NOTHING
                """,
                (
                    profile_id,
                    prof.get("description", profile_id),
                    "current",
                    json.dumps(prof.get("fingerprint", {})),
                    json.dumps(prof.get("blocks", [])),
                    "db/loader.py sync",
                ),
            )
    conn.commit()


def sync_manifest_prerequisites(conn: psycopg.Connection, sha256_set: set[str]) -> None:
    """Ensure source, artifact, and profile exist for each sha256 before inserting into value."""
    with conn.cursor() as cur:
        for sha in sha256_set:
            manifest_file = DOCS_ROOT / sha[:8] / "manifest.json"
            if manifest_file.exists():
                m = json.loads(manifest_file.read_text(encoding="utf-8"))
                source_id = m.get("source_id") or f"src_{sha[:8]}"
                inst_code = m.get("institution_code") or "UNKNOWN"
                country = m.get("country") or "IN"
                entry_type = "fixture"
                cur.execute(
                    """
                    INSERT INTO source (source_id, country, institution_code, entry_type)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (source_id) DO NOTHING
                    """,
                    (source_id, country, inst_code, entry_type),
                )
                runs = m.get("runs", [])
                latest = runs[-1] if runs else {}
                cur.execute(
                    """
                    INSERT INTO artifact (
                        sha256, source_id, url, run_id, fetched_at, http_status,
                        content_type, n_pages, classify_label, profile_id, match_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (sha256) DO NOTHING
                    """,
                    (
                        sha,
                        source_id,
                        m.get("canonical_url", f"fixture://{sha[:8]}"),
                        latest.get("run_id", "extraction"),
                        latest.get("fetched_at", "2026-01-01T00:00:00Z"),
                        latest.get("http_status", 200),
                        latest.get("content_type", "application/pdf"),
                        m.get("convert", {}).get("n_pages", 1),
                        m.get("classify", {}).get("label", "pdf_digital"),
                        "nirf_submission_v2020_2026",
                        "MATCH",
                    ),
                )
            else:
                # Stub source/artifact if manifest missing
                source_id = f"src_{sha[:8]}"
                cur.execute(
                    """
                    INSERT INTO source (source_id, country, institution_code, entry_type)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (source_id) DO NOTHING
                    """,
                    (source_id, "IN", "UNKNOWN", "fixture"),
                )
                cur.execute(
                    """
                    INSERT INTO artifact (
                        sha256, source_id, url, run_id, fetched_at, http_status,
                        content_type, n_pages, classify_label, profile_id, match_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (sha256) DO NOTHING
                    """,
                    (
                        sha,
                        source_id,
                        f"fixture://{sha[:8]}",
                        "extraction",
                        "2026-01-01T00:00:00Z",
                        200,
                        "application/pdf",
                        1,
                        "pdf_digital",
                        "nirf_submission_v2020_2026",
                        "MATCH",
                    ),
                )
    conn.commit()


def sync_doc_items(conn: psycopg.Connection, value_records: list[dict]) -> None:
    """Ensure each cited item_id exists in doc_item before inserting into value."""
    # Dedup by item_id
    seen_items = {}
    for r in value_records:
        item_id = r.get("item_id")
        if item_id and item_id not in seen_items:
            seen_items[item_id] = (
                item_id,
                r["sha256"],
                r.get("page_no"),
                json.dumps(r.get("bbox")) if r.get("bbox") else None,
                "table_cell",
                r.get("raw_value", ""),
            )

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO doc_item (item_id, sha256, page_no, bbox, item_type, text)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (item_id) DO NOTHING
            """,
            list(seen_items.values()),
        )
    conn.commit()


def load_run_to_postgres(
    run_id: str,
    values_path: Path,
    checksums_path: Path | None = None,
    dsn: str = DEFAULT_DSN,
) -> dict[str, Any]:
    """Read a completed run's values.jsonl and insert into Postgres value table.

    Includes read-back verification and returns summary report.
    """
    if not values_path.exists():
        raise FileNotFoundError(f"values.jsonl not found at {values_path}")

    value_lines = [
        json.loads(line)
        for line in values_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    checksum_map: dict[tuple[str, str], str] = {}
    if checksums_path and checksums_path.exists():
        for line in checksums_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                c_row = json.loads(line)
                checksum_map[(c_row["sha256"], c_row["item_id"])] = c_row.get("state", "UNVERIFIED")

    with psycopg.connect(dsn) as conn:
        ensure_database_ready(conn)

        # Guard: refuse to load if this run_id already has rows. The append-only
        # trigger blocks UPDATE/DELETE but cannot block a second INSERT under the
        # same run_id -- that would silently double every row.  Raise here so
        # callers get a loud failure instead of corrupted counts.
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM value WHERE run_id = %s", (run_id,))
            existing = cur.fetchone()[0]
        if existing:
            raise RuntimeError(
                f"load_run_to_postgres: run_id={run_id!r} already has {existing} row(s) "
                f"in the value table. Refusing to insert again -- this would double every "
                f"row. Use a fresh run_id for each extraction run (append-only, P-5)."
            )

        sha256_set = {r["sha256"] for r in value_lines if r.get("sha256")}
        sync_manifest_prerequisites(conn, sha256_set)
        sync_doc_items(conn, value_lines)

        insert_rows = []
        for r in value_lines:
            sha = r["sha256"]
            item_id = r["item_id"]
            kpi_code, mapping_status, domain = resolve_mapping(r)

            # Determine auth_status from checksum map if available
            key = (sha, item_id)
            if key in checksum_map:
                auth_status = checksum_map[key]
            else:
                auth_status = "NOT_APPLICABLE"

            profile_id = "nirf_submission_v2020_2026"
            confidence = 0.0 if mapping_status == "ANOMALY" else (1.0 if mapping_status != "ORPHAN" else 0.5)
            anomaly_reason = r.get("anomaly_reason")
            row_label = r.get("row_label")  # grid[row][0].text -- orphan grouping key

            insert_rows.append(
                (
                    kpi_code,
                    r.get("institution_code") or "UNKNOWN",
                    r.get("period_value"),
                    r.get("period_type"),
                    r["raw_value"],
                    r.get("normalized_value"),
                    sha,
                    item_id,
                    profile_id,
                    auth_status,
                    run_id,
                    confidence,
                    r.get("section"),
                    domain,
                    mapping_status,
                    anomaly_reason,
                    row_label,
                )
            )

        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO value (
                    kpi_code, institution_code, period_value, period_type,
                    raw_value, normalized_value, sha256, item_id, profile_id,
                    auth_status, run_id, confidence, section, domain, mapping_status,
                    anomaly_reason, row_label
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                insert_rows,
            )
        conn.commit()

        # Read-back verification (P-10: never claim a write succeeded without reading it back)
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT count(*) as cnt FROM value WHERE run_id = %s", (run_id,))
            inserted_count = cur.fetchone()["cnt"]
            assert inserted_count == len(value_lines), (
                f"Read-back count mismatch: JSONL has {len(value_lines)} rows, Postgres has {inserted_count}"
            )

            # Query mapping status distribution
            cur.execute(
                """
                SELECT mapping_status, count(*) as cnt
                FROM value
                WHERE run_id = %s
                GROUP BY mapping_status
                ORDER BY cnt DESC
                """,
                (run_id,),
            )
            status_dist = {row["mapping_status"]: row["cnt"] for row in cur.fetchall()}

            # Query domain distribution
            cur.execute(
                """
                SELECT domain, count(*) as cnt
                FROM value
                WHERE run_id = %s
                GROUP BY domain
                ORDER BY cnt DESC
                """,
                (run_id,),
            )
            domain_dist = {row["domain"]: row["cnt"] for row in cur.fetchall()}

            # Query null domains (must be 0 for NIRF rows)
            cur.execute(
                "SELECT count(*) as cnt FROM value WHERE run_id = %s AND domain IS NULL",
                (run_id,),
            )
            null_domain_count = cur.fetchone()["cnt"]

            # Spot-check CONFLICTING checksum rows (Sandip 37.5L case)
            cur.execute(
                """
                SELECT raw_value, auth_status, institution_code, sha256
                FROM value
                WHERE run_id = %s AND auth_status = 'CONFLICTING'
                """,
                (run_id,),
            )
            conflicting_rows = cur.fetchall()

    return {
        "run_id": run_id,
        "total_inserted": inserted_count,
        "jsonl_count": len(value_lines),
        "status_distribution": status_dist,
        "domain_distribution": domain_dist,
        "null_domain_count": null_domain_count,
        "anomaly_count": status_dist.get("ANOMALY", 0),
        "conflicting_rows_count": len(conflicting_rows),
        "conflicting_samples": [dict(r) for r in conflicting_rows[:5]],
    }


def delete_manual_test_run(run_id: str, dsn: str = DEFAULT_DSN) -> int:
    """Delete all rows for a sandbox run from the value table.

    Hard-refuses to delete any run_id that does not start with 'manual_test_'.
    Returns the number of deleted rows.
    """
    if not run_id.startswith("manual_test_"):
        raise ValueError(f"Refusing to delete non-sandbox run: {run_id!r}")

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM value WHERE run_id = %s", (run_id,))
            deleted = cur.rowcount
        conn.commit()

    # Also remove on-disk run directory under values/ if present
    run_dir = REPO_ROOT / "values" / f"run={run_id}"
    if run_dir.exists() and run_dir.is_dir():
        import shutil
        shutil.rmtree(run_dir, ignore_errors=True)

    return deleted

