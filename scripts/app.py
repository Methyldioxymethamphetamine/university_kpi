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

import protego
import psycopg
from flask import Flask, request

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from acquire import manifestlog  # noqa: E402
from acquire.settings import USER_AGENT  # noqa: E402
from acquire.storage import raw_path, sha256_of, write_once  # noqa: E402
from classify.artifact import classify_artifact, manifest_path  # noqa: E402
from convert.artifact import CONVERTIBLE_LABELS, ConversionSkipped, convert_artifact  # noqa: E402
from discovery.candidates import generate_candidates  # noqa: E402
from extract.docling_source import load_docling_json  # noqa: E402
from extract.pipeline import extract_artifact  # noqa: E402
from fingerprint.matcher import MATCHED, known_profile_ids, match_document  # noqa: E402
from profiles.engine import load_profile  # noqa: E402

DSN = "host=localhost port=5433 dbname=kpi user=postgres password=kpi"
DOCS_ROOT = REPO_ROOT / "docs"

app = Flask(__name__)

PAGE_HEAD = """<!doctype html><html><head><meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 1100px; margin: 1.5rem auto; padding: 0 1rem; color: #222; }}
  table {{ border-collapse: collapse; width: 100%; margin: 0.75rem 0 1.5rem; }}
  th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.9rem; vertical-align: top; }}
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
  code {{ background: #f2f2f2; padding: 0.05rem 0.3rem; border-radius: 3px; font-size: 0.85em; }}
  .note {{ background: #fff8e6; border-left: 3px solid #e0a800; padding: 0.6rem 0.9rem; margin: 0.75rem 0; font-size: 0.9rem; }}
  nav {{ margin-bottom: 1rem; }}
  form input[type=text] {{ width: 480px; padding: 0.4rem; }}
  form button {{ padding: 0.4rem 1rem; }}
</style></head><body>
<nav><a href="/">Browse everything scraped</a> &nbsp;|&nbsp; <a href="/scrape">Paste a link, scrape it live</a></nav>
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
# ROUTE 1 -- browse everything actually scraped
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

    by_source: dict[str, list[dict]] = {}
    for a in artifacts:
        by_source.setdefault(a["source_id"], []).append(a)

    html = [PAGE_HEAD.format(title="Inventory")]
    html.append(f"<h1>Everything actually scraped</h1>")
    html.append(f'<p>Queried live from Postgres (<code>source</code> + <code>artifact</code> tables) '
                f'just now. {newly_synced} artifact(s) newly synced into the inventory this request '
                f'(from <code>docs/*/manifest.json</code> on disk, not previously in Postgres). '
                f'{len(sources)} source institution(s), {len(artifacts)} artifact(s) total.</p>')

    for src in sources:
        arts = by_source.get(src["source_id"], [])
        html.append(f'<h2>{escape(src["institution_code"])} <span style="color:#888;font-weight:normal">'
                    f'({escape(src["source_id"])}, {escape(src["country"])}, {escape(src["entry_type"])})</span></h2>')
        html.append("<table><thead><tr><th>sha256</th><th>URL</th><th>classify_label</th>"
                    "<th>match_status</th><th>pages</th><th>fetched_at</th><th></th></tr></thead><tbody>")
        for a in arts:
            badge = a["match_status"].lower()
            html.append(
                f'<tr><td><code>{a["sha256"][:8]}</code></td>'
                f'<td><a href="{escape(a["url"])}">{escape(a["url"][:70])}</a></td>'
                f'<td>{escape(a["classify_label"])}</td>'
                f'<td><span class="badge {badge}">{a["match_status"]}</span></td>'
                f'<td>{a["n_pages"] if a["n_pages"] is not None else "?"}</td>'
                f'<td>{a["fetched_at"]}</td>'
                f'<td><a href="/artifact/{a["sha256"][:8]}">view extracted rows</a></td></tr>'
            )
        html.append("</tbody></table>")

    if not sources:
        html.append("<p><em>No artifacts acquired yet.</em></p>")

    html.append(PAGE_TAIL)
    return "".join(html)


@app.route("/artifact/<sha8>")
def artifact_detail(sha8: str):
    matches = list(DOCS_ROOT.glob(f"{sha8}*/manifest.json"))
    if not matches:
        return f"<p>No artifact found for sha8={escape(sha8)}</p>", 404
    manifest = json.loads(matches[0].read_text())
    sha256 = manifest["sha256"]
    label = manifest.get("classify", {}).get("label", "(not classified)")

    html = [PAGE_HEAD.format(title=f"Artifact {sha8}")]
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

    result = extract_artifact(manifest)  # extract/pipeline.py, unchanged -- this call IS the reuse
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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
