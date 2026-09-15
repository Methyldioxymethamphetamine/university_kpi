"""scripts/app.py -- Flask presentation layer for NIRF Institutional Benchmarking.

Reuses acquire/, classify/, convert/, extract/, profiles/, fingerprint/ and
discovery/ directly. Implements a unified, modular UI architecture with Jinja2
templates and centralized CSS tokens.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import protego
import psycopg
from flask import Flask, redirect, render_template, request, url_for

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from acquire import manifestlog  # noqa: E402
from acquire.settings import USER_AGENT  # noqa: E402
from acquire.storage import raw_path, sha256_of, write_once  # noqa: E402
from classify.artifact import classify_artifact, manifest_path  # noqa: E402
from convert.artifact import CONVERTIBLE_LABELS, convert_artifact  # noqa: E402
from db.loader import DEFAULT_DSN, delete_manual_test_run, load_run_to_postgres  # noqa: E402
from extract.docling_source import load_docling_json  # noqa: E402
from extract.pipeline import extract_artifact, write_run  # noqa: E402
from fingerprint.matcher import MATCHED, known_profile_ids, match_document  # noqa: E402
from profiles.engine import load_profile  # noqa: E402

DSN = "host=localhost port=5433 dbname=kpi user=postgres password=kpi"
DOCS_ROOT = REPO_ROOT / "docs"
PAGE_SIZE = 50
DOMAIN_ORDER = ["FAC", "STU", "RES", "FIN", "PLC", "X", "ACA", "INT", "INF", "GOV", "ESG"]
DOMAIN_NAMES = {
    "FAC": "Faculty",
    "STU": "Student",
    "RES": "Research",
    "FIN": "Financial",
    "PLC": "Placement",
    "X": "Cross-cutting",
    "ACA": "Academic",
    "INT": "International",
    "INF": "Infrastructure",
    "GOV": "Governance",
    "ESG": "Sustainability",
}

app = Flask(
    __name__,
    template_folder=str(REPO_ROOT / "templates"),
    static_folder=str(REPO_ROOT / "static"),
)


def db():
    return psycopg.connect(DSN)


def ensure_schema_and_profiles(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute((REPO_ROOT / "db" / "schema.sql").read_text())
        for profile_id in known_profile_ids():
            profile = load_profile(profile_id)
            cur.execute(
                "INSERT INTO profile (profile_id, name, version, fingerprint, blocks, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (profile_id) DO NOTHING",
                (profile_id, profile.get("description", profile_id), "current",
                 json.dumps(profile.get("fingerprint", {})), json.dumps(profile.get("blocks", [])),
                 "scripts/app.py, reading profiles/*.yaml directly"),
            )
    conn.commit()


def compute_match_status(sha256: str) -> tuple[str, str | None]:
    """Fingerprint check against actual docling.json. Returns (match_status, profile_id)."""
    doc = load_docling_json(sha256)
    if doc is None:
        return "NONE", None
    fp = match_document(sha256, doc)
    if fp.outcome != MATCHED:
        return "NONE", None
    if fp.run and fp.run.incomplete:
        return "PARTIAL", fp.profile_id
    return "MATCH", fp.profile_id


def sync_artifact(conn: psycopg.Connection, manifest: dict) -> None:
    sha256 = manifest["sha256"]
    source_id = manifest.get("source_id") or "unknown"
    institution_code = manifest.get("institution_code") or "unknown"
    country = manifest.get("country") or "unknown"
    url = manifest.get("canonical_url") or ""

    run_entry = manifest.get("runs", [{}])[-1] if manifest.get("runs") else {}
    run_id = run_entry.get("run_id") or "unknown"
    fetched_at = run_entry.get("fetched_at") or datetime.now(timezone.utc).isoformat()
    http_status = run_entry.get("http_status") or 200
    content_type = run_entry.get("content_type")

    n_pages = None
    if manifest.get("convert") and manifest["convert"].get("n_pages") is not None:
        n_pages = manifest["convert"]["n_pages"]
    elif manifest.get("classify") and manifest["classify"].get("n_pages") is not None:
        n_pages = manifest["classify"]["n_pages"]

    classify_label = manifest.get("classify", {}).get("label") or "(not classified)"
    match_status, profile_id = compute_match_status(sha256)

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO source (source_id, country, institution_code, entry_type) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (source_id) DO NOTHING",
            (source_id, country, institution_code, "annual_report"),
        )
        cur.execute(
            """
            INSERT INTO artifact (sha256, source_id, url, run_id, fetched_at,
                                  http_status, content_type, n_pages,
                                  classify_label, profile_id, match_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (sha256) DO UPDATE SET
                profile_id = EXCLUDED.profile_id,
                match_status = EXCLUDED.match_status,
                classify_label = EXCLUDED.classify_label,
                n_pages = EXCLUDED.n_pages
            """,
            (sha256, source_id, url, run_id, fetched_at, http_status, content_type,
             n_pages, classify_label, profile_id, match_status),
        )
    conn.commit()


def sync_all_known_artifacts(conn: psycopg.Connection) -> int:
    n = 0
    for mp in sorted(DOCS_ROOT.glob("*/manifest.json")):
        manifest = json.loads(mp.read_text())
        before = manifest.get("sha256")
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM artifact WHERE sha256 = %s", (before,))
            already = cur.fetchone()
        sync_artifact(conn, manifest)
        if not already:
            n += 1
    return n


_INSTITUTION_NAME_CACHE: dict[str, str] = {}


def get_institution_human_name(code: str, manifest: dict | None = None) -> str:
    if manifest and manifest.get("institution_name"):
        return manifest["institution_name"]
    global _INSTITUTION_NAME_CACHE
    if not _INSTITUTION_NAME_CACHE:
        for mp in DOCS_ROOT.glob("*/manifest.json"):
            try:
                m = json.loads(mp.read_text())
                c = m.get("institution_code")
                n = m.get("institution_name")
                if c and n and c not in _INSTITUTION_NAME_CACHE:
                    _INSTITUTION_NAME_CACHE[c] = n
            except Exception:
                pass
        _INSTITUTION_NAME_CACHE.setdefault("IR-E-C-36995", "Sri Krishna College of Engineering and Technology")
        _INSTITUTION_NAME_CACHE.setdefault("IR-O-C-41520", "Sandip Institute of Technology & Research Centre")
        _INSTITUTION_NAME_CACHE.setdefault("IR-E-I-1480", "Thapar Institute of Engineering and Technology (Deemed-to-be-university)")
        _INSTITUTION_NAME_CACHE.setdefault("IR-E-C-16604", "Sri Sivasubramaniya Nadar College of Engineering")
        _INSTITUTION_NAME_CACHE.setdefault("IR-E-U-0456", "Indian Institute of Technology Madras")
        _INSTITUTION_NAME_CACHE.setdefault("IR-E-U-0391", "Birla Institute of Technology & Science - Pilani")
        _INSTITUTION_NAME_CACHE.setdefault("IR-E-I-1074", "Indian Institute of Technology Delhi")
        _INSTITUTION_NAME_CACHE.setdefault("IR-O-U-0306", "Indian Institute of Technology Bombay")
        _INSTITUTION_NAME_CACHE.setdefault("MIT", "Massachusetts Institute of Technology")
    return _INSTITUTION_NAME_CACHE.get(code, code)


def resolve_document_meta(manifest: dict) -> tuple[str, str]:
    code = manifest.get("institution_code") or ""
    url = manifest.get("canonical_url") or ""
    src = manifest.get("source_id") or ""
    cat = "Institutional"
    if "Overall" in url or "overall" in src or code.startswith("IR-O-"):
        cat = "Overall"
    elif "Engineering" in url or "engineering" in src or code.startswith("IR-E-"):
        cat = "Engineering"
    elif "Management" in url or code.startswith("IR-M-"):
        cat = "Management"
    elif "MIT" in code or "common_data_set" in src:
        cat = "Common Data Set"

    m = re.search(r'202[0-9]', url + " " + src)
    if m:
        year = m.group(0)
    elif manifest.get("period_value"):
        year = str(manifest.get("period_value"))
    else:
        year = "2025"
    return year, cat


def get_institutions_grouped() -> list[dict]:
    """Return unique institutions each with their list of acquired artifacts."""
    groups: dict[str, dict] = {}
    for mp in sorted(DOCS_ROOT.glob("*/manifest.json")):
        try:
            m = json.loads(mp.read_text())
            code = m.get("institution_code", "")
            if not code:
                continue
            sha256 = m.get("sha256", "")
            sha8 = sha256[:8]
            name = get_institution_human_name(code, m)
            year, cat = resolve_document_meta(m)
            if code not in groups:
                groups[code] = {"code": code, "name": name, "docs": []}
            groups[code]["docs"].append({
                "sha8": sha8, "sha256": sha256,
                "year": year, "category": cat,
            })
        except Exception:
            pass
    result = list(groups.values())
    result.sort(key=lambda x: x["name"])
    for g in result:
        g["docs"].sort(key=lambda d: d["year"])
    return result


def get_active_run_id() -> str:
    """Return the active reference run ID (demo_clean_8fixtures if present,
    or the latest recorded run in Postgres)."""
    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT run_id FROM value WHERE run_id = 'demo_clean_8fixtures'")
                if cur.fetchone():
                    return "demo_clean_8fixtures"
                cur.execute("SELECT run_id FROM value GROUP BY run_id ORDER BY run_id DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    return row[0]
    except Exception:
        pass
    return "demo_clean_8fixtures"


def _parse_row_col(item_id: str) -> str:
    """Extract Row R, Col C from item_id."""
    m = re.search(r':r(\d+)c(\d+)$', item_id)
    if m:
        return f"Row {m.group(1)}, Col {m.group(2)}"
    return ""


@app.context_processor
def inject_global_context():
    groups = get_institutions_grouped()
    inst_map = {g["code"]: g["name"] for g in groups}
    for c, n in _INSTITUTION_NAME_CACHE.items():
        if c not in inst_map:
            inst_map[c] = n
    return {
        "institution_groups": groups,
        "institution_names": inst_map,
        "domain_names": DOMAIN_NAMES,
        "active_run_id": get_active_run_id(),
    }


@app.template_filter("inst_name")
def inst_name_filter(code: str) -> str:
    return get_institution_human_name(code)


@app.template_filter("domain_name")
def domain_name_filter(code: str) -> str:
    return DOMAIN_NAMES.get(code, code)


# --------------------------------------------------------------------- #
# 01 OVERVIEW: DASHBOARD
# --------------------------------------------------------------------- #

@app.route("/")
def index():
    active_run = get_active_run_id()
    inst_filter = request.args.get("institution_code", "").strip()
    with db() as conn:
        ensure_schema_and_profiles(conn)
        newly_synced = sync_all_known_artifacts(conn)
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            if inst_filter:
                cur.execute("SELECT * FROM source WHERE institution_code = %s ORDER BY source_id", (inst_filter,))
                sources = cur.fetchall()
                cur.execute(
                    """
                    SELECT a.* FROM artifact a
                    JOIN source s ON a.source_id = s.source_id
                    WHERE s.institution_code = %s
                    ORDER BY a.source_id, a.fetched_at
                    """,
                    (inst_filter,),
                )
                artifacts = cur.fetchall()

                # Live pipeline health metrics for active run filtered by institution
                cur.execute("SELECT COUNT(*) AS total FROM value WHERE run_id = %s AND institution_code = %s", (active_run, inst_filter))
                total_value_rows = cur.fetchone()["total"]

                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM value
                    WHERE run_id = %s AND institution_code = %s AND mapping_status IN ('DIRECT', 'DERIVED', 'ANNEXURE', 'PARTIAL')
                    """,
                    (active_run, inst_filter),
                )
                n_mapped = cur.fetchone()["cnt"]

                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM value WHERE run_id = %s AND institution_code = %s AND auth_status = 'CONFLICTING'",
                    (active_run, inst_filter),
                )
                n_conflicting = cur.fetchone()["cnt"]

                cur.execute(
                    """
                    SELECT COUNT(DISTINCT (section, row_label)) AS cnt FROM value
                    WHERE run_id = %s AND institution_code = %s AND mapping_status = 'ORPHAN'
                    """,
                    (active_run, inst_filter),
                )
                n_orphans = cur.fetchone()["cnt"]
            else:
                cur.execute("SELECT * FROM source ORDER BY source_id")
                sources = cur.fetchall()
                cur.execute("SELECT * FROM artifact ORDER BY source_id, fetched_at")
                artifacts = cur.fetchall()

                # Live pipeline health metrics for active run
                cur.execute("SELECT COUNT(*) AS total FROM value WHERE run_id = %s", (active_run,))
                total_value_rows = cur.fetchone()["total"]

                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM value
                    WHERE run_id = %s AND mapping_status IN ('DIRECT', 'DERIVED', 'ANNEXURE', 'PARTIAL')
                    """,
                    (active_run,),
                )
                n_mapped = cur.fetchone()["cnt"]

                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM value WHERE run_id = %s AND auth_status = 'CONFLICTING'",
                    (active_run,),
                )
                n_conflicting = cur.fetchone()["cnt"]

                cur.execute(
                    """
                    SELECT COUNT(DISTINCT (section, row_label)) AS cnt FROM value
                    WHERE run_id = %s AND mapping_status = 'ORPHAN'
                    """,
                    (active_run,),
                )
                n_orphans = cur.fetchone()["cnt"]

    for src in sources:
        src["human_name"] = get_institution_human_name(src["institution_code"])

    artifacts_by_source: dict[str, list[dict]] = defaultdict(list)
    for a in artifacts:
        artifacts_by_source[a["source_id"]].append(a)

    stats = [
        {"value": len(sources), "label": "institutions in scope"},
        {"value": len(artifacts), "label": "acquired documents"},
        {"value": total_value_rows, "label": "fields extracted"},
        {"value": n_mapped, "label": "KPI codes mapped"},
        {"value": n_conflicting, "label": "discrepancy flags"},
        {"value": n_orphans, "label": "distinct orphan concepts"},
    ]

    return render_template(
        "pages/dashboard.html",
        active_nav="dashboard",
        heading="Dashboard",
        subheading=f"Executive Pipeline Overview &bull; Active Reference Run: {active_run}",
        stats=stats,
        sources=sources,
        artifacts=artifacts,
        artifacts_by_source=artifacts_by_source,
        total_value_rows=total_value_rows,
        newly_synced=newly_synced,
        inst_filter=inst_filter,
    )


# --------------------------------------------------------------------- #
# ARTIFACT DETAIL INSPECTION
# --------------------------------------------------------------------- #

@app.route("/artifact/<sha>")
def artifact_detail(sha: str):
    matches = list(DOCS_ROOT.glob(f"{sha}*/manifest.json"))
    if not matches and len(sha) >= 8:
        matches = list(DOCS_ROOT.glob(f"{sha[:8]}*/manifest.json"))
    if not matches:
        for g in get_institutions_grouped():
            if g["code"] == sha and g.get("docs"):
                return redirect(f"/artifact/{g['docs'][0]['sha8']}")
        return "<p>No artifact found</p>", 404

    manifest = json.loads(matches[0].read_text())
    sha256 = manifest["sha256"]
    sha8 = sha256[:8]
    label = manifest.get("classify", {}).get("label", "(not classified)")
    inst_name = get_institution_human_name(manifest.get("institution_code", ""), manifest)
    doc_year, doc_cat = resolve_document_meta(manifest)
    subheading = f"{doc_year} &bull; {doc_cat} Category &bull; Code: {manifest.get('institution_code', '')}"

    is_debug = request.args.get("debug") == "1"

    if load_docling_json(sha256) is None:
        return render_template(
            "pages/artifact_detail.html",
            active_nav="artifacts",
            heading=inst_name,
            subheading=subheading,
            inst_name=inst_name,
            sha8=sha8,
            sha256=sha256,
            manifest=manifest,
            label=label,
            is_converted=False,
            is_debug=is_debug,
            inst_groups=get_institutions_grouped(),
            canon_url=manifest.get("canonical_url", ""),
            stats=[],
            value_rows=[],
            checksum_rows=[],
        )

    result = extract_artifact(manifest)
    if result.error:
        return render_template(
            "pages/artifact_detail.html",
            active_nav="artifacts",
            heading=inst_name,
            subheading=subheading,
            inst_name=inst_name,
            sha8=sha8,
            sha256=sha256,
            manifest=manifest,
            label=label,
            is_converted=True,
            error_msg=result.error,
            is_debug=is_debug,
            inst_groups=get_institutions_grouped(),
            canon_url=manifest.get("canonical_url", ""),
            stats=[],
            value_rows=[],
            checksum_rows=[],
        )

    n_total = len(result.value_rows)
    n_reported = sum(1 for v in result.value_rows if v.dash_state != "DASH")
    n_not_reported = sum(1 for v in result.value_rows if v.dash_state == "DASH")
    n_checksums = len(result.checksum_rows)
    n_confirmed = sum(1 for c in result.checksum_rows if c.state == "CONFIRMED")
    n_pages = manifest.get("convert", {}).get("n_pages") or manifest.get("classify", {}).get("n_pages") or "—"

    stats = [
        {"value": n_total, "label": "fields extracted"},
        {"value": n_reported, "label": "values reported"},
        {"value": n_not_reported, "label": "not reported (dash)"},
        {"value": f"{n_confirmed} / {n_checksums}", "label": "checksums confirmed"},
        {"value": n_pages, "label": "document pages"},
    ]

    value_rows = []
    for v in result.value_rows:
        value_rows.append({
            "row_label": v.row_label,
            "column_label": v.column_label,
            "period_value": v.period_value,
            "dash_state": v.dash_state,
            "raw_value": v.raw_value,
            "normalized_value": v.normalized_value,
            "page_no": v.page_no,
            "bbox_json": json.dumps(v.bbox) if v.bbox else "null",
        })

    checksum_rows = []
    for c in result.checksum_rows:
        checksum_rows.append({
            "raw_value": c.raw_value,
            "digits_value": c.digits_value,
            "words_value": c.words_value,
            "state": c.state,
            "abstain_reason": c.abstain_reason,
            "page_no": c.page_no,
            "bbox_json": json.dumps(c.bbox) if c.bbox else "null",
        })

    latest_run = manifest.get("runs", [{}])[-1] if manifest.get("runs") else {}
    cross_check_info = ""
    if result.cross_check:
        cc = result.cross_check
        cross_check_info = f"\nP-11 Geometric Cross-Check: docling={cc.docling_pair_count}, geometric={cc.geometric_pair_count}, agrees={cc.agrees}"

    return render_template(
        "pages/artifact_detail.html",
        active_nav="artifacts",
        heading=inst_name,
        subheading=subheading,
        inst_name=inst_name,
        sha8=sha8,
        sha256=sha256,
        manifest=manifest,
        label=label,
        is_converted=True,
        error_msg=None,
        is_debug=is_debug,
        inst_groups=get_institutions_grouped(),
        canon_url=manifest.get("canonical_url", ""),
        stats=stats,
        value_rows=value_rows,
        checksum_rows=checksum_rows,
        n_confirmed=n_confirmed,
        latest_run_id=latest_run.get("run_id", "none"),
        cross_check_info=cross_check_info,
    )


# --------------------------------------------------------------------- #
# INSTITUTIONS CONTEXT (Redirected per information architecture)
# --------------------------------------------------------------------- #

@app.route("/institutes")
def institutes_hub():
    """Per prompt requirement: 'Institutions is removed as a standalone
    top-level product area and preserved as a contextual filter.'
    Redirects to dashboard or extraction browser."""
    return redirect(url_for("index"))


# --------------------------------------------------------------------- #
# AUDIT UTILITY: RUN REPORTS & HISTORY
# --------------------------------------------------------------------- #

@app.route("/runs")
def runs_index():
    """Run reports: list all run_ids with links into each view."""
    with db() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT run_id,
                       COUNT(*) AS total_rows,
                       COUNT(DISTINCT institution_code) AS institutions,
                       array_agg(DISTINCT institution_code ORDER BY institution_code) AS inst_codes,
                       MAX(run_id) AS run_id_sort
                FROM value
                GROUP BY run_id
                ORDER BY run_id DESC
                """
            )
            runs = cur.fetchall()

    return render_template(
        "pages/runs.html",
        active_nav="runs",
        heading="Run History &amp; Reports",
        subheading="Append-only extraction runs archive and audit trail",
        runs=runs,
    )


# --------------------------------------------------------------------- #
# 02 LAYER 1: EXTRACTION BROWSER
# --------------------------------------------------------------------- #

@app.route("/extracted")
def extracted_shortcut():
    return redirect(f"/run/{get_active_run_id()}/extracted")


@app.route("/run/<run_id>/extracted")
def run_extracted(run_id: str):
    inst_filter = request.args.get("institution_code", "").strip()
    section_filter = request.args.get("section", "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    offset = (page - 1) * PAGE_SIZE

    params: list = [run_id]
    where_extra = ""
    if inst_filter:
        params.append(f"%{inst_filter}%")
        where_extra += " AND v.institution_code ILIKE %s"
    if section_filter:
        params.append(f"%{section_filter}%")
        where_extra += " AND v.section ILIKE %s"

    with db() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(f"SELECT COUNT(*) AS cnt FROM value v WHERE v.run_id = %s{where_extra}", params)
            total = cur.fetchone()["cnt"]

            cur.execute(
                f"""
                SELECT v.value_id, v.institution_code, v.section,
                       v.item_id, v.raw_value, v.period_type, v.period_value,
                       v.auth_status, v.mapping_status, v.domain,
                       v.sha256, a.url, di.page_no
                FROM value v
                JOIN artifact a ON v.sha256 = a.sha256
                JOIN doc_item di ON v.item_id = di.item_id
                WHERE v.run_id = %s{where_extra}
                ORDER BY v.institution_code, v.section, v.value_id
                LIMIT %s OFFSET %s
                """,
                params + [PAGE_SIZE, offset],
            )
            raw_rows = cur.fetchall()

            cur.execute(
                "SELECT DISTINCT institution_code FROM value WHERE run_id = %s ORDER BY institution_code",
                (run_id,),
            )
            institutions = [r["institution_code"] for r in cur.fetchall()]

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    rows = []
    for r in raw_rows:
        r_dict = dict(r)
        r_dict["row_col"] = _parse_row_col(r["item_id"])
        rows.append(r_dict)

    query_parts = []
    if inst_filter:
        query_parts.append(f"institution_code={inst_filter}")
    if section_filter:
        query_parts.append(f"section={section_filter}")
    query_string = "&".join(query_parts)

    return render_template(
        "pages/extraction.html",
        active_nav="extracted",
        active_layer="extracted",
        run_id=run_id,
        heading="Extraction Browser",
        subheading=f"Layer 1: Raw Extracted Rows &bull; Run: {run_id}",
        rows=rows,
        institutions=institutions,
        inst_filter=inst_filter,
        section_filter=section_filter,
        page=page,
        total_pages=total_pages,
        total_rows=total,
        query_string=query_string,
    )


# --------------------------------------------------------------------- #
# LAYER 2: DOMAINS VIEW
# --------------------------------------------------------------------- #

@app.route("/domains")
def domains_shortcut():
    return redirect(f"/run/{get_active_run_id()}/domains")


@app.route("/run/<run_id>/domains")
def run_domains(run_id: str):
    inst_filter = request.args.get("institution_code", "").strip()
    with db() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            if inst_filter:
                cur.execute(
                    """
                    SELECT domain, COUNT(*) AS cnt
                    FROM value
                    WHERE run_id = %s AND institution_code = %s
                    GROUP BY domain
                    ORDER BY cnt DESC
                    """,
                    (run_id, inst_filter),
                )
                domain_counts = {r["domain"]: r["cnt"] for r in cur.fetchall()}

                cur.execute(
                    """
                    SELECT v.value_id, v.institution_code, v.section, v.domain,
                           v.item_id, v.raw_value, v.period_type, v.period_value,
                           v.auth_status, v.mapping_status, v.kpi_code,
                           v.sha256, a.url, di.page_no
                    FROM value v
                    JOIN artifact a ON v.sha256 = a.sha256
                    JOIN doc_item di ON v.item_id = di.item_id
                    WHERE v.run_id = %s AND v.institution_code = %s
                    ORDER BY v.domain NULLS LAST, v.institution_code, v.section, v.value_id
                    """,
                    (run_id, inst_filter),
                )
                rows = cur.fetchall()
            else:
                cur.execute(
                    """
                    SELECT domain, COUNT(*) AS cnt
                    FROM value
                    WHERE run_id = %s
                    GROUP BY domain
                    ORDER BY cnt DESC
                    """,
                    (run_id,),
                )
                domain_counts = {r["domain"]: r["cnt"] for r in cur.fetchall()}

                cur.execute(
                    """
                    SELECT v.value_id, v.institution_code, v.section, v.domain,
                           v.item_id, v.raw_value, v.period_type, v.period_value,
                           v.auth_status, v.mapping_status, v.kpi_code,
                           v.sha256, a.url, di.page_no
                    FROM value v
                    JOIN artifact a ON v.sha256 = a.sha256
                    JOIN doc_item di ON v.item_id = di.item_id
                    WHERE v.run_id = %s
                    ORDER BY v.domain NULLS LAST, v.institution_code, v.section, v.value_id
                    """,
                    (run_id,),
                )
                rows = cur.fetchall()

    total = sum(domain_counts.values())

    domain_summary = []
    for dom in DOMAIN_ORDER:
        cnt = domain_counts.get(dom, 0)
        if cnt > 0:
            pct = f"{100.0 * cnt / total:.1f}" if total else "0.0"
            domain_summary.append({
                "code": dom,
                "domain": dom,
                "name": DOMAIN_NAMES.get(dom, dom),
                "count": cnt,
                "pct": pct,
            })
    for dom, cnt in sorted(domain_counts.items()):
        if dom not in DOMAIN_ORDER:
            pct = f"{100.0 * cnt / total:.1f}" if total else "0.0"
            domain_summary.append({
                "code": dom or "unassigned",
                "domain": dom or "(Unassigned)",
                "name": DOMAIN_NAMES.get(dom, dom or "(Unassigned)"),
                "count": cnt,
                "pct": pct,
            })

    by_domain: dict[str, list] = defaultdict(list)
    for row in rows:
        by_domain[row["domain"] or "(Unassigned)"].append(row)

    domain_groups = []
    ordered_keys = [d for d in DOMAIN_ORDER if d in by_domain] + [k for k in sorted(by_domain.keys()) if k not in DOMAIN_ORDER]
    for dom in ordered_keys:
        domain_groups.append({
            "code": dom,
            "domain": dom,
            "name": DOMAIN_NAMES.get(dom, dom or "(Unassigned)"),
            "rows": by_domain[dom],
        })

    return render_template(
        "pages/domains.html",
        active_nav="domains",
        active_layer="domains",
        run_id=run_id,
        heading="Domains Grouping",
        subheading=f"Layer 2: Domain-Categorized Rows &bull; Run: {run_id}",
        total_rows=total,
        domain_counts=domain_counts,
        domain_summary=domain_summary,
        domain_groups=domain_groups,
        inst_filter=inst_filter,
    )


# --------------------------------------------------------------------- #
# 03 LAYER 3: DICTIONARY MAPPING
# --------------------------------------------------------------------- #

@app.route("/mapped")
def mapped_shortcut():
    return redirect(f"/run/{get_active_run_id()}/mapped")


@app.route("/run/<run_id>/mapped")
def run_mapped(run_id: str):
    inst_filter = request.args.get("institution_code", "").strip()
    with db() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            if inst_filter:
                cur.execute(
                    """
                    SELECT v.value_id, v.institution_code, v.section, v.domain,
                           v.kpi_code, v.mapping_status,
                           v.item_id, v.raw_value, v.normalized_value,
                           v.period_type, v.period_value,
                           v.auth_status, v.sha256, a.url, di.page_no
                    FROM value v
                    JOIN artifact a ON v.sha256 = a.sha256
                    JOIN doc_item di ON v.item_id = di.item_id
                    WHERE v.run_id = %s AND v.institution_code = %s
                      AND v.mapping_status IN ('DIRECT', 'DERIVED', 'ANNEXURE', 'PARTIAL')
                    ORDER BY v.kpi_code, v.institution_code, v.period_value, v.value_id
                    """,
                    (run_id, inst_filter),
                )
                rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM value v
                    WHERE v.run_id = %s AND v.institution_code = %s
                      AND v.mapping_status IN ('DIRECT', 'DERIVED', 'ANNEXURE', 'PARTIAL')
                      AND v.auth_status = 'CONFLICTING'
                    """,
                    (run_id, inst_filter),
                )
                n_conflicting = cur.fetchone()["cnt"]
            else:
                cur.execute(
                    """
                    SELECT v.value_id, v.institution_code, v.section, v.domain,
                           v.kpi_code, v.mapping_status,
                           v.item_id, v.raw_value, v.normalized_value,
                           v.period_type, v.period_value,
                           v.auth_status, v.sha256, a.url, di.page_no
                    FROM value v
                    JOIN artifact a ON v.sha256 = a.sha256
                    JOIN doc_item di ON v.item_id = di.item_id
                    WHERE v.run_id = %s
                      AND v.mapping_status IN ('DIRECT', 'DERIVED', 'ANNEXURE', 'PARTIAL')
                    ORDER BY v.kpi_code, v.institution_code, v.period_value, v.value_id
                    """,
                    (run_id,),
                )
                rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM value v
                    WHERE v.run_id = %s
                      AND v.mapping_status IN ('DIRECT', 'DERIVED', 'ANNEXURE', 'PARTIAL')
                      AND v.auth_status = 'CONFLICTING'
                    """,
                    (run_id,),
                )
                n_conflicting = cur.fetchone()["cnt"]

    by_kpi: dict[str, list] = defaultdict(list)
    for row in rows:
        r_dict = dict(row)
        r_dict["institution_name"] = get_institution_human_name(row["institution_code"])
        by_kpi[row["kpi_code"] or "(no code)"].append(r_dict)

    kpi_groups = []
    for code in sorted(by_kpi.keys()):
        kpi_groups.append({
            "code": code,
            "rows": by_kpi[code],
        })

    return render_template(
        "pages/mapping.html",
        active_nav="mapped",
        active_layer="mapped",
        run_id=run_id,
        heading="Dictionary Mapping",
        subheading=f"Layer 3: KPI Dictionary Mapped Rows &bull; Run: {run_id}",
        total_rows=len(rows),
        n_conflicting=n_conflicting,
        kpi_groups=kpi_groups,
        inst_filter=inst_filter,
    )


# --------------------------------------------------------------------- #
# 04 LAYER 4: ORPHAN CONCEPTS
# --------------------------------------------------------------------- #

@app.route("/orphans")
def orphans_shortcut():
    return redirect(f"/run/{get_active_run_id()}/orphans")


@app.route("/run/<run_id>/orphans")
def run_orphans(run_id: str):
    inst_filter = request.args.get("institution_code", "").strip()
    with db() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            if inst_filter:
                cur.execute(
                    """
                    SELECT v.section,
                           v.row_label AS label,
                           COUNT(*) AS raw_rows,
                           COUNT(DISTINCT v.institution_code) AS institutions,
                           array_agg(DISTINCT v.institution_code ORDER BY v.institution_code) AS inst_list,
                           MAX(v.domain) AS domain
                    FROM value v
                    WHERE v.run_id = %s AND v.institution_code = %s
                      AND v.mapping_status = 'ORPHAN'
                    GROUP BY v.section, v.row_label
                    ORDER BY raw_rows DESC, v.section, v.row_label
                    """,
                    (run_id, inst_filter),
                )
                orphan_groups = cur.fetchall()

                cur.execute(
                    """
                    SELECT v.value_id, v.institution_code, v.section,
                           v.raw_value, v.anomaly_reason, v.sha256, a.url, di.page_no
                    FROM value v
                    JOIN artifact a ON v.sha256 = a.sha256
                    JOIN doc_item di ON v.item_id = di.item_id
                    WHERE v.run_id = %s AND v.institution_code = %s
                      AND v.mapping_status = 'ANOMALY'
                    ORDER BY v.institution_code, v.section, v.value_id
                    """,
                    (run_id, inst_filter),
                )
                anomaly_rows = cur.fetchall()

                cur.execute(
                    "SELECT COUNT(DISTINCT institution_code) AS n FROM value WHERE run_id = %s AND institution_code = %s AND mapping_status = 'ORPHAN'",
                    (run_id, inst_filter),
                )
                n_institutions = cur.fetchone()["n"]
            else:
                cur.execute(
                    """
                    SELECT v.section,
                           v.row_label AS label,
                           COUNT(*) AS raw_rows,
                           COUNT(DISTINCT v.institution_code) AS institutions,
                           array_agg(DISTINCT v.institution_code ORDER BY v.institution_code) AS inst_list,
                           MAX(v.domain) AS domain
                    FROM value v
                    WHERE v.run_id = %s
                      AND v.mapping_status = 'ORPHAN'
                    GROUP BY v.section, v.row_label
                    ORDER BY raw_rows DESC, v.section, v.row_label
                    """,
                    (run_id,),
                )
                orphan_groups = cur.fetchall()

                cur.execute(
                    """
                    SELECT v.value_id, v.institution_code, v.section,
                           v.raw_value, v.anomaly_reason, v.sha256, a.url, di.page_no
                    FROM value v
                    JOIN artifact a ON v.sha256 = a.sha256
                    JOIN doc_item di ON v.item_id = di.item_id
                    WHERE v.run_id = %s
                      AND v.mapping_status = 'ANOMALY'
                    ORDER BY v.institution_code, v.section, v.value_id
                    """,
                    (run_id,),
                )
                anomaly_rows = cur.fetchall()

                cur.execute(
                    "SELECT COUNT(DISTINCT institution_code) AS n FROM value WHERE run_id = %s AND mapping_status = 'ORPHAN'",
                    (run_id,),
                )
                n_institutions = cur.fetchone()["n"]

    n_concepts = len(orphan_groups)
    n_anomalies = len(anomaly_rows)

    return render_template(
        "pages/orphans.html",
        active_nav="orphans",
        active_layer="orphans",
        run_id=run_id,
        heading="Orphan Concepts",
        subheading=f"Layer 4: Preserved Unmapped Disclosures &bull; Run: {run_id}",
        n_concepts=n_concepts,
        n_institutions=n_institutions,
        n_anomalies=n_anomalies,
        orphan_groups=orphan_groups,
        anomaly_rows=anomaly_rows,
        inst_filter=inst_filter,
    )


# --------------------------------------------------------------------- #
# 05 LAYER 5: VALIDATION & CHECKSUM
# --------------------------------------------------------------------- #

@app.route("/validation")
def validation_shortcut():
    return redirect(f"/run/{get_active_run_id()}/validation")


@app.route("/run/<run_id>/validation")
def run_validation(run_id: str):
    inst_filter = request.args.get("institution_code", "").strip()
    checksum_rows = []
    with db() as conn:
        with conn.cursor() as cur:
            if inst_filter:
                cur.execute(
                    "SELECT DISTINCT v.sha256, v.institution_code FROM value v WHERE v.run_id = %s AND v.institution_code = %s",
                    (run_id, inst_filter),
                )
            else:
                cur.execute(
                    "SELECT DISTINCT v.sha256, v.institution_code FROM value v WHERE v.run_id = %s",
                    (run_id,),
                )
            art_list = cur.fetchall()

    for sha, inst in art_list:
        matches = list(DOCS_ROOT.glob(f"{sha[:8]}*/manifest.json"))
        if matches:
            try:
                m = json.loads(matches[0].read_text())
                res = extract_artifact(m)
                for c in res.checksum_rows:
                    checksum_rows.append({
                        "institution_code": inst,
                        "raw_value": c.raw_value,
                        "digits_value": c.digits_value,
                        "words_value": c.words_value,
                        "state": c.state,
                        "abstain_reason": c.abstain_reason,
                        "page_no": c.page_no,
                        "sha256": sha,
                    })
            except Exception:
                pass

    n_confirmed = sum(1 for c in checksum_rows if c["state"] == "CONFIRMED")
    n_conflicting = sum(1 for c in checksum_rows if c["state"] == "CONFLICTING")
    n_unverified = sum(1 for c in checksum_rows if c["state"] == "UNVERIFIED")

    stats = [
        {"value": len(checksum_rows), "label": "validation pairs"},
        {"value": n_confirmed, "label": "confirmed matches"},
        {"value": n_conflicting, "label": "conflicting discrepancies"},
        {"value": n_unverified, "label": "abstained / unverified"},
    ]

    return render_template(
        "pages/validation.html",
        active_nav="validation",
        active_layer="validation",
        run_id=run_id,
        heading="Validation &amp; Checksums",
        subheading=f"Layer 5: Numerical vs. Verbal Consistency Checks &bull; Run: {run_id}",
        checksum_rows=checksum_rows,
        n_confirmed=n_confirmed,
        n_conflicting=n_conflicting,
        n_unverified=n_unverified,
        stats=stats,
        inst_filter=inst_filter,
    )


# --------------------------------------------------------------------- #
# 06 CLIENT-FACING: PRESIDENT BRIEF
# --------------------------------------------------------------------- #

@app.route("/brief")
@app.route("/president-brief")
def president_brief():
    return render_template(
        "pages/president_brief.html",
        active_nav="brief",
        heading="President Brief",
        subheading="Regulatory Compliance &amp; Institutional Salary Findings",
    )


# --------------------------------------------------------------------- #
# LIVE SCRAPE
# --------------------------------------------------------------------- #

def _robots_allows(url: str) -> tuple[bool, str]:
    origin = "/".join(url.split("/")[:3])
    try:
        req = urllib.request.Request(f"{origin}/robots.txt", headers={"User-Agent": USER_AGENT})
        body = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    except Exception as exc:
        return True, f"no robots.txt reachable ({exc!r}) -- proceeding"
    allowed = protego.Protego.parse(body).can_fetch(url, USER_AGENT)
    return allowed, "checked via protego"


@app.route("/scrape", methods=["GET", "POST"])
def scrape():
    if request.method == "GET":
        return render_template(
            "pages/scrape.html",
            active_nav="scrape",
            heading="Live Scrape",
            subheading="Synchronous acquisition, conversion, and classification pipeline",
            result=None,
        )

    url = request.form.get("url", "").strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        return render_template(
            "pages/scrape.html",
            active_nav="scrape",
            heading="Live Scrape",
            subheading="Error: Invalid URL",
            result={"url": url, "success": False, "error": "Invalid URL protocol (must start with http:// or https://)"},
        )

    allowed, reason = _robots_allows(url)
    if not allowed:
        return render_template(
            "pages/scrape.html",
            active_nav="scrape",
            heading="Live Scrape",
            subheading="Robots.txt Disallowed",
            result={"url": url, "success": False, "error": f"Robots.txt disallows fetching: {reason}"},
        )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        resp = urllib.request.urlopen(req, timeout=60)
        body = resp.read()
        status = resp.status
        content_type = resp.headers.get("Content-Type")
    except Exception as exc:
        return render_template(
            "pages/scrape.html",
            active_nav="scrape",
            heading="Live Scrape",
            subheading="Fetch Error",
            result={"url": url, "success": False, "error": f"Failed to fetch: {exc}"},
        )

    sha256 = sha256_of(body)
    path = raw_path(sha256, content_type)
    is_new = write_once(path, body)

    run_entry = {
        "run_id": f"app-scrape-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "url": url, "http_status": status, "content_type": content_type, "content_length": len(body),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "etag": resp.headers.get("ETag"), "last_modified": resp.headers.get("Last-Modified"),
    }
    manifestlog.append_run(
        sha256=sha256, source_id="app_adhoc_scrape", institution_code="ADHOC",
        institution_name="(pasted via /scrape)", country="unknown", canonical_url=url,
        period_type=None, period_value=None, run_entry=run_entry,
    )

    classify_record = classify_artifact(sha256)
    label = classify_record["label"]

    with db() as conn:
        ensure_schema_and_profiles(conn)
        manifest = json.loads(manifest_path(sha256).read_text())
        sync_artifact(conn, manifest)

    match_status, profile_id = compute_match_status(sha256)

    result = {
        "url": url,
        "success": True,
        "http_status": status,
        "content_length": len(body),
        "sha8": sha256[:8],
        "label": label,
        "is_new": is_new,
        "robots_msg": reason,
        "match_status": match_status,
        "profile_id": profile_id,
    }

    return render_template(
        "pages/scrape.html",
        active_nav="scrape",
        heading="Live Scrape",
        subheading="Acquisition Complete",
        result=result,
    )


# --------------------------------------------------------------------- #
# SAFE SANDBOX TESTING
# --------------------------------------------------------------------- #

def run_manual_sandbox_pipeline(url: str, auto_cleanup: bool = True) -> tuple[str, dict]:
    url = url.strip()
    if not url:
        raise ValueError("URL cannot be empty")

    content_type = "application/pdf"
    if url.startswith("fixture://"):
        fname = url.replace("fixture://", "")
        fpath = REPO_ROOT / "tests" / "fixtures" / fname
        if not fpath.exists():
            raise FileNotFoundError(f"Fixture file not found in tests/fixtures: {fname}")
        content = fpath.read_bytes()
    else:
        import requests
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=45)
        resp.raise_for_status()
        content = resp.content
        raw_ct = resp.headers.get("Content-Type", "application/pdf")
        content_type = raw_ct.split(";")[0].strip()

    sha256 = sha256_of(content)
    out_raw = raw_path(sha256, content_type)
    write_once(out_raw, content)

    institution_code = "TEST_INST"
    institution_name = f"Test Institution ({sha256[:8]})"
    period_value = None

    if "pdf" in content_type:
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(content)
            text0 = pdf[0].get_textpage().get_text_range()
            for line in text0.splitlines():
                if "Institute Name:" in line:
                    n_part = line.split("Institute Name:")[1].strip()
                    if "[" in n_part and "]" in n_part:
                        institution_name = n_part[:n_part.rfind("[")].strip()
                        institution_code = n_part[n_part.rfind("[")+1:n_part.rfind("]")].strip()
                    else:
                        institution_name = n_part
                    break
                elif "NIRF" in line:
                    m_yr = re.search(r'202\d', line)
                    if m_yr:
                        period_value = m_yr.group(0)
        except Exception:
            pass
    elif "html" in content_type:
        institution_code = "TEST_HTML"
        institution_name = "Test HTML Document"

    run_entry = {
        "run_id": "manual_test_ingest",
        "url": url,
        "http_status": 200,
        "content_type": content_type,
        "content_length": len(content),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    manifestlog.append_run(
        sha256=sha256,
        source_id=f"manual_test_{institution_code.lower()}",
        institution_code=institution_code,
        institution_name=institution_name,
        country="IN" if "pdf" in content_type else "US",
        canonical_url=url,
        period_type="academic_year",
        period_value=period_value,
        run_entry=run_entry,
    )

    m_path = manifest_path(sha256)
    manifest = json.loads(m_path.read_text(encoding="utf-8"))
    if not manifest.get("classify"):
        classify_artifact(sha256)
        manifest = json.loads(m_path.read_text(encoding="utf-8"))

    docling_path = DOCS_ROOT / sha256[:8] / "docling.json"
    if not docling_path.exists() or not manifest.get("convert"):
        convert_artifact(sha256)
        manifest = json.loads(m_path.read_text(encoding="utf-8"))

    clean_code = re.sub(r'[^A-Za-z0-9_-]', '', institution_code)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"manual_test_{clean_code}_{ts}_{uuid.uuid4().hex[:6]}"

    if auto_cleanup:
        with psycopg.connect(DEFAULT_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT run_id FROM value WHERE run_id LIKE %s AND institution_code = %s",
                    ("manual_test_%", institution_code),
                )
                prior_runs = [r[0] for r in cur.fetchall()]
        for pr in prior_runs:
            delete_manual_test_run(pr)

    res = extract_artifact(manifest)
    values_path, checksums_path = write_run(run_id, [res])
    report = load_run_to_postgres(run_id, values_path, checksums_path)
    return run_id, report


@app.route("/test", methods=["GET", "POST"])
def manual_test():
    if request.method == "POST":
        url = request.form.get("url", "").strip()
        auto_cleanup = bool(request.form.get("auto_cleanup"))
        if not url:
            return render_template(
                "pages/test_sandbox.html",
                active_nav="test",
                heading="Sandbox Testing",
                subheading="Error: URL required",
                error_msg="URL cannot be empty",
            ), 400
        try:
            run_id, _ = run_manual_sandbox_pipeline(url, auto_cleanup=auto_cleanup)
            return redirect(f"/test?run_id={run_id}&msg=success")
        except Exception as exc:
            return render_template(
                "pages/test_sandbox.html",
                active_nav="test",
                heading="Sandbox Testing",
                subheading="Pipeline Execution Error",
                error_msg=str(exc),
            ), 500

    run_id = request.args.get("run_id", "").strip()
    msg = request.args.get("msg", "").strip()
    deleted_run = request.args.get("deleted_run", "").strip()

    run_summary = None
    if run_id:
        with db() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(
                    "SELECT COUNT(*) as total_rows, COUNT(DISTINCT institution_code) as n_inst, COUNT(DISTINCT sha256) as n_sha FROM value WHERE run_id = %s",
                    (run_id,),
                )
                run_summary = cur.fetchone()

    return render_template(
        "pages/test_sandbox.html",
        active_nav="test",
        heading="Sandbox Testing",
        subheading="Safe, isolated document link testing",
        run_id=run_id,
        msg=msg,
        deleted_run=deleted_run,
        run_summary=run_summary,
    )


@app.route("/test/delete", methods=["POST"])
def manual_test_delete():
    run_id = request.form.get("run_id", "").strip()
    if not run_id.startswith("manual_test_"):
        return "Forbidden: delete is restricted to manual_test_ runs only", 403
    try:
        delete_manual_test_run(run_id)
        return redirect(f"/test?msg=deleted&deleted_run={run_id}")
    except Exception as exc:
        return f"Error deleting test run: {exc}", 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
