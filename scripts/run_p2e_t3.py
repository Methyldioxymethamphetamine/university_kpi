"""PROMPTS.md P2E, T3: A random private college HOMEPAGE.
EXPECT: 0 values, stated explicitly. "No structured self-disclosure found.
0 candidate fields." If this returns even one value, STOP EVERYTHING --
P-15 violated, the rotation failure wearing a new costume.

This is the CRITICAL acceptance test (PROMPTS.md P2E STOP CONDITION), so it
is run against a REAL fetch of a REAL, uninvolved institution's homepage --
not simulated. Target: https://www.swarthmore.edu/ -- a private liberal
arts college with no connection to this project's three iteration-1
institutions (Sandip, IIT Bombay, MIT). Chosen for a plain, standard-Drupal
robots.txt that a general crawler can actually check (verified below, not
assumed) -- several other candidates tried first (amherst.edu, williams.edu)
returned bot-challenge pages (AWS WAF / Cloudflare) to a plain HTTP client,
which is a different failure mode entirely and would have made this test
about challenge pages, not about self-disclosure tables.

Fetch path deliberately reuses acquire/'s own storage + manifestlog modules
(content-addressed write, manifest with real provenance) rather than ad hoc
file writing, and checks robots.txt with protego -- the same library
Scrapy's own RobotsTxtMiddleware uses -- before making the real request,
exactly as gate/P2A-acquire.md Sec3 already established for Sandip. This is
a one-off single-URL acquisition (not a registry entry -- this fixture is
not one of iteration 1's three institutions), so it is a small standalone
script rather than a Scrapy crawl, but every provenance field a registry-
driven fetch would produce is still recorded.
"""
from __future__ import annotations

import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import protego

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from acquire import manifestlog  # noqa: E402
from acquire.settings import USER_AGENT  # noqa: E402
from acquire.storage import ext_for, raw_path, sha256_of, write_once  # noqa: E402
from classify.artifact import classify_artifact  # noqa: E402
from convert.artifact import convert_artifact  # noqa: E402
from discovery.candidates import generate_candidates  # noqa: E402
from extract.docling_source import load_docling_json  # noqa: E402
from fingerprint.matcher import match_document, NO_MATCH  # noqa: E402

TARGET_URL = "https://www.swarthmore.edu/"
SOURCE_ID = "p2e_t3_random_private_college_homepage"
INSTITUTION_NAME = "Swarthmore College (T3 acceptance-test fixture -- not an iteration-1 institution)"


def _robots_allows(url: str) -> bool:
    origin = "/".join(url.split("/")[:3])
    req = urllib.request.Request(f"{origin}/robots.txt", headers={"User-Agent": USER_AGENT})
    body = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    return protego.Protego.parse(body).can_fetch(url, USER_AGENT)


def fetch_and_store() -> str:
    print(f"=== T3 fetch: {TARGET_URL} ===")
    allowed = _robots_allows(TARGET_URL)
    print(f"robots.txt check (protego, same library Scrapy's RobotsTxtMiddleware uses): can_fetch={allowed}")
    if not allowed:
        raise SystemExit("robots.txt disallows this fetch -- per ROBOTSTXT_OBEY=True, stopping, not routing around it")

    req = urllib.request.Request(TARGET_URL, headers={"User-Agent": USER_AGENT})
    resp = urllib.request.urlopen(req, timeout=20)
    body = resp.read()
    status = resp.status
    content_type = resp.headers.get("Content-Type")
    print(f"HTTP {status}, Content-Type={content_type}, {len(body)} bytes")

    sha256 = sha256_of(body)
    path = raw_path(sha256, content_type)
    is_new = write_once(path, body)
    print(f"raw store: {path} ({'written' if is_new else 'already present, content-addressed match'})")

    run_entry = {
        "run_id": "p2e-t3",
        "url": TARGET_URL,
        "http_status": status,
        "content_type": content_type,
        "content_length": len(body),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "etag": resp.headers.get("ETag"),
        "last_modified": resp.headers.get("Last-Modified"),
    }
    manifestlog.append_run(
        sha256=sha256,
        source_id=SOURCE_ID,
        institution_code="T3_FIXTURE",
        institution_name=INSTITUTION_NAME,
        country="US",
        canonical_url=TARGET_URL,
        period_type=None,
        period_value=None,
        run_entry=run_entry,
    )
    print(f"manifest written: docs/{sha256[:8]}/manifest.json")
    return sha256


def main() -> None:
    sha256 = fetch_and_store()

    classify_record = classify_artifact(sha256)
    print(f"\n=== classify ===\nlabel={classify_record['label']}")

    try:
        convert_record = convert_artifact(sha256)
        print(f"=== convert ===\nn_tables={convert_record['n_tables']} n_texts={convert_record['n_texts']}")
    except Exception as exc:  # noqa: BLE001 -- report and continue; this is a diagnostic script, not the pipeline
        print(f"convert step raised: {exc!r} -- if this label isn't in convert's CONVERTIBLE_LABELS, "
              f"there is no docling.json and therefore trivially 0 table-derived values, which still "
              f"satisfies T3's EXPECT (0 values) but for a different, equally-honest reason.")
        return

    doc = load_docling_json(sha256)
    fp = match_document(sha256, doc)
    print(f"\n=== fingerprint ===\noutcome={fp.outcome} (expected NO_MATCH -- a homepage carries no NIRF or CDS anchor)")

    candidates = generate_candidates(sha256, doc)
    scored = [c for c in candidates if c.suggestions]
    print(f"\n=== T3 RESULT ===")
    print(f"candidate fields: {len(candidates)}")
    print(f"candidates with a nonzero KPI-dictionary suggestion: {len(scored)}")
    if candidates:
        print("Some structured tabular content exists on this homepage -- listing it so a human can judge "
              "whether ANY of it is genuine institutional self-disclosure (P-15) or incidental page furniture "
              "(nav menus, cookie banners, etc. that happen to be marked up as <table>):")
        for c in candidates[:30]:
            print(f"  {c.item_id}: label={c.label!r} value={c.value!r}")
    else:
        print('"No structured self-disclosure found. 0 candidate fields."')

    if len(candidates) == 0:
        print("\nT3: PASS -- 0 values, 0 candidate fields, stated explicitly.")
    else:
        print("\nT3: STOP EVERYTHING -- candidate fields were found on a homepage. "
              "This must be inspected by hand (see the list above) before P2E is trusted "
              "further, per PROMPTS.md P2E's own STOP CONDITION.")


if __name__ == "__main__":
    main()
