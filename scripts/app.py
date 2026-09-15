"""scripts/app.py -- single-file Flask app, the delivery artifact replacing
scripts/build_demo.py (deleted, along with demo_output/ -- the curated
per-KPI comparison is gone, not superseded by another curated view).

Reuses acquire/, classify/, convert/, extract/, profiles/, fingerprint/ and
discovery/ directly. Nothing in this file reimplements extraction, cell
classification, fingerprint matching or candidate scoring -- it calls those
modules and renders what they return.

Two independent display paths, deliberately not unified into one, because
they answer different questions:

  ROUTE 1 (browse) shows what extract/'s geometric parser (P2C, profile-
  agnostic -- it never needed a fingerprint match to run) already produced
  for an artifact this project has already converted. This is a raw,
  unmapped inventory view -- "here is everything extracted", not a claim
  that it's KPI-confirmed data (P-16: unmapped fields are still shown,
  with citations, not discarded).

  ROUTE 2 (scrape) is P-15's actual gate in action: a brand-new, never-seen
  document only gets its extraction *presented as trustworthy* if a known
  profile's fingerprint matches it (profiles/, fingerprint/). If nothing
  matches, this app does NOT fall back to showing P2C's raw geometric
  extraction as if it were reliable -- that would be exactly the
  "plausible, unrecognised-but-shown-anyway" failure P-15 exists to
  prevent. Instead it runs discovery/ and shows scored candidates, plainly
  labeled unreviewed (P-13: never auto-accept a candidate into a value row
  here, no matter the score).

Postgres (P2D's minimal demo-scoped schema, db/schema.sql -- see its own
top-of-file note) is used only for the `source`/`artifact` inventory Route
1 lists from ("from the source table", per instruction) -- it does not
store the extracted value/checksum rows themselves; those are always
computed live, straight from the modules that produce them, every time a
page is requested. No caching of extraction results anywhere in this file.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import re
import uuid
import protego
import psycopg
from flask import Flask, redirect, request

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from acquire import manifestlog  # noqa: E402
from acquire.settings import USER_AGENT  # noqa: E402
from acquire.storage import raw_path, sha256_of, write_once  # noqa: E402
from classify.artifact import classify_artifact, manifest_path  # noqa: E402
from convert.artifact import CONVERTIBLE_LABELS, ConversionSkipped, convert_artifact  # noqa: E402
from db.loader import DEFAULT_DSN, delete_manual_test_run, ensure_database_ready, load_run_to_postgres  # noqa: E402
from discovery.candidates import generate_candidates  # noqa: E402
from extract.docling_source import load_docling_json  # noqa: E402
from extract.pipeline import extract_artifact, write_run  # noqa: E402
from fingerprint.matcher import MATCHED, known_profile_ids, match_document  # noqa: E402
from profiles.engine import load_profile  # noqa: E402

DSN = "host=localhost port=5433 dbname=kpi user=postgres password=kpi"
DOCS_ROOT = REPO_ROOT / "docs"

app = Flask(__name__)

PAGE_HEAD = """<!doctype html><html><head><meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 1200px; margin: 1.5rem auto; padding: 0 1rem; color: #222; }}
  table {{ border-collapse: collapse; width: 100%; margin: 0.75rem 0 1.5rem; }}
  th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.85rem; vertical-align: top; }}
  th {{ background: #f2f2f2; }}
  a {{ color: #0645ad; }}
  .badge {{ display: inline-block; padding: 0.1rem 0.45rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }}
  .badge.match {{ background: #d4edda; color: #155724; }}
  .badge.none {{ background: #e2e3e5; color: #383d41; }}
  .badge.partial {{ background: #fff3cd; color: #856404; }}
  .badge.confirmed {{ background: #d4edda; color: #155724; }}
  .badge.conflicting {{ background: #f8d7da; color: #721c24; }}
  .badge.unverified {{ background: #fff3cd; color: #856404; }}
  .badge.unreviewed {{ background: #cfe2ff; color: #084298; }}
  .badge.direct {{ background: #d4edda; color: #155724; }}
  .badge.derived {{ background: #d1ecf1; color: #0c5460; }}
  .badge.annexure {{ background: #e2d9f3; color: #432874; }}
  .badge.orphan {{ background: #e2e3e5; color: #383d41; }}
  .badge.anomaly {{ background: #f5c6cb; color: #491217; }}
  code {{ background: #f2f2f2; padding: 0.05rem 0.3rem; border-radius: 3px; font-size: 0.85em; }}
  .note {{ background: #fff8e6; border-left: 3px solid #e0a800; padding: 0.6rem 0.9rem; margin: 0.75rem 0; font-size: 0.9rem; }}
  nav {{ margin-bottom: 1rem; font-size: 0.9rem; }}
  form input[type=text] {{ width: 480px; padding: 0.4rem; }}
  form button {{ padding: 0.4rem 1rem; }}
  /* CONFLICTING row highlight -- hard visual distinction, not just badge text */
  tr.row-conflicting {{ background: #fff0f0 !important; outline: 2px solid #c0392b; }}
  tr.row-conflicting td {{ border-color: #c0392b; }}
  .conflicting-banner {{ background: #f8d7da; border: 2px solid #c0392b; color: #721c24;
    padding: 0.5rem 0.9rem; margin: 0.5rem 0; font-weight: 600; border-radius: 4px; }}
  .summary-bar {{ background: #f8f9fa; border: 1px solid #dee2e6; padding: 0.5rem 1rem;
    margin: 0.5rem 0 1rem; border-radius: 4px; font-size: 0.9rem; }}
  .domain-header {{ background: #e9ecef; font-weight: 600; }}
  .pagination {{ margin: 0.5rem 0 1.5rem; }}
  .pagination a {{ margin-right: 0.4rem; }}
  .run-nav {{ background: #f8f9fa; border-bottom: 1px solid #dee2e6; padding: 0.4rem 0;
    margin-bottom: 1rem; font-size: 0.85rem; }}
  .run-nav a {{ margin-right: 0.8rem; }}
  .review-badge {{ display: inline-block; background: #ffc107; color: #212529;
    padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }}
</style></head><body>
<nav><a href="/">Browse artifacts</a> &nbsp;|&nbsp; <a href="/scrape">Scrape live</a> &nbsp;|&nbsp; <a href="/test">Sandbox testing</a> &nbsp;|&nbsp; <a href="/runs">Run reports</a></nav>
"""
PAGE_TAIL = "</body></html>"


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
    """Real fingerprint check against the actual docling.json, if one
    exists -- never a placeholder default. Returns (match_status, profile_id)."""
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
    """Insert this artifact's source+artifact rows if not already present.
    Never UPDATEs, never DELETEs (P-4/P-5) -- an artifact already in the
    table is left exactly as it was."""
    sha256 = manifest["sha256"]
    classify = manifest.get("classify")
    if classify is None:
        return  # never classified -- nothing to browse yet
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM artifact WHERE sha256 = %s", (sha256,))
        if cur.fetchone():
            return

        source_id = manifest.get("source_id") or "unknown"
        institution_code = manifest.get("institution_code") or "UNKNOWN"
        country = manifest.get("country") or "unknown"
        # [ASSUMED] entry_type inferred, not stored anywhere upstream --
        # the three registry-driven sources are 'pattern', anything else
        # (T3/T3b fixtures, a /scrape paste) is necessarily an ad hoc single
        # URL. Cosmetic only (browse-page metadata), not used by any query.
        entry_type = "pattern" if source_id in ("nirf_iitb_overall", "sandip_sitrc_overall", "mit_common_data_set_2025_26", "mit_common_data_set_2024_25") else "adhoc_url"
        cur.execute(
            "INSERT INTO source (source_id, country, institution_code, pattern, entry_type) "
            "VALUES (%s, %s, %s, NULL, %s) ON CONFLICT (source_id) DO NOTHING",
            (source_id, country, institution_code, entry_type),
        )

        runs = manifest.get("runs", [])
        latest = runs[-1] if runs else {}
        match_status, profile_id = compute_match_status(sha256)
        cur.execute(
            "INSERT INTO artifact (sha256, source_id, url, run_id, fetched_at, http_status, "
            "content_type, n_pages, classify_label, profile_id, match_status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (sha256, source_id, manifest.get("canonical_url", ""), latest.get("run_id", "unknown"),
             latest.get("fetched_at"), latest.get("http_status", 0), latest.get("content_type"),
             manifest.get("convert", {}).get("n_pages"), classify["label"], profile_id, match_status),
        )
    conn.commit()


def sync_all_known_artifacts(conn: psycopg.Connection) -> int:
    """The real inventory sync: every docs/<sha8>/manifest.json this
    project has ever produced (every institution acquired across every
    phase -- not a curated subset), inserted if not already present."""
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


# --------------------------------------------------------------------- #
# PRESENTATION DESIGN SYSTEM (Matching nirf-pipeline-ui-review.html)
# --------------------------------------------------------------------- #

MOCKUP_CSS = """
:root{
  --paper:#EFF1EC;
  --panel:#FFFFFF;
  --panel-alt:#F6F7F3;
  --ink:#1B231F;
  --ink-soft:#5C6560;
  --ink-faint:#8A9089;
  --rule:#D7DAD1;
  --rule-strong:#B9BEB3;
  --accent:#A8791E;
  --accent-soft:#F1E6CE;
  --ok:#2E6B4C;
  --ok-soft:#E3EDE6;
  --bad:#B4432A;
  --bad-soft:#F5E4DE;
  --neutral:#8A8578;
  --neutral-soft:#EDEBE4;
  --derived:#3B6E71;
  --derived-soft:#E1EBEA;
  --annexure:#6B4F6B;
  --annexure-soft:#EAE3EA;
  --serif: 'Source Serif 4', Georgia, serif;
  --sans: 'IBM Plex Sans', -apple-system, sans-serif;
  --mono: 'IBM Plex Mono', 'SF Mono', monospace;
  --radius: 3px;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;background:var(--paper);color:var(--ink);font-family:var(--sans);}
body{font-size:13.5px;line-height:1.5;}
a{color:inherit;}

.shell{display:flex;min-height:100vh;}
.sidebar{
  width:240px;flex:0 0 240px;background:var(--ink);color:#EEEFE9;
  display:flex;flex-direction:column;position:sticky;top:0;height:100vh;
}
.brand{padding:22px 20px 16px;border-bottom:1px solid rgba(255,255,255,0.12);}
.brand-mark{font-family:var(--serif);font-size:16px;font-weight:600;letter-spacing:.2px;line-height:1.25;color:#FFF;}
.brand-sub{font-family:var(--mono);font-size:10.5px;color:#A9AFA5;margin-top:5px;letter-spacing:.02em;}
nav.mainnav{padding:14px 10px;flex:1;overflow-y:auto;}
.nav-group-label{font-size:10px;color:#8D9389;padding:14px 10px 6px;letter-spacing:.05em;text-transform:uppercase;font-weight:600;}
.nav-group-label:first-child{padding-top:4px;}
.navitem{
  display:flex;align-items:center;gap:10px;width:100%;text-align:left;
  padding:8px 10px;border-radius:var(--radius);border:none;background:transparent;
  color:#D7DAD1;font-family:var(--sans);font-size:13px;cursor:pointer;margin-bottom:1px;
  text-decoration:none;
}
.navitem:hover{background:rgba(255,255,255,0.06);color:#FFF;}
.navitem.active{background:rgba(168,121,30,0.22);color:#F3E4C4;}
.navitem .n{font-family:var(--mono);font-size:10.5px;color:#8D9389;width:18px;flex:0 0 18px;}
.navitem.active .n{color:var(--accent);}
.sidebar-foot{padding:16px 20px;border-top:1px solid rgba(255,255,255,0.12);font-size:11px;color:#8D9389;line-height:1.4;}

.main{flex:1;min-width:0;display:flex;flex-direction:column;}
.topbar{
  background:var(--panel);border-bottom:1px solid var(--rule);
  padding:18px 36px;display:flex;align-items:center;justify-content:space-between;
  position:sticky;top:0;z-index:10;
}
.topbar-left h1{font-family:var(--serif);font-weight:600;font-size:21px;margin:0;color:var(--ink);}
.topbar-left .desc{color:var(--ink-soft);font-size:12.5px;margin-top:3px;}
.topbar-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;}

.content{padding:28px 36px 80px;max-width:1280px;width:100%;}

.docbtn{
  font-family:var(--sans);font-size:12px;padding:6px 12px;border-radius:var(--radius);
  border:1px solid var(--rule-strong);background:var(--panel);color:var(--ink-soft);
  cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:5px;font-weight:500;
}
.docbtn:hover{background:var(--panel-alt);color:var(--ink);}
.docbtn.active{background:var(--ink);color:#F3E4C4;border-color:var(--ink);}

.stats-row{display:flex;gap:1px;background:var(--rule);border:1px solid var(--rule);margin-bottom:24px;border-radius:var(--radius);overflow:hidden;}
.stat{background:var(--panel);flex:1;padding:14px 18px;}
.stat .num{font-family:var(--serif);font-size:24px;font-weight:600;color:var(--ink);}
.stat .lbl{font-size:11.5px;color:var(--ink-soft);margin-top:3px;}

.panel{background:var(--panel);border:1px solid var(--rule);border-radius:var(--radius);margin-bottom:24px;box-shadow:0 1px 2px rgba(0,0,0,0.02);}
.panel-head{padding:14px 18px;border-bottom:1px solid var(--rule);display:flex;justify-content:space-between;align-items:center;}
.panel-head h3{font-family:var(--serif);font-size:15px;font-weight:600;margin:0;display:flex;align-items:center;gap:8px;color:var(--ink);}
.panel-body{padding:18px;}
.panel-body.flush{padding:0;}

table.reg{width:100%;border-collapse:collapse;background:var(--panel);}
table.reg th{
  text-align:left;font-size:11px;font-weight:600;color:var(--ink-soft);
  padding:10px 14px;border-bottom:1px solid var(--rule-strong);white-space:nowrap;
  text-transform:uppercase;letter-spacing:0.04em;
}
table.reg td{padding:10px 14px;border-bottom:1px solid var(--rule);font-size:13px;vertical-align:middle;}
table.reg tr:last-child td{border-bottom:none;}
table.reg tbody tr:hover{background:var(--panel-alt);}

.mono{font-family:var(--mono);font-size:12px;}
.badge{
  display:inline-flex;align-items:center;gap:5px;font-size:11px;font-family:var(--sans);
  padding:2.5px 8px;border-radius:12px;font-weight:500;white-space:nowrap;
}
.dot{width:7px;height:7px;border-radius:50%;flex:0 0 7px;}
.dot.ok{background:var(--ok);} .dot.bad{background:var(--bad);} .dot.neutral{background:var(--neutral);}
.dot.derived{background:var(--derived);} .dot.annexure{background:var(--annexure);} .dot.accent{background:var(--accent);}

.badge.ok,.badge.confirmed,.badge.match,.badge.direct{background:var(--ok-soft);color:var(--ok);}
.badge.bad,.badge.conflicting,.badge.anomaly{background:var(--bad-soft);color:var(--bad);}
.badge.neutral,.badge.none,.badge.unverified,.badge.orphan{background:var(--neutral-soft);color:#6B6E63;}
.badge.derived{background:var(--derived-soft);color:var(--derived);}
.badge.annexure{background:var(--annexure-soft);color:var(--annexure);}
.badge.accent,.badge.partial,.badge.unreviewed{background:var(--accent-soft);color:#8C6414;}

.cite-link{font-family:var(--mono);font-size:11.5px;color:var(--derived);text-decoration:none;border-bottom:1px dotted var(--derived);}
.cite-link:hover{border-bottom-style:solid;}

details.reveal{margin-top:14px;border-top:1px dashed var(--rule-strong);padding-top:12px;}
details.reveal summary{cursor:pointer;font-size:12.5px;color:var(--derived);list-style:none;font-weight:500;}
details.reveal summary::before{content:"▸ ";}
details.reveal[open] summary::before{content:"▾ ";}
details.reveal .evidence-box{
  margin-top:10px;background:var(--panel-alt);border:1px solid var(--rule);border-radius:var(--radius);
  padding:12px 14px;font-family:var(--mono);font-size:11.5px;line-height:1.7;color:var(--ink);white-space:pre-wrap;
  word-break:break-all;
}

.val-primary{font-family:var(--mono);font-size:13px;font-weight:600;color:var(--ink);}
.val-muted{color:var(--ink-faint);font-style:italic;font-size:12.5px;}
.field-name{font-weight:500;font-size:13px;color:var(--ink);}
.field-sub{font-size:11.5px;color:var(--ink-soft);margin-top:2px;}
"""

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


def get_all_institution_artifacts() -> list[dict]:
    items = []
    seen = set()
    for mp in sorted(DOCS_ROOT.glob("*/manifest.json")):
        try:
            m = json.loads(mp.read_text())
            code = m.get("institution_code", "")
            sha256 = m.get("sha256", "")
            sha8 = sha256[:8]
            name = get_institution_human_name(code, m)
            year, cat = resolve_document_meta(m)
            key = (code, sha8)
            if key not in seen:
                seen.add(key)
                items.append({
                    "sha8": sha8,
                    "sha256": sha256,
                    "code": code,
                    "name": name,
                    "year": year,
                    "category": cat,
                })
        except Exception:
            pass
    items.sort(key=lambda x: x["name"])
    return items


def get_institutions_grouped() -> list[dict]:
    """Return one entry per unique institution (code), each with a list of
    their artifacts sorted by year. Used for the institution selector hub
    and the topbar dropdown."""
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


def render_presentation_shell(
    title: str,
    heading: str,
    subheading: str,
    content_html: str,
    active_nav: str = "artifacts",
    actions_html: str = "",
    run_id: str = "demo_clean_8fixtures",
    current_sha8: str = "",
) -> str:
    nav_items = [
        ("dashboard", "01", "Dashboard", "/runs"),
        ("institutes", "02", "Institutions", "/institutes"),
        ("artifacts", "03", "Inventory", "/"),
        ("extracted", "04", "Extraction Browser", f"/run/{run_id}/extracted"),
        ("domains", "05", "Domains", f"/run/{run_id}/domains"),
        ("mapped", "06", "Dictionary Mapping", f"/run/{run_id}/mapped"),
        ("orphans", "07", "Orphan Concepts", f"/run/{run_id}/orphans"),
        ("scrape", "08", "Scrape Live", "/scrape"),
        ("test", "09", "Sandbox Testing", "/test"),
    ]

    nav_links_html = []
    nav_links_html.append('<div class="nav-group-label">Overview</div>')
    for key, num, label, url in nav_items[:3]:
        is_active = ' active' if active_nav == key else ''
        nav_links_html.append(f'<a class="navitem{is_active}" href="{url}"><span class="n">{num}</span> {label}</a>')

    nav_links_html.append('<div class="nav-group-label">Four Layers</div>')
    for key, num, label, url in nav_items[3:7]:
        is_active = ' active' if active_nav == key else ''
        nav_links_html.append(f'<a class="navitem{is_active}" href="{url}"><span class="n">{num}</span> {label}</a>')

    nav_links_html.append('<div class="nav-group-label">Utilities</div>')
    for key, num, label, url in nav_items[7:]:
        is_active = ' active' if active_nav == key else ''
        nav_links_html.append(f'<a class="navitem{is_active}" href="{url}"><span class="n">{num}</span> {label}</a>')

    # Build the topbar institution selector
    inst_groups = get_institutions_grouped()
    inst_opts = ['<option value="">— Select institution —</option>']
    for g in inst_groups:
        first_sha8 = g["docs"][0]["sha8"] if g["docs"] else ""
        sel = ' selected' if any(d["sha8"] == current_sha8 for d in g["docs"]) else ''
        short_name = g["name"][:55] + '…' if len(g["name"]) > 55 else g["name"]
        doc_count = len(g["docs"])
        inst_opts.append(
            f'<option value="{first_sha8}"{sel}>'
            f'{escape(short_name)} ({doc_count} doc{"s" if doc_count != 1 else ""})</option>'
        )
    inst_selector = (
        '<select id="inst-nav-select" '
        'style="font-family:var(--sans);font-size:12px;padding:5px 10px;'
        'border-radius:var(--radius);border:1px solid var(--rule-strong);'
        'background:var(--panel);color:var(--ink);cursor:pointer;max-width:320px;" '
        'onchange="var v=this.value;if(v)window.location.href=\'/artifact/\'+v">'
        + ''.join(inst_opts)
        + '</select>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<meta name="description" content="NIRF Institutional Benchmarking Pipeline Review">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600;8..60,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
{MOCKUP_CSS}
</style>
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">NIRF Benchmarking</div>
      <div class="brand-sub">Pipeline System Review</div>
    </div>
    <nav class="mainnav">
      {"".join(nav_links_html)}
    </nav>
    <div class="sidebar-foot">NIRF Institutional Benchmarking<br>Executive Presentation UI</div>
  </aside>

  <div class="main">
    <div class="topbar">
      <div class="topbar-left">
        <h1>{heading}</h1>
        <div class="desc">{subheading}</div>
      </div>
      <div class="topbar-actions">
        <div style="display:flex;align-items:center;gap:6px;">
          <span style="font-size:11.5px;color:var(--ink-soft);white-space:nowrap;">Institution:</span>
          {inst_selector}
        </div>
        {actions_html}
      </div>
    </div>
    <div class="content">
      {content_html}
    </div>
  </div>
</div>
</body>
</html>"""


# --------------------------------------------------------------------- #
# ROUTE 1 -- browse everything actually scraped (Inventory)
# --------------------------------------------------------------------- #

@app.route("/")
def index():
    with db() as conn:
        ensure_schema_and_profiles(conn)
        newly_synced = sync_all_known_artifacts(conn)
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("SELECT * FROM source ORDER BY source_id")
            sources = cur.fetchall()
            cur.execute("SELECT * FROM artifact ORDER BY source_id, fetched_at")
            artifacts = cur.fetchall()

    if request.args.get("debug") == "1":
        by_source: dict[str, list[dict]] = {}
        for a in artifacts:
            by_source.setdefault(a["source_id"], []).append(a)

        html = [PAGE_HEAD.format(title="Inventory (Debug)")]
        html.append(f'<div class="note" style="margin-bottom:1rem;display:flex;justify-content:space-between;align-items:center;">'
                    f'<span><strong>Debug View</strong> &mdash; Raw source &amp; artifact columns</span>'
                    f'<a href="{request.path}">Switch to Presentation View &rarr;</a></div>')
        html.append(f"<h1>Everything actually scraped</h1>")
        for src in sources:
            arts = by_source.get(src["source_id"], [])
            html.append(f'<h2>{escape(src["institution_code"])} ({escape(src["source_id"])})</h2>')
            html.append("<table><thead><tr><th>sha256</th><th>URL</th><th>classify_label</th><th>match_status</th><th>pages</th><th>fetched_at</th><th></th></tr></thead><tbody>")
            for a in arts:
                badge = a["match_status"].lower()
                html.append(
                    f'<tr><td><code>{a["sha256"][:8]}</code></td>'
                    f'<td><a href="{escape(a["url"])}">{escape(a["url"][:70])}</a></td>'
                    f'<td>{escape(a["classify_label"])}</td>'
                    f'<td><span class="badge {badge}">{a["match_status"]}</span></td>'
                    f'<td>{a["n_pages"] if a["n_pages"] is not None else "?"}</td>'
                    f'<td>{a["fetched_at"]}</td>'
                    f'<td><a href="/artifact/{a["sha256"][:8]}?debug=1">raw debug</a></td></tr>'
                )
            html.append("</tbody></table>")
        html.append(PAGE_TAIL)
        return "".join(html)

    by_source: dict[str, list[dict]] = {}
    for a in artifacts:
        by_source.setdefault(a["source_id"], []).append(a)

    body = []
    body.append(f"""
    <div class="stats-row">
      <div class="stat"><div class="num">{len(sources)}</div><div class="lbl">universities / sources</div></div>
      <div class="stat"><div class="num">{len(artifacts)}</div><div class="lbl">acquired documents</div></div>
      <div class="stat"><div class="num">{newly_synced}</div><div class="lbl">newly synced this request</div></div>
    </div>
    """)

    body.append('<div class="panel">')
    body.append('<div class="panel-head"><h3>All Acquired Institutions &amp; Documents</h3><span class="mono" style="font-size:11.5px;color:var(--ink-faint);">Postgres inventory</span></div>')
    body.append('<div class="panel-body flush">')
    body.append('<table class="reg"><thead><tr>'
                '<th>University</th><th>Category / Source ID</th><th>Artifact SHA</th><th>Pages</th><th>Status</th><th>View</th>'
                '</tr></thead><tbody>')
    for src in sources:
        arts = by_source.get(src["source_id"], [])
        h_name = get_institution_human_name(src["institution_code"])
        for a in arts:
            sha8 = a["sha256"][:8]
            badge_cls = a["match_status"].lower()
            body.append(
                f'<tr>'
                f'<td><div><strong>{escape(h_name)}</strong></div><div class="mono" style="font-size:11px;color:var(--ink-soft);">{escape(src["institution_code"])} ({escape(src["country"])})</div></td>'
                f'<td><code style="font-size:11.5px;">{escape(src["source_id"])}</code></td>'
                f'<td><code style="font-weight:600;">{sha8}</code></td>'
                f'<td class="mono">{a["n_pages"] if a["n_pages"] is not None else "—"}</td>'
                f'<td><span class="badge {badge_cls}"><span class="dot {badge_cls}"></span>{escape(a["match_status"])}</span></td>'
                f'<td><a class="docbtn" href="/artifact/{sha8}">View Presentation &rarr;</a></td>'
                f'</tr>'
            )
    if not sources:
        body.append('<tr><td colspan="6"><em>No artifacts acquired yet.</em></td></tr>')
    body.append('</tbody></table></div></div>')

    return render_presentation_shell(
        title="Inventory — NIRF Benchmarking",
        heading="All Acquired Institutions",
        subheading=f"Live inventory: {len(sources)} institutions, {len(artifacts)} acquired documents across repositories",
        content_html="".join(body),
        active_nav="artifacts",
        actions_html=f'<a class="docbtn" href="{request.path}?debug=1">Debug View</a>',
    )


@app.route("/artifact/<sha>")
def artifact_detail(sha: str):
    matches = list(DOCS_ROOT.glob(f"{sha}*/manifest.json"))
    if not matches and len(sha) >= 8:
        matches = list(DOCS_ROOT.glob(f"{sha[:8]}*/manifest.json"))
    if not matches:
        return f"<p>No artifact found for sha={escape(sha)}</p>", 404
    manifest = json.loads(matches[0].read_text())
    sha256 = manifest["sha256"]
    label = manifest.get("classify", {}).get("label", "(not classified)")

    # Debug view preservation (?debug=1)
    if request.args.get("debug") == "1":
        html = [PAGE_HEAD.format(title=f"Debug: Artifact {sha[:8]}")]
        html.append(f'<div class="note" style="margin-bottom:1rem;display:flex;justify-content:space-between;align-items:center;">'
                    f'<span><strong>Debug View</strong> &mdash; Raw extractor &amp; Postgres columns</span>'
                    f'<a href="{request.path}">Switch to Presentation View &rarr;</a></div>')
        html.append(f"<h1>Artifact <code>{sha256}</code></h1>")
        html.append(f'<p>source_id={escape(manifest.get("source_id",""))} &middot; '
                    f'institution_code={escape(manifest.get("institution_code",""))} &middot; '
                    f'classify_label={escape(label)} &middot; '
                    f'url=<a href="{escape(manifest.get("canonical_url",""))}">{escape(manifest.get("canonical_url",""))}</a></p>')

        if load_docling_json(sha256) is None:
            html.append(f'<div class="note">This artifact has not been converted (label={escape(label)} -- '
                        f'no <code>docling.json</code> exists). Nothing to extract. Shown plainly, not omitted.</div>')
            html.append(PAGE_TAIL)
            return "".join(html)

        result = extract_artifact(manifest)
        if result.error:
            html.append(f'<div class="note">extract_artifact reported an error: {escape(result.error)}</div>')
            html.append(PAGE_TAIL)
            return "".join(html)

        html.append(f"<h2>Value rows ({len(result.value_rows)}) -- raw extracted fields, no KPI code assigned (P-16)</h2>")
        html.append("<table><thead><tr><th>row_label</th><th>column_label</th><th>raw_value</th>"
                    "<th>normalized_value</th><th>dash_state</th><th>period</th><th>page_no</th><th>bbox</th></tr></thead><tbody>")
        for v in result.value_rows:
            page_cell = v.page_no if v.page_no is not None else '<em>none (no per-page citation for this source type)</em>'
            bbox_cell = escape(json.dumps(v.bbox)) if v.bbox else '<em>none</em>'
            html.append(
                f"<tr><td>{escape(v.row_label or '')}</td><td>{escape(v.column_label or '')}</td>"
                f"<td>{escape(v.raw_value)}</td><td>{v.normalized_value if v.normalized_value is not None else ''}</td>"
                f"<td>{v.dash_state}</td><td>{escape(v.period_value or '')} ({v.period_type or 'none'})</td>"
                f"<td>{page_cell}</td><td>{bbox_cell}</td></tr>"
            )
        html.append("</tbody></table>")

        html.append(f"<h2>Checksum rows ({len(result.checksum_rows)}) -- digits(words) pairs, three-state (P-7)</h2>")
        html.append("<table><thead><tr><th>raw_value</th><th>digits</th><th>words</th><th>state</th>"
                    "<th>abstain_reason</th><th>page_no</th><th>bbox</th></tr></thead><tbody>")
        for c in result.checksum_rows:
            page_cell = c.page_no if c.page_no is not None else '<em>none</em>'
            bbox_cell = escape(json.dumps(c.bbox)) if c.bbox else '<em>none</em>'
            badge = c.state.lower()
            html.append(
                f"<tr><td>{escape(c.raw_value)}</td><td>{c.digits_value}</td>"
                f"<td>{c.words_value if c.words_value is not None else '(abstained)'}</td>"
                f'<td><span class="badge {badge}">{c.state}</span></td>'
                f"<td>{c.abstain_reason or ''}</td><td>{page_cell}</td><td>{bbox_cell}</td></tr>"
            )
        html.append("</tbody></table>")

        if result.cross_check:
            cc = result.cross_check
            html.append(f'<div class="note">P-11 geometric cross-check: docling={cc.docling_pair_count} '
                        f'geometric={cc.geometric_pair_count} agree={cc.agrees}</div>')

        html.append(PAGE_TAIL)
        return "".join(html)

    # Presentation view (default)
    inst_name = get_institution_human_name(manifest.get("institution_code", ""), manifest)
    doc_year, doc_cat = resolve_document_meta(manifest)
    subheading = f"{doc_year} &middot; {doc_cat} Category &middot; Ref: {escape(manifest.get('institution_code', ''))}"

    inst_groups = get_institutions_grouped()
    sha8_current = sha[:8]

    # Build document-level selector grouped by institution
    opt_list = ['<option value="">— Jump to a document —</option>']
    for g in inst_groups:
        opt_list.append(f'<optgroup label="{escape(g["name"])}">')
        for doc in g["docs"]:
            sel = " selected" if doc["sha8"] == sha8_current else ""
            label = f"{doc['year']} · {doc['category']} ({doc['sha8']})"
            opt_list.append(f'<option value="{doc["sha8"]}"{sel}>{escape(label)}</option>')
        opt_list.append('</optgroup>')

    actions = []
    canon_url = manifest.get("canonical_url", "")
    if canon_url and canon_url.startswith("http"):
        actions.append(f'<a class="docbtn" href="{escape(canon_url)}" target="_blank" rel="noopener">source PDF &#8599;</a>')
    actions.append(f'<a class="docbtn" href="{request.path}?debug=1">Debug view</a>')
    actions_html = "".join(actions)

    body = []

    # Document Selector Banner (within the institution)
    body.append(f"""
    <div style="background:var(--panel);border:1px solid var(--rule);padding:12px 18px;margin-bottom:20px;border-radius:var(--radius);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
      <div style="display:flex;align-items:center;gap:12px;">
        <label style="font-weight:500;color:var(--ink-soft);font-size:12.5px;white-space:nowrap;">Document:</label>
        <select class="docbtn" style="cursor:pointer;font-size:12.5px;padding:6px 12px;max-width:520px;" onchange="if(this.value) window.location.href='/artifact/'+this.value">
          {''.join(opt_list)}
        </select>
      </div>
      <a href="/institutes" style="font-size:12px;color:var(--derived);text-decoration:none;">&#8592; All Institutions</a>
    </div>
    """)

    if load_docling_json(sha256) is None:
        body.append(f'<div class="panel"><div class="panel-body">'
                    f'<p style="color:var(--ink-soft);margin:0;">This artifact has not been converted (classification: <code>{escape(label)}</code> &mdash; '
                    f'no <code>docling.json</code> exists). Nothing to extract.</p></div></div>')
        return render_presentation_shell(
            title=f"{inst_name} — Artifact",
            heading=escape(inst_name),
            subheading=subheading,
            content_html="".join(body),
            active_nav="artifacts",
            actions_html=actions_html,
        )

    result = extract_artifact(manifest)
    if result.error:
        body.append(f'<div class="panel"><div class="panel-body" style="background:var(--bad-soft);color:var(--bad);">'
                    f'extract_artifact reported an error: {escape(result.error)}</div></div>')
        return render_presentation_shell(
            title=f"{inst_name} — Artifact",
            heading=escape(inst_name),
            subheading=subheading,
            content_html="".join(body),
            active_nav="artifacts",
            actions_html=actions_html,
        )

    n_total = len(result.value_rows)
    n_reported = sum(1 for v in result.value_rows if v.dash_state != "DASH")
    n_not_reported = sum(1 for v in result.value_rows if v.dash_state == "DASH")
    n_checksums = len(result.checksum_rows)
    n_confirmed = sum(1 for c in result.checksum_rows if c.state == "CONFIRMED")
    n_pages = manifest.get("convert", {}).get("n_pages") or manifest.get("classify", {}).get("n_pages") or "—"

    body.append(f"""
    <div class="stats-row">
      <div class="stat"><div class="num">{n_total}</div><div class="lbl">fields extracted</div></div>
      <div class="stat"><div class="num">{n_reported}</div><div class="lbl">values reported</div></div>
      <div class="stat"><div class="num">{n_not_reported}</div><div class="lbl">not reported (dash)</div></div>
      <div class="stat"><div class="num">{n_confirmed} / {n_checksums}</div><div class="lbl">checksums confirmed</div></div>
      <div class="stat"><div class="num">{n_pages}</div><div class="lbl">document pages</div></div>
    </div>
    """)

    # Value rows table
    body.append('<div class="panel">')
    body.append(f'<div class="panel-head"><h3>Extracted Document Fields <span class="badge ok">{n_total} items</span></h3>'
                f'<span class="mono" style="font-size:11px;color:var(--ink-faint)">Layer 1: Geometric parse</span></div>')
    body.append('<div class="panel-body flush">')
    body.append('<table class="reg"><thead><tr>'
                '<th>Field / Program</th><th>Period</th><th>Extracted Value</th><th>Evidence</th>'
                '</tr></thead><tbody>')
    for v in result.value_rows:
        row_lbl = escape(v.row_label or '(unlabeled)')
        col_lbl = escape(v.column_label or '')
        period_lbl = escape(v.period_value or '')

        if col_lbl and col_lbl != period_lbl:
            field_display = f'<div class="field-name">{row_lbl}</div><div class="field-sub">{col_lbl}</div>'
        else:
            field_display = f'<div class="field-name">{row_lbl}</div>'

        period_display = f'<span class="mono">{period_lbl or col_lbl or "&mdash;"}</span>'

        if v.dash_state == "DASH":
            val_display = '<span class="val-muted">Not reported</span>'
        else:
            val_display = f'<span class="val-primary">{escape(v.raw_value)}</span>'

        page_str = f"p.{v.page_no}" if v.page_no is not None else "p.&mdash;"
        bbox_json = escape(json.dumps(v.bbox)) if v.bbox else "null"
        evidence_display = (
            f'<details class="reveal" style="margin:0;padding:0;border:none;">'
            f'<summary style="font-size:11px;color:var(--derived);">{page_str} &middot; bbox</summary>'
            f'<div class="evidence-box" style="margin-top:4px;padding:6px 8px;font-size:10.5px;">'
            f'page: {v.page_no}<br>bbox: {bbox_json}'
            f'</div></details>'
        )

        body.append(
            f'<tr>'
            f'<td>{field_display}</td>'
            f'<td>{period_display}</td>'
            f'<td>{val_display}</td>'
            f'<td>{evidence_display}</td>'
            f'</tr>'
        )
    body.append('</tbody></table></div></div>')

    # Checksums table
    if result.checksum_rows:
        body.append('<div class="panel">')
        body.append(f'<div class="panel-head"><h3>Validation &amp; Checksums <span class="badge ok">{n_confirmed} of {n_checksums} confirmed</span></h3>'
                    f'<span class="mono" style="font-size:11px;color:var(--ink-faint)">Digits &amp; Words encoding check</span></div>')
        body.append('<div class="panel-body flush">')
        body.append('<table class="reg"><thead><tr>'
                    '<th>Extracted Phrase</th><th>Digits</th><th>Words Value</th><th>Status</th><th>Evidence</th>'
                    '</tr></thead><tbody>')
        for c in result.checksum_rows:
            page_str = f"p.{c.page_no}" if c.page_no is not None else "p.&mdash;"
            bbox_json = escape(json.dumps(c.bbox)) if c.bbox else "null"

            if c.state == "CONFIRMED":
                badge_html = '<span class="badge ok"><span class="dot ok"></span>CONFIRMED</span>'
            elif c.state == "CONFLICTING":
                badge_html = '<span class="badge bad"><span class="dot bad"></span>CONFLICTING</span>'
            else:
                badge_html = f'<span class="badge neutral"><span class="dot neutral"></span>{escape(c.state)}</span>'

            words_val = escape(str(c.words_value)) if c.words_value is not None else '<span class="val-muted">(abstained)</span>'
            abstain_str = f"<br>abstain reason: {escape(c.abstain_reason)}" if c.abstain_reason else ""

            evidence_display = (
                f'<details class="reveal" style="margin:0;padding:0;border:none;">'
                f'<summary style="font-size:11px;color:var(--derived);">{page_str} &middot; bbox</summary>'
                f'<div class="evidence-box" style="margin-top:4px;padding:6px 8px;font-size:10.5px;">'
                f'page: {c.page_no}<br>bbox: {bbox_json}{abstain_str}'
                f'</div></details>'
            )

            body.append(
                f'<tr>'
                f'<td style="max-width:320px;">{escape(c.raw_value)}</td>'
                f'<td class="mono">{c.digits_value}</td>'
                f'<td class="mono">{words_val}</td>'
                f'<td>{badge_html}</td>'
                f'<td>{evidence_display}</td>'
                f'</tr>'
            )
        body.append('</tbody></table></div></div>')

    # Overall Document Provenance disclosure
    latest_run = manifest.get("runs", [{}])[-1] if manifest.get("runs") else {}
    cc_info = ""
    if result.cross_check:
        cc = result.cross_check
        cc_info = f"<br><strong>P-11 geometric cross-check:</strong> docling={cc.docling_pair_count} geometric={cc.geometric_pair_count} agree={cc.agrees}"

    body.append(f"""
    <details class="reveal" style="margin-top:20px;padding-top:16px;">
      <summary style="font-size:13px;font-weight:600;">Show raw extraction evidence</summary>
      <div class="evidence-box">
<strong>SHA256:</strong> {sha256}
<strong>Source ID:</strong> {escape(manifest.get("source_id", "none"))}
<strong>Institution Code:</strong> {escape(manifest.get("institution_code", "none"))}
<strong>Classification Label:</strong> {escape(label)}
<strong>Canonical URL:</strong> {escape(manifest.get("canonical_url", "none"))}
<strong>Internal Ingest Run ID:</strong> {escape(latest_run.get("run_id", "none"))}{cc_info}
      </div>
    </details>
    """)

    return render_presentation_shell(
        title=f"{inst_name} — NIRF Extraction",
        heading=escape(inst_name),
        subheading=subheading,
        content_html="".join(body),
        active_nav="artifacts",
        actions_html=actions_html,
        current_sha8=sha8_current,
    )




# --------------------------------------------------------------------- #
# ROUTE 1b -- Institution selector hub
# --------------------------------------------------------------------- #

@app.route("/institutes")
def institutes_hub():
    inst_groups = get_institutions_grouped()
    n_inst = len(inst_groups)
    n_docs = sum(len(g["docs"]) for g in inst_groups)

    body = []

    # Summary stats
    body.append(f"""
    <div class="stats-row">
      <div class="stat"><div class="num">{n_inst}</div><div class="lbl">institutions indexed</div></div>
      <div class="stat"><div class="num">{n_docs}</div><div class="lbl">documents acquired</div></div>
      <div class="stat"><div class="num">NIRF</div><div class="lbl">framework</div></div>
    </div>
    """)

    # Search / filter
    body.append("""
    <div style="margin-bottom:20px;display:flex;align-items:center;gap:10px;">
      <input id="inst-search" type="text" placeholder="Filter institutions..."
        style="font-family:var(--sans);font-size:13px;padding:8px 14px;border:1px solid var(--rule-strong);
               border-radius:var(--radius);background:var(--panel);color:var(--ink);width:340px;outline:none;"
        oninput="filterInstitutions(this.value)">
      <span id="inst-count" style="font-size:12px;color:var(--ink-soft);"></span>
    </div>
    """)

    # Institution cards grid
    body.append('<div id="inst-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;">')
    for g in inst_groups:
        code = g["code"]
        name = g["name"]
        docs = g["docs"]
        first_sha8 = docs[0]["sha8"] if docs else ""
        n_doc = len(docs)

        # Category chips
        cats = sorted({d["category"] for d in docs})
        years = sorted({d["year"] for d in docs})
        year_range = f"{years[0]}–{years[-1]}" if len(years) > 1 else (years[0] if years else "—")

        cat_badges = "".join(
            f'<span class="badge neutral" style="font-size:10.5px;padding:2px 7px;">{escape(c)}</span>'
            for c in cats
        )

        # Institution type from code
        if code.startswith("IR-E-"):
            type_badge = '<span class="badge derived" style="font-size:10px;">Engineering</span>'
        elif code.startswith("IR-O-"):
            type_badge = '<span class="badge accent" style="font-size:10px;">Overall</span>'
        elif code.startswith("IR-M-"):
            type_badge = '<span class="badge annexure" style="font-size:10px;">Management</span>'
        else:
            type_badge = '<span class="badge neutral" style="font-size:10px;">Institution</span>'

        doc_links = " ".join(
            f'<a href="/artifact/{d["sha8"]}" class="docbtn" style="font-size:11px;padding:4px 9px;">'
            f'{d["year"]} {d["category"]}</a>'
            for d in docs
        )

        body.append(f"""
        <div class="inst-card" data-name="{escape(name.lower())}"
          style="background:var(--panel);border:1px solid var(--rule);border-radius:var(--radius);
                 padding:18px 20px;display:flex;flex-direction:column;gap:12px;
                 transition:box-shadow .15s,border-color .15s;cursor:default;"
          onmouseover="this.style.boxShadow='0 3px 12px rgba(0,0,0,0.08)';this.style.borderColor='var(--rule-strong)'"
          onmouseout="this.style.boxShadow='';this.style.borderColor='var(--rule)'">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;">
            <div style="font-family:var(--serif);font-weight:600;font-size:14.5px;color:var(--ink);line-height:1.35;">{escape(name)}</div>
            {type_badge}
          </div>
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
            {cat_badges}
            <span style="font-size:11px;color:var(--ink-faint);">{year_range}</span>
          </div>
          <div style="font-family:var(--mono);font-size:10.5px;color:var(--ink-faint);">{escape(code)}</div>
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;border-top:1px solid var(--rule);padding-top:12px;">
            {doc_links}
          </div>
        </div>
        """)
    body.append("</div>")

    # JS for live filter
    body.append("""
    <script>
    function filterInstitutions(q) {
      q = q.toLowerCase().trim();
      var cards = document.querySelectorAll('.inst-card');
      var shown = 0;
      cards.forEach(function(c) {
        var match = !q || c.dataset.name.includes(q);
        c.style.display = match ? '' : 'none';
        if (match) shown++;
      });
      document.getElementById('inst-count').textContent =
        q ? shown + ' of ' + cards.length + ' institutions' : '';
    }
    </script>
    """)

    return render_presentation_shell(
        title="All Institutions — NIRF Benchmarking",
        heading="All Institutions",
        subheading=f"{n_inst} institutions · {n_docs} acquired documents · NIRF framework",
        content_html="".join(body),
        active_nav="institutes",
        actions_html='<a class="docbtn" href="/">Inventory Table</a>',
    )


# --------------------------------------------------------------------- #
# ROUTE 2 -- paste a link, scrape it live
# --------------------------------------------------------------------- #

@app.route("/scrape", methods=["GET"])
def scrape_form():
    html = [PAGE_HEAD.format(title="Scrape a URL")]
    html.append("<h1>Paste a link, scrape it live</h1>")
    html.append('<form method="post" action="/scrape">'
                '<input type="text" name="url" placeholder="https://example.org/some-nirf-submission.pdf" required>'
                '<button type="submit">Scrape</button></form>')
    html.append('<div class="note">This runs the real pipeline synchronously: fetch &rarr; classify &rarr; '
                "convert (Docling) &rarr; fingerprint. A large or slow PDF may take a while -- this page "
                "will not respond until it's done. Don't refresh.</div>")
    html.append(PAGE_TAIL)
    return "".join(html)


def _robots_allows(url: str) -> tuple[bool, str]:
    origin = "/".join(url.split("/")[:3])
    try:
        req = urllib.request.Request(f"{origin}/robots.txt", headers={"User-Agent": USER_AGENT})
        body = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001 -- no robots.txt reachable is not the same as "disallowed"
        return True, f"no robots.txt reachable ({exc!r}) -- proceeding"
    allowed = protego.Protego.parse(body).can_fetch(url, USER_AGENT)
    return allowed, "checked via protego"


@app.route("/scrape", methods=["POST"])
def scrape_run():
    url = request.form.get("url", "").strip()
    html = [PAGE_HEAD.format(title="Scrape result")]
    html.append(f"<h1>Scrape result for <code>{escape(url)}</code></h1>")

    if not url.startswith("http://") and not url.startswith("https://"):
        html.append('<div class="note">Not a valid http(s) URL.</div>')
        html.append(PAGE_TAIL)
        return "".join(html)

    allowed, reason = _robots_allows(url)
    html.append(f"<p>robots.txt check: {'allowed' if allowed else 'DISALLOWED'} ({escape(reason)})</p>")
    if not allowed:
        html.append('<div class="note">robots.txt disallows fetching this URL for this bot. '
                    "Not routed around -- stopping here, per this project's ROBOTSTXT_OBEY discipline "
                    "for any source outside the three iteration-1 institutions covered by the recorded "
                    "global override (CLAUDE.md \"Recorded decisions\").</div>")
        html.append(PAGE_TAIL)
        return "".join(html)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        resp = urllib.request.urlopen(req, timeout=60)
        body = resp.read()
        status = resp.status
        content_type = resp.headers.get("Content-Type")
    except urllib.error.HTTPError as exc:
        html.append(f'<div class="note">Real HTTP status: {exc.code} {escape(exc.reason)}. Stopping -- not faking a result.</div>')
        html.append(PAGE_TAIL)
        return "".join(html)
    except urllib.error.URLError as exc:
        html.append(f'<div class="note">Fetch failed: {escape(str(exc.reason))}. Stopping -- not faking a result.</div>')
        html.append(PAGE_TAIL)
        return "".join(html)

    sha256 = sha256_of(body)
    path = raw_path(sha256, content_type)
    is_new = write_once(path, body)
    html.append(f"<p>HTTP {status}, {len(body)} bytes, sha256=<code>{sha256[:8]}</code> "
                f"({'new file written' if is_new else 'already present, content-addressed match'})</p>")

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
    html.append(f"<p>classify: label=<code>{label}</code></p>")

    with db() as conn:
        ensure_schema_and_profiles(conn)
        manifest = json.loads(manifest_path(sha256).read_text())
        sync_artifact(conn, manifest)

    if label not in CONVERTIBLE_LABELS:
        html.append(f'<div class="note">classify labelled this <code>{escape(label)}</code>, which is not '
                    f"a convertible type in this iteration's scope (nothing to convert or extract). "
                    f'Synced into the inventory (<a href="/">browse</a>) with that label, plainly, not hidden.</div>')
        html.append(PAGE_TAIL)
        return "".join(html)

    try:
        convert_record = convert_artifact(sha256)
    except ConversionSkipped as exc:
        html.append(f'<div class="note">convert skipped: {escape(str(exc))}</div>')
        html.append(PAGE_TAIL)
        return "".join(html)
    html.append(f"<p>convert: n_tables={convert_record['n_tables']} n_texts={convert_record['n_texts']} "
                f"n_pages={convert_record['n_pages']}</p>")

    doc = load_docling_json(sha256)
    fp = match_document(sha256, doc)
    match_status, profile_id = compute_match_status(sha256)
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE artifact SET match_status = %s, profile_id = %s WHERE sha256 = %s",
                        (match_status, profile_id, sha256))
        conn.commit()

    html.append(f"<h2>Fingerprint: {fp.outcome}{f', profile={fp.profile_id}' if fp.profile_id else ''}</h2>")

    if fp.outcome == MATCHED and fp.run and not fp.run.incomplete:
        html.append(f'<p><span class="badge match">MATCH</span> -- applying <code>{fp.profile_id}</code>, '
                    f"showing extracted value rows with citations, same as the browse view.</p>")
        html.append(f"<h3>Value rows ({len(fp.run.value_rows)})</h3>")
        html.append("<table><thead><tr><th>row_label</th><th>column_label</th><th>raw_value</th>"
                    "<th>page_no</th><th>bbox</th></tr></thead><tbody>")
        for v in fp.run.value_rows:
            html.append(f"<tr><td>{escape(v.row_label or '')}</td><td>{escape(v.column_label or '')}</td>"
                        f"<td>{escape(v.raw_value)}</td><td>{v.page_no}</td><td>{escape(json.dumps(v.bbox))}</td></tr>")
        html.append("</tbody></table>")
        html.append(f"<h3>Checksum rows ({len(fp.run.checksum_rows)})</h3>")
        html.append("<table><thead><tr><th>raw_value</th><th>state</th><th>page_no</th></tr></thead><tbody>")
        for c in fp.run.checksum_rows:
            badge = c.state.lower()
            html.append(f'<tr><td>{escape(c.raw_value)}</td><td><span class="badge {badge}">{c.state}</span></td>'
                        f"<td>{c.page_no}</td></tr>")
        html.append("</tbody></table>")
    else:
        candidates = generate_candidates(sha256, doc)
        if not candidates:
            html.append('<div class="note"><strong>No structured KPI-shaped data found on this page.</strong> '
                        "0 candidate fields (P-15: stated explicitly, not shown as an empty table implying success).</div>")
        else:
            scored = sorted((c for c in candidates if c.suggestions), key=lambda c: -c.suggestions[0].score)
            html.append(f'<p><span class="badge none">{fp.outcome}</span> -- no known profile matched. '
                        f"Discovery mode: {len(candidates)} candidate field(s), {len(scored)} with a scored "
                        f'suggestion. <span class="badge unreviewed">UNREVIEWED</span> -- no KPI code assigned '
                        f"automatically (P-13), regardless of score.</p>")
            html.append("<table><thead><tr><th>label</th><th>value</th><th>top suggestion</th><th>score</th>"
                        "<th>contestable</th></tr></thead><tbody>")
            for c in scored[:100]:
                top = c.suggestions[0]
                html.append(f"<tr><td>{escape(c.label)}</td><td>{escape(c.value)}</td>"
                            f"<td>{top.kpi_code} ({escape(top.kpi_label)})</td><td>{top.score}</td>"
                            f"<td>{top.contestable}</td></tr>")
            html.append("</tbody></table>")
            unscored = len(candidates) - len(scored)
            if unscored:
                html.append(f"<p>{unscored} further candidate field(s) had zero token-overlap with the KPI "
                            "dictionary -- not listed individually.</p>")

    html.append(PAGE_TAIL)
    return "".join(html)


# --------------------------------------------------------------------- #
# REPORT ROUTES -- 4-layer presentation over the value table (read-only)
# Per-run: all routes take run_id as a path param so old runs stay
# viewable after re-extraction (append-only / never-UPDATE rule).
# --------------------------------------------------------------------- #

PAGE_SIZE = 100  # rows per page for /extracted

DOMAIN_ORDER = ["FAC", "STU", "RES", "FIN", "PLC", "X", "ACA", "INT", "INF", "GOV", "ESG"]


def _run_nav(run_id: str) -> str:
    """Small nav bar linking between the 4 views for a given run."""
    r = escape(run_id)
    return (
        f'<div class="run-nav">'
        f'Run: <code>{r}</code> &nbsp;&mdash;&nbsp; '
        f'<a href="/run/{r}/extracted">extracted</a> '
        f'<a href="/run/{r}/domains">domains</a> '
        f'<a href="/run/{r}/mapped">mapped</a> '
        f'<a href="/run/{r}/orphans">orphans</a>'
        f'</div>'
    )


def _source_citation(url: str, sha256: str) -> str:
    """Build the traceable source citation for a row.
    If url is a fixture:// or local path, show the sha8 reference.
    If url is http(s), show a clickable link plus sha8.
    Every row shown in the UI carries this -- hard requirement.
    """
    sha8 = sha256[:8]
    if url and url.startswith("http"):
        return f'<a href="{escape(url)}" title="{escape(sha256)}">{escape(url[:60])}</a> <code>{sha8}</code>'
    # fixture:// or other local reference
    label = url or f"sha256:{sha8}"
    return f'<code title="{escape(sha256)}">{escape(label)}</code> <code>{sha8}</code>'


def _auth_badge(auth_status: str) -> str:
    css = auth_status.lower()
    return f'<span class="badge {css}">{escape(auth_status)}</span>'


def _mapping_badge(mapping_status: str) -> str:
    css = (mapping_status or "orphan").lower()
    return f'<span class="badge {css}">{escape(mapping_status or "")}</span>'


def _parse_row_col(item_id: str) -> tuple[str, str]:
    """Extract row/col index from item_id like sha256:#/tables/N:rRcC.
    Returns ("Row R", "Col C") or ("", "") if unparseable."""
    import re
    m = re.search(r':r(\d+)c(\d+)$', item_id)
    if m:
        return f"Row {m.group(1)}", f"Col {m.group(2)}"
    return "", ""


@app.route("/runs")
def runs_index():
    """Landing page: list all run_ids with links to each of the 4 views."""
    with db() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT run_id,
                       COUNT(*) AS total_rows,
                       COUNT(DISTINCT institution_code) AS institutions,
                       MAX(run_id) AS run_id_sort
                FROM value
                GROUP BY run_id
                ORDER BY run_id DESC
                """
            )
            runs = cur.fetchall()

    html = [PAGE_HEAD.format(title="Run Reports")]
    html.append("<h1>Run Reports</h1>")
    html.append(
        '<p>Each row is one extraction run. Click a view to explore that run. '
        'Old runs remain viewable after re-extraction (append-only data, per project rule).</p>'
    )
    html.append(
        "<table><thead><tr>"
        "<th>run_id</th><th>total rows</th><th>institutions</th>"
        "<th>extracted</th><th>domains</th><th>mapped</th><th>orphans</th>"
        "</tr></thead><tbody>"
    )
    for row in runs:
        r = escape(row["run_id"])
        html.append(
            f"<tr>"
            f"<td><code>{r}</code></td>"
            f"<td>{row['total_rows']}</td>"
            f"<td>{row['institutions']}</td>"
            f"<td><a href='/run/{r}/extracted'>extracted</a></td>"
            f"<td><a href='/run/{r}/domains'>domains</a></td>"
            f"<td><a href='/run/{r}/mapped'>mapped</a></td>"
            f"<td><a href='/run/{r}/orphans'>orphans</a></td>"
            f"</tr>"
        )
    if not runs:
        html.append("<tr><td colspan='7'><em>No runs found in value table.</em></td></tr>")
    html.append("</tbody></table>")
    html.append(PAGE_TAIL)
    return "".join(html)


@app.route("/run/<run_id>/extracted")
def run_extracted(run_id: str):
    """Layer 1: every extracted row for this run, raw, with full source citation.
    Paginated (PAGE_SIZE rows/page). Filterable by institution_code and section.
    """
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
        where_extra += f" AND v.institution_code ILIKE %s"
    if section_filter:
        params.append(f"%{section_filter}%")
        where_extra += f" AND v.section ILIKE %s"

    with db() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM value v
                WHERE v.run_id = %s{where_extra}
                """,
                params,
            )
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
            rows = cur.fetchall()

            # Institution list for filter dropdown
            cur.execute(
                "SELECT DISTINCT institution_code FROM value WHERE run_id = %s ORDER BY institution_code",
                (run_id,),
            )
            institutions = [r["institution_code"] for r in cur.fetchall()]

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    run_e = escape(run_id)

    html = [PAGE_HEAD.format(title=f"Extracted — {run_id}")]
    html.append(_run_nav(run_id))
    html.append(f"<h1>Layer 1: All Extracted Rows</h1>")

    # Filter form
    html.append('<form method="get" style="margin-bottom:0.75rem">')
    html.append(
        f'<label>Institution: <select name="institution_code">'
        f'<option value="">(all)</option>'
    )
    for inst in institutions:
        sel = 'selected' if inst == inst_filter else ''
        html.append(f'<option value="{escape(inst)}" {sel}>{escape(inst)}</option>')
    html.append('</select></label> &nbsp;')
    html.append(
        f'<label>Section contains: <input type="text" name="section" '
        f'value="{escape(section_filter)}" style="width:280px"></label> &nbsp;'
    )
    html.append('<button type="submit">Filter</button>')
    html.append('</form>')

    html.append(
        f'<div class="summary-bar">'
        f'Run <code>{run_e}</code> &mdash; '
        f'<strong>{total}</strong> rows matching filter &mdash; '
        f'page {page} of {total_pages} &mdash; '
        f'<a href="/runs">all runs</a>'
        f'</div>'
    )

    # Pagination
    def _pg_link(p: int, label: str) -> str:
        base = f"/run/{run_e}/extracted?page={p}"
        if inst_filter:
            base += f"&institution_code={escape(inst_filter)}"
        if section_filter:
            base += f"&section={escape(section_filter)}"
        return f'<a href="{base}">{label}</a>'

    pag = []
    if page > 1:
        pag.append(_pg_link(page - 1, "&laquo; prev"))
    for p in range(max(1, page - 3), min(total_pages + 1, page + 4)):
        pag.append(_pg_link(p, f"<strong>[{p}]</strong>" if p == page else str(p)))
    if page < total_pages:
        pag.append(_pg_link(page + 1, "next &raquo;"))
    html.append(f'<div class="pagination">{" ".join(pag)}</div>')

    html.append(
        "<table><thead><tr>"
        "<th>institution</th><th>section</th><th>row pos</th><th>col pos</th>"
        "<th>raw_value</th><th>period</th>"
        "<th>auth_status</th><th>mapping</th><th>source (doc + sha8)</th>"
        "</tr></thead><tbody>"
    )
    for row in rows:
        row_pos, col_pos = _parse_row_col(row["item_id"])
        period = ""
        if row["period_value"] or row["period_type"]:
            period = f"{escape(row['period_value'] or '')} ({escape(row['period_type'] or '')})"
        citation = _source_citation(row["url"] or "", row["sha256"])
        if row["page_no"] is not None:
            citation += f' p.{row["page_no"]}'
        html.append(
            f"<tr>"
            f"<td><code>{escape(row['institution_code'])}</code></td>"
            f"<td>{escape(row['section'] or '')}</td>"
            f"<td>{escape(row_pos)}</td>"
            f"<td>{escape(col_pos)}</td>"
            f"<td><strong>{escape(row['raw_value'])}</strong></td>"
            f"<td style='white-space:nowrap'>{period}</td>"
            f"<td>{_auth_badge(row['auth_status'])}</td>"
            f"<td>{_mapping_badge(row['mapping_status'])}</td>"
            f"<td style='font-size:0.8rem'>{citation}</td>"
            f"</tr>"
        )
    html.append("</tbody></table>")
    html.append(f'<div class="pagination">{" ".join(pag)}</div>')
    html.append(PAGE_TAIL)
    return "".join(html)


@app.route("/run/<run_id>/domains")
def run_domains(run_id: str):
    """Layer 2: rows grouped by domain with row count per domain at top.
    Uses the same GROUP BY domain logic as the reconciliation loader --
    domain is stored per-row in the value table (resolved at load time).
    """
    with db() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            # Domain summary (same GROUP BY as loader read-back)
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

            # All rows, ordered by domain then institution
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
    run_e = escape(run_id)

    html = [PAGE_HEAD.format(title=f"Domains — {run_id}")]
    html.append(_run_nav(run_id))
    html.append("<h1>Layer 2: Domain-Sorted View</h1>")
    html.append(
        f'<div class="summary-bar">Run <code>{run_e}</code> &mdash; '
        f'<strong>{total}</strong> rows across <strong>{len(domain_counts)}</strong> domains</div>'
    )

    # Domain count summary table at top
    html.append("<h2>Row counts by domain</h2>")
    html.append("<table style='width:auto'><thead><tr><th>domain</th><th>rows</th><th>% of total</th></tr></thead><tbody>")
    for dom in DOMAIN_ORDER:
        cnt = domain_counts.get(dom, 0)
        if cnt == 0:
            continue
        pct = f"{100.0 * cnt / total:.1f}" if total else "0.0"
        html.append(f"<tr><td><strong>{escape(dom)}</strong></td><td>{cnt}</td><td>{pct}%</td></tr>")
    # Any domains not in canonical list
    for dom, cnt in sorted(domain_counts.items()):
        if dom not in DOMAIN_ORDER:
            pct = f"{100.0 * cnt / total:.1f}" if total else "0.0"
            html.append(f"<tr><td><em>{escape(str(dom))}</em></td><td>{cnt}</td><td>{pct}%</td></tr>")
    html.append("</tbody></table>")

    # Group rows by domain for expandable sections
    from collections import defaultdict
    by_domain: dict[str, list] = defaultdict(list)
    for row in rows:
        by_domain[row["domain"] or "(null)"].append(row)

    html.append("<h2>Rows by domain</h2>")
    for dom in DOMAIN_ORDER + sorted(k for k in by_domain if k not in DOMAIN_ORDER):
        dom_rows = by_domain.get(dom, [])
        if not dom_rows:
            continue
        section_id = f"dom-{escape(dom)}"
        html.append(
            f'<details id="{section_id}" style="margin-bottom:1rem">'
            f'<summary class="domain-header" style="cursor:pointer;padding:0.4rem 0.6rem;border:1px solid #ccc">'
            f'{escape(dom)} &mdash; {len(dom_rows)} rows'
            f'</summary>'
        )
        html.append(
            "<table><thead><tr>"
            "<th>institution</th><th>section</th><th>raw_value</th>"
            "<th>period</th><th>auth</th><th>mapping</th><th>kpi_code</th>"
            "<th>source (doc + sha8)</th>"
            "</tr></thead><tbody>"
        )
        for row in dom_rows:
            period = ""
            if row["period_value"] or row["period_type"]:
                period = f"{escape(row['period_value'] or '')} ({escape(row['period_type'] or '')})"
            citation = _source_citation(row["url"] or "", row["sha256"])
            if row["page_no"] is not None:
                citation += f' p.{row["page_no"]}'
            html.append(
                f"<tr>"
                f"<td><code>{escape(row['institution_code'])}</code></td>"
                f"<td>{escape(row['section'] or '')}</td>"
                f"<td><strong>{escape(row['raw_value'])}</strong></td>"
                f"<td style='white-space:nowrap'>{period}</td>"
                f"<td>{_auth_badge(row['auth_status'])}</td>"
                f"<td>{_mapping_badge(row['mapping_status'])}</td>"
                f"<td><code>{escape(row['kpi_code'] or '')}</code></td>"
                f"<td style='font-size:0.8rem'>{citation}</td>"
                f"</tr>"
            )
        html.append("</tbody></table></details>")

    html.append(PAGE_TAIL)
    return "".join(html)


@app.route("/run/<run_id>/mapped")
def run_mapped(run_id: str):
    """Layer 3: only rows with kpi_code assigned (mapping_status IN
    DIRECT/DERIVED/ANNEXURE/PARTIAL). Grouped by kpi_code so multi-year
    values for the same KPI sit together. CONFLICTING rows are visually
    prominent -- red row highlight + banner, not just a text label.
    """
    with db() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
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

    from collections import defaultdict, OrderedDict
    by_kpi: dict[str, list] = defaultdict(list)
    for row in rows:
        by_kpi[row["kpi_code"] or "(no code)"].append(row)

    run_e = escape(run_id)

    html = [PAGE_HEAD.format(title=f"Mapped — {run_id}")]
    html.append(_run_nav(run_id))
    html.append("<h1>Layer 3: Dictionary-Mapped View</h1>")
    html.append(
        f'<div class="summary-bar">Run <code>{run_e}</code> &mdash; '
        f'<strong>{len(rows)}</strong> mapped rows across '
        f'<strong>{len(by_kpi)}</strong> KPI codes'
        f'</div>'
    )

    if n_conflicting:
        html.append(
            f'<div class="conflicting-banner">'
            f'&#9888; {n_conflicting} CONFLICTING row(s) in this view &mdash; '
            f'digits &ne; words encoding. Highlighted in red below. '
            f'This is where checksum discrepancies live.'
            f'</div>'
        )

    for kpi_code in sorted(by_kpi.keys()):
        kpi_rows = by_kpi[kpi_code]
        has_conflicting = any(r["auth_status"] == "CONFLICTING" for r in kpi_rows)
        border = ' style="border:2px solid #c0392b"' if has_conflicting else ""
        html.append(
            f'<h2{border}><code>{escape(kpi_code)}</code> '
            f'<span style="font-weight:normal;font-size:0.85rem">'
            f'({len(kpi_rows)} row{"s" if len(kpi_rows) != 1 else ""}'
            f'{" &mdash; " + _mapping_badge(kpi_rows[0]["mapping_status"]) if kpi_rows else ""}'
            f')</span></h2>'
        )
        html.append(
            "<table><thead><tr>"
            "<th>institution</th><th>section</th><th>raw_value</th>"
            "<th>normalized</th><th>period</th>"
            "<th>auth_status</th><th>mapping</th>"
            "<th>source (doc + sha8)</th>"
            "</tr></thead><tbody>"
        )
        for row in kpi_rows:
            is_conflict = row["auth_status"] == "CONFLICTING"
            row_class = ' class="row-conflicting"' if is_conflict else ""
            period = ""
            if row["period_value"] or row["period_type"]:
                period = f"{escape(row['period_value'] or '')} ({escape(row['period_type'] or '')})"
            citation = _source_citation(row["url"] or "", row["sha256"])
            if row["page_no"] is not None:
                citation += f' p.{row["page_no"]}'
            norm = str(row["normalized_value"]) if row["normalized_value"] is not None else ""
            conflict_marker = " &#9888;" if is_conflict else ""
            html.append(
                f"<tr{row_class}>"
                f"<td><code>{escape(row['institution_code'])}</code></td>"
                f"<td>{escape(row['section'] or '')}</td>"
                f"<td><strong>{escape(row['raw_value'])}</strong>{conflict_marker}</td>"
                f"<td>{escape(norm)}</td>"
                f"<td style='white-space:nowrap'>{period}</td>"
                f"<td>{_auth_badge(row['auth_status'])}</td>"
                f"<td>{_mapping_badge(row['mapping_status'])}</td>"
                f"<td style='font-size:0.8rem'>{citation}</td>"
                f"</tr>"
            )
        html.append("</tbody></table>")

    if not rows:
        html.append('<div class="note">No mapped rows found for this run.</div>')

    html.append(PAGE_TAIL)
    return "".join(html)


@app.route("/run/<run_id>/orphans")
def run_orphans(run_id: str):
    """Layer 4: orphan view -- rows where mapping_status = 'ORPHAN'.
    ANOMALY rows (mapping_status = 'ANOMALY') are EXCLUDED from the
    orphan concept count and listed separately as a 'flagged for review'
    badge -- they are not genuine orphan concepts.
    Concept grouping: (section, row_label) where row_label = grid[row][0].text --
    the row's header/label text, shared across all cells in that row. This is the
    same key used in the reconciliation work and produces 60 distinct concepts
    (sub-blocks split) or 49 (sub-blocks merged) across the 8 fixtures.
    ANOMALY rows (mapping_status = 'ANOMALY') are EXCLUDED from this count.
    """
    with db() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            # Orphan concept groups -- group on (section, row_label), ANOMALY excluded.
            # row_label = grid[row][0].text, the first cell of each row in the source
            # table -- the row's header label, shared by all data cells in that row.
            # This matches the reconciliation's grouping logic exactly.
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

            # ANOMALY rows -- flagged for review, not folded into orphan count
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

            # Total distinct institutions
            cur.execute(
                "SELECT COUNT(DISTINCT institution_code) AS n FROM value WHERE run_id = %s AND mapping_status = 'ORPHAN'",
                (run_id,),
            )
            n_institutions = cur.fetchone()["n"]

    n_concepts = len(orphan_groups)
    n_anomalies = len(anomaly_rows)
    run_e = escape(run_id)

    html = [PAGE_HEAD.format(title=f"Orphans — {run_id}")]
    html.append(_run_nav(run_id))
    html.append("<h1>Layer 4: Orphan View</h1>")

    # Summary line at top (concepts, not raw row count -- same as reconciliation)
    html.append(
        f'<div class="summary-bar">'
        f'<strong>{n_concepts} distinct orphan concepts</strong> across '
        f'<strong>{n_institutions} institution(s)</strong> &mdash; '
        f'run <code>{run_e}</code>. '
        f'Concept = unique (section, row_label) pair, where row_label is the '
        f'first-cell header text shared across all cells in that table row. '
        f'Raw orphan row count is higher (same concept, multiple years/institutions).'
    )
    if n_anomalies:
        html.append(
            f' &nbsp; <span class="review-badge">&#9888; {n_anomalies} row(s) flagged for review</span> '
            f'<a href="#anomaly-section">(see below)</a> &mdash; excluded from concept count.'
        )
    html.append('</div>')

    # Orphan concept table
    html.append(
        "<table><thead><tr>"
        "<th>#</th><th>section</th><th>row_label</th>"
        "<th>domain</th><th>raw rows</th><th>institutions</th>"
        "</tr></thead><tbody>"
    )
    for i, grp in enumerate(orphan_groups, 1):
        inst_title = escape(", ".join(grp["inst_list"] or []))
        html.append(
            f"<tr>"
            f"<td>{i}</td>"
            f"<td>{escape(grp['section'] or '')}</td>"
            f"<td>{escape(grp['label'] or '')}</td>"
            f"<td>{escape(grp['domain'] or '')}</td>"
            f"<td>{grp['raw_rows']}</td>"
            f"<td title='{inst_title}'>{grp['institutions']}</td>"
            f"</tr>"
        )
    if not orphan_groups:
        html.append("<tr><td colspan='6'><em>No orphan rows for this run.</em></td></tr>")
    html.append("</tbody></table>")

    # Anomaly section -- separate, not part of orphan count
    html.append(f'<h2 id="anomaly-section">Rows Flagged for Review ({n_anomalies})</h2>')
    if n_anomalies:
        html.append(
            '<div class="note">These rows have <code>mapping_status = ANOMALY</code>. '
            'They are extraction anomalies (e.g. merged-cell column-count mismatches) '
            'and are <strong>excluded</strong> from the orphan concept count above -- '
            'they are not genuine unmapped concepts.</div>'
        )
        html.append(
            "<table><thead><tr>"
            "<th>institution</th><th>section</th><th>raw_value</th>"
            "<th>anomaly_reason</th><th>source (doc + sha8)</th><th>page</th>"
            "</tr></thead><tbody>"
        )
        for row in anomaly_rows:
            citation = _source_citation(row["url"] or "", row["sha256"])
            html.append(
                f"<tr>"
                f"<td><code>{escape(row['institution_code'])}</code></td>"
                f"<td>{escape(row['section'] or '')}</td>"
                f"<td>{escape(row['raw_value'])}</td>"
                f"<td><span class='badge anomaly'>{escape(row['anomaly_reason'] or 'anomaly')}</span></td>"
                f"<td style='font-size:0.8rem'>{citation}</td>"
                f"<td>{row['page_no'] if row['page_no'] is not None else ''}</td>"
                f"</tr>"
            )
        html.append("</tbody></table>")
    else:
        html.append('<p><em>No anomaly-flagged rows for this run.</em></p>')

    html.append(PAGE_TAIL)
    return "".join(html)


def run_manual_sandbox_pipeline(url: str, auto_cleanup: bool = True) -> tuple[str, dict]:
    """Execute the full extraction -> mapping -> load pipeline for a test document in sandbox mode.

    Reuses existing pipeline modules directly (never duplicates extraction/mapping/loading logic).
    Enforces manual_test_ prefix on the run_id.
    """
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

    # Ingest / manifest
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

    # Classify & convert
    m_path = manifest_path(sha256)
    manifest = json.loads(m_path.read_text(encoding="utf-8"))
    if not manifest.get("classify"):
        classify_artifact(sha256)
        manifest = json.loads(m_path.read_text(encoding="utf-8"))

    docling_path = DOCS_ROOT / sha256[:8] / "docling.json"
    if not docling_path.exists() or not manifest.get("convert"):
        convert_artifact(sha256)
        manifest = json.loads(m_path.read_text(encoding="utf-8"))

    # Generate fresh sandbox run_id with strictly enforced prefix
    clean_code = re.sub(r'[^A-Za-z0-9_-]', '', institution_code)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"manual_test_{clean_code}_{ts}_{uuid.uuid4().hex[:6]}"

    # Auto-cleanup prior sandbox test runs for this institution if requested
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

    # Extract via existing pipeline logic
    res = extract_artifact(manifest)

    # Write run files
    values_path, checksums_path = write_run(run_id, [res])

    # Load into Postgres value table with mapping and verification
    report = load_run_to_postgres(run_id, values_path, checksums_path)
    return run_id, report


@app.route("/test", methods=["GET", "POST"])
def manual_test():
    if request.method == "POST":
        url = request.form.get("url", "").strip()
        auto_cleanup = bool(request.form.get("auto_cleanup"))
        if not url:
            return (
                PAGE_HEAD.format(title="Error")
                + "<h1>Error</h1><p>URL cannot be empty.</p><p><a href='/test'>Back</a></p>"
                + PAGE_TAIL,
                400,
            )
        try:
            run_id, report = run_manual_sandbox_pipeline(url, auto_cleanup=auto_cleanup)
            return redirect(f"/test?run_id={run_id}&msg=success")
        except Exception as exc:
            html = [PAGE_HEAD.format(title="Manual Testing Sandbox - Error")]
            html.append("<h1>Manual Testing Sandbox &mdash; Error</h1>")
            html.append(f'<div class="conflicting-banner">Pipeline failed: {escape(str(exc))}</div>')
            html.append('<p><a href="/test">&larr; Back to Sandbox</a></p>')
            html.append(PAGE_TAIL)
            return "".join(html), 500

    # GET request
    run_id = request.args.get("run_id", "").strip()
    msg = request.args.get("msg", "").strip()

    html = [PAGE_HEAD.format(title="Safe Manual Link-Testing Sandbox")]
    html.append("<h1>Safe Manual Link-Testing Sandbox</h1>")
    html.append(
        '<p>Paste a document URL (live HTTPS link or fixture URL like <code>fixture://IR-E-I-1480.pdf</code>) '
        'to run it through the full extraction &rarr; mapping &rarr; loading pipeline into an isolated sandbox run. '
        'Sandbox runs are strictly isolated under <code>manual_test_*</code> run IDs and can be safely deleted '
        'without affecting immutable reference data.</p>'
    )

    if msg == "success" and run_id:
        html.append(f'<div class="summary-bar" style="background:#d4edda; border-color:#c3e6cb; color:#155724;">'
                    f'&#10004; Sandbox run <code>{escape(run_id)}</code> generated and loaded successfully.</div>')
    elif msg == "deleted":
        del_run = escape(request.args.get("deleted_run", "Sandbox run"))
        html.append(f'<div class="summary-bar" style="background:#fff3cd; border-color:#ffeeba; color:#856404;">'
                    f'&#10004; {del_run} and all its value rows were cleanly deleted.</div>')

    # Submission form
    html.append(
        '<form method="POST" action="/test" style="background:#f8f9fa; border:1px solid #dee2e6; padding:1.2rem; border-radius:6px; margin-bottom:1.5rem;">'
        '<div style="margin-bottom:0.8rem;">'
        '<label for="url-input" style="font-weight:600; display:block; margin-bottom:0.3rem;">Document URL to test:</label>'
        '<input type="text" id="url-input" name="url" placeholder="https://example.edu/nirf.pdf or fixture://IR-E-U-0456.pdf" style="width:70%; font-size:0.95rem; padding:0.5rem;" required>'
        '</div>'
        '<div style="margin-bottom:1rem;">'
        '<label><input type="checkbox" name="auto_cleanup" value="1" checked> '
        'Auto-cleanup prior sandbox runs for this institution before running (prevents test clutter)</label>'
        '</div>'
        '<button type="submit" style="background:#0d6efd; color:white; border:none; border-radius:4px; padding:0.55rem 1.4rem; font-size:0.95rem; font-weight:600; cursor:pointer;">Run Pipeline</button>'
        '</form>'
    )

    # If run_id is selected, show its full inspection summary
    if run_id:
        with db() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) as total_rows,
                           COUNT(DISTINCT institution_code) as n_inst,
                           COUNT(DISTINCT sha256) as n_sha
                    FROM value WHERE run_id = %s
                    """,
                    (run_id,),
                )
                run_summary = cur.fetchone()

                # Institution details
                cur.execute(
                    """
                    SELECT v.institution_code, v.sha256, a.url
                    FROM value v
                    LEFT JOIN artifact a ON v.sha256 = a.sha256
                    WHERE v.run_id = %s
                    GROUP BY v.institution_code, v.sha256, a.url
                    """,
                    (run_id,),
                )
                inst_details = cur.fetchall()

                # Status distribution
                cur.execute(
                    """
                    SELECT mapping_status, count(*) as cnt
                    FROM value WHERE run_id = %s
                    GROUP BY mapping_status ORDER BY cnt DESC
                    """,
                    (run_id,),
                )
                status_dist = {r["mapping_status"]: r["cnt"] for r in cur.fetchall()}

                # Domain distribution
                cur.execute(
                    """
                    SELECT domain, count(*) as cnt
                    FROM value WHERE run_id = %s
                    GROUP BY domain ORDER BY cnt DESC
                    """,
                    (run_id,),
                )
                domain_dist = {r["domain"]: r["cnt"] for r in cur.fetchall()}

                # Conflicting rows
                cur.execute(
                    """
                    SELECT v.institution_code, v.sha256, v.raw_value, v.auth_status, v.kpi_code,
                           v.mapping_status, v.section, v.row_label, a.url
                    FROM value v
                    LEFT JOIN artifact a ON v.sha256 = a.sha256
                    WHERE v.run_id = %s AND v.auth_status = 'CONFLICTING'
                    """,
                    (run_id,),
                )
                conflicting = cur.fetchall()

                # Anomaly rows
                cur.execute(
                    """
                    SELECT v.institution_code, v.sha256, v.raw_value, v.anomaly_reason, v.section, v.row_label
                    FROM value v WHERE v.run_id = %s AND v.mapping_status = 'ANOMALY'
                    """,
                    (run_id,),
                )
                anomalies = cur.fetchall()

        if run_summary and run_summary["total_rows"] > 0:
            tot = run_summary["total_rows"]
            n_mapped = tot - status_dist.get("ORPHAN", 0) - status_dist.get("ANOMALY", 0)
            n_orphans = status_dist.get("ORPHAN", 0)
            n_anom = status_dist.get("ANOMALY", 0)
            n_conf = len(conflicting)

            html.append(f'<div style="background:#fff; border:2px solid #0d6efd; border-radius:6px; padding:1.2rem; margin-bottom:2rem;">')
            html.append(f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.8rem;">')
            html.append(f'<h2 style="margin:0;">Sandbox Run Inspection: <code>{escape(run_id)}</code></h2>')

            # Delete button
            html.append(
                f'<form method="POST" action="/test/delete" onsubmit="return confirm(\'Delete sandbox run {escape(run_id)} and all its rows?\');">'
                f'<input type="hidden" name="run_id" value="{escape(run_id)}">'
                f'<button type="submit" style="background:#dc3545; color:white; border:none; border-radius:4px; padding:0.45rem 1rem; font-weight:600; cursor:pointer;">Delete This Test Run</button>'
                f'</form>'
            )
            html.append('</div>')

            # Quick nav to 4 presentation routes
            html.append(
                f'<div class="summary-bar">'
                f'<strong>Explore in 4-Layer Views:</strong> &nbsp;&nbsp;'
                f'<a href="/run/{escape(run_id)}/extracted" target="_blank">1. Extracted (Raw)</a> &nbsp;|&nbsp; '
                f'<a href="/run/{escape(run_id)}/domains" target="_blank">2. Domains</a> &nbsp;|&nbsp; '
                f'<a href="/run/{escape(run_id)}/mapped" target="_blank">3. Mapped KPIs</a> &nbsp;|&nbsp; '
                f'<a href="/run/{escape(run_id)}/orphans" target="_blank">4. Orphan Concepts</a>'
                f'</div>'
            )

            # Metadata info
            html.append('<div style="margin:0.8rem 0; font-size:0.9rem;">')
            for inst in inst_details:
                c_code = escape(inst["institution_code"] or "UNKNOWN")
                c_sha = escape(inst["sha256"][:8])
                c_url = escape(inst["url"] or "")
                html.append(f'<div><strong>Institution:</strong> <code>{c_code}</code> &nbsp;|&nbsp; '
                            f'<strong>Artifact:</strong> <code>{c_sha}</code> &nbsp;|&nbsp; '
                            f'<strong>URL:</strong> <code>{c_url}</code></div>')
            html.append('</div>')

            # Conflicting banner if present
            if n_conf:
                html.append(
                    f'<div class="conflicting-banner">'
                    f'&#9888; {n_conf} CONFLICTING row(s) detected! Dual-encoding mismatch between digits and words.'
                    f'</div>'
                )
                html.append('<table><thead><tr><th>Section</th><th>Row Label</th><th>Raw Value</th><th>Status</th><th>KPI</th></tr></thead><tbody>')
                for c in conflicting:
                    html.append(
                        f'<tr class="row-conflicting">'
                        f'<td>{escape(c["section"] or "")}</td>'
                        f'<td>{escape(c["row_label"] or "")}</td>'
                        f'<td><strong>{escape(c["raw_value"])}</strong></td>'
                        f'<td>{_auth_badge(c["auth_status"])}</td>'
                        f'<td>{escape(c["kpi_code"] or "")} ({escape(c["mapping_status"] or "")})</td>'
                        f'</tr>'
                    )
                html.append('</tbody></table>')

            # Metrics row
            html.append('<div style="display:flex; gap:1.5rem; margin:1rem 0;">')
            html.append(f'<div style="flex:1; border:1px solid #dee2e6; border-radius:4px; padding:0.8rem; background:#f8f9fa;">'
                        f'<div style="font-size:0.8rem; color:#666;">TOTAL ROWS</div>'
                        f'<div style="font-size:1.6rem; font-weight:700;">{tot}</div>'
                        f'</div>')
            html.append(f'<div style="flex:1; border:1px solid #dee2e6; border-radius:4px; padding:0.8rem; background:#f8f9fa;">'
                        f'<div style="font-size:0.8rem; color:#666;">MAPPED ROWS</div>'
                        f'<div style="font-size:1.6rem; font-weight:700; color:#155724;">{n_mapped}</div>'
                        f'</div>')
            html.append(f'<div style="flex:1; border:1px solid #dee2e6; border-radius:4px; padding:0.8rem; background:#f8f9fa;">'
                        f'<div style="font-size:0.8rem; color:#666;">ORPHAN ROWS</div>'
                        f'<div style="font-size:1.6rem; font-weight:700; color:#383d41;">{n_orphans}</div>'
                        f'</div>')
            if n_anom:
                html.append(f'<div style="flex:1; border:1px solid #dee2e6; border-radius:4px; padding:0.8rem; background:#fff3cd;">'
                            f'<div style="font-size:0.8rem; color:#856404;">ANOMALIES</div>'
                            f'<div style="font-size:1.6rem; font-weight:700; color:#856404;">{n_anom}</div>'
                            f'</div>')
            html.append('</div>')

            # Breakdown tables (Domain + Mapping Status side by side)
            html.append('<div style="display:flex; gap:1.5rem; margin-top:1rem;">')
            html.append('<div style="flex:1;"><h3>Domain Distribution</h3><table><thead><tr><th>Domain</th><th>Rows</th></tr></thead><tbody>')
            for dom, cnt in domain_dist.items():
                html.append(f'<tr><td><code>{escape(dom or "None")}</code></td><td>{cnt}</td></tr>')
            html.append('</tbody></table></div>')

            html.append('<div style="flex:1;"><h3>Mapping Status Distribution</h3><table><thead><tr><th>Status</th><th>Rows</th></tr></thead><tbody>')
            for st, cnt in status_dist.items():
                html.append(f'<tr><td>{_mapping_badge(st)}</td><td>{cnt}</td></tr>')
            html.append('</tbody></table></div>')
            html.append('</div>')

            html.append('</div>')
        else:
            html.append(f'<div class="note">Run <code>{escape(run_id)}</code> has 0 rows in database.</div>')

    # List of all active sandbox test runs
    with db() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT run_id,
                       institution_code,
                       COUNT(*) as row_count,
                       COUNT(DISTINCT sha256) as doc_count
                FROM value
                WHERE run_id LIKE %s
                GROUP BY run_id, institution_code
                ORDER BY run_id DESC
                """,
                ("manual_test_%",),
            )
            active_runs = cur.fetchall()

    html.append("<h2>Active Sandbox Test Runs</h2>")
    if active_runs:
        html.append(
            "<table><thead><tr>"
            "<th>Sandbox run_id</th><th>Institution</th><th>Rows</th>"
            "<th>Inspect</th><th>Actions</th>"
            "</tr></thead><tbody>"
        )
        for ar in active_runs:
            r_id = escape(ar["run_id"])
            inst = escape(ar["institution_code"])
            cnt = ar["row_count"]
            html.append(
                f"<tr>"
                f"<td><code>{r_id}</code></td>"
                f"<td><code>{inst}</code></td>"
                f"<td>{cnt}</td>"
                f"<td><a href='/test?run_id={r_id}'>Summary</a> &nbsp;|&nbsp; "
                f"<a href='/run/{r_id}/mapped' target='_blank'>Mapped</a> &nbsp;|&nbsp; "
                f"<a href='/run/{r_id}/orphans' target='_blank'>Orphans</a></td>"
                f"<td>"
                f"<form method='POST' action='/test/delete' style='display:inline;' onsubmit='return confirm(\"Delete sandbox run {r_id}?\");'>"
                f"<input type='hidden' name='run_id' value='{r_id}'>"
                f"<button type='submit' style='background:#dc3545; color:white; border:none; border-radius:3px; padding:0.25rem 0.6rem; font-size:0.8rem; cursor:pointer;'>Delete</button>"
                f"</form>"
                f"</td>"
                f"</tr>"
            )
        html.append("</tbody></table>")
    else:
        html.append("<p><em>No active sandbox test runs. The database contains only reference runs.</em></p>")

    html.append(PAGE_TAIL)
    return "".join(html)


@app.route("/test/delete", methods=["POST"])
def manual_test_delete():
    run_id = request.form.get("run_id", "").strip()
    if not run_id.startswith("manual_test_"):
        return "Forbidden: delete is restricted to manual_test_ runs only", 403
    try:
        deleted = delete_manual_test_run(run_id)
        return redirect(f"/test?msg=deleted&deleted_run={run_id}")
    except Exception as exc:
        return f"Error deleting test run: {escape(str(exc))}", 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)

