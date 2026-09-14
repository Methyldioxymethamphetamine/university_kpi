"""P2E T3b — incidental-table stress test, NOT the original T3.

gate/P4-review.md finding H1: T3's PASS (swarthmore.edu) is real but
narrow -- it proves one specific homepage with ZERO <table> elements
yields zero values. It does not prove the pipeline is safe against a
homepage that DOES have an incidental (non-disclosure) <table> -- a nav
widget, a footer link grid, a notices ticker -- since discovery/
candidates.py scores every table cell uniformly with no way to
distinguish institutional self-disclosure from page furniture.

This script finds out, for real, rather than leaving H1 as a theoretical
gap. Target: https://www.jnu.ac.in/ (Jawaharlal Nehru University) -- a
real, uninvolved Indian university (not one of this project's three
iteration-1 institutions), chosen because a direct fetch confirmed it
actually has <table> markup on its homepage (2 tables), unlike every
liberal-arts-college and IIT homepage tried first (all zero <table>
elements) -- see this script's own robots.txt check and fetch below for
the real numbers, not an assumption.

Same pipeline as scripts/run_p2e_t3.py, unchanged: acquire (protego robots
check + content-addressed store + manifest) -> classify -> convert
(Docling) -> fingerprint -> discovery. H1's fix is deliberately NOT
implemented here -- this script only reports what the unmodified pipeline
actually does.
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
from acquire.storage import raw_path, sha256_of, write_once  # noqa: E402
from classify.artifact import classify_artifact  # noqa: E402
from convert.artifact import convert_artifact  # noqa: E402
from discovery.candidates import generate_candidates  # noqa: E402
from extract.docling_source import load_docling_json  # noqa: E402
from fingerprint.matcher import match_document  # noqa: E402

TARGET_URL = "https://www.jnu.ac.in/"
SOURCE_ID = "p2e_t3b_incidental_table_stress_test"
INSTITUTION_NAME = "Jawaharlal Nehru University (T3b stress-test fixture -- not an iteration-1 institution)"


def _robots_allows(url: str) -> bool:
    origin = "/".join(url.split("/")[:3])
    req = urllib.request.Request(f"{origin}/robots.txt", headers={"User-Agent": USER_AGENT})
    body = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    return protego.Protego.parse(body).can_fetch(url, USER_AGENT)


def fetch_and_store() -> str:
    print(f"=== T3b fetch: {TARGET_URL} ===")
    allowed = _robots_allows(TARGET_URL)
    print(f"robots.txt check (protego): can_fetch={allowed}")
    if not allowed:
        raise SystemExit("robots.txt disallows this fetch -- stopping, not routing around it")

    req = urllib.request.Request(TARGET_URL, headers={"User-Agent": USER_AGENT})
    resp = urllib.request.urlopen(req, timeout=20)
    body = resp.read()
    status = resp.status
    content_type = resp.headers.get("Content-Type")
    print(f"HTTP {status}, Content-Type={content_type}, {len(body)} bytes")
    print(f"raw <table markup count in fetched bytes: {body.count(b'<table')}")

    sha256 = sha256_of(body)
    path = raw_path(sha256, content_type)
    is_new = write_once(path, body)
    print(f"raw store: {path} ({'written' if is_new else 'already present, content-addressed match'})")

    run_entry = {
        "run_id": "p2e-t3b",
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
        institution_code="T3B_FIXTURE",
        institution_name=INSTITUTION_NAME,
        country="IN",
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
    except Exception as exc:  # noqa: BLE001 -- report and continue, diagnostic script
        print(f"convert step raised: {exc!r}")
        return

    doc = load_docling_json(sha256)
    fp = match_document(sha256, doc)
    print(f"\n=== fingerprint ===\noutcome={fp.outcome}")

    candidates = generate_candidates(sha256, doc)
    scored = sorted((c for c in candidates if c.suggestions), key=lambda c: -c.suggestions[0].score)
    print(f"\n=== T3b RESULT ===")
    print(f"candidate fields (total table cells discovery would propose): {len(candidates)}")
    print(f"candidates with >=1 nonzero KPI-dictionary suggestion: {len(scored)}")
    if scored:
        print("\nTop-scoring candidates (label -> value, top suggestion + score):")
        for c in scored[:15]:
            top = c.suggestions[0]
            print(f"  score={top.score:<6} kpi={top.kpi_code:<6} label={c.label!r} value={c.value!r}")
        highest = scored[0].suggestions[0]
        risky = highest.score >= 0.3  # same rough "would a careless reviewer bite" bar this session applied to real MIT candidates
        print(f"\nHighest single score across all candidates: {highest.score} (kpi={highest.kpi_code})")
        print(f"Would a careless reviewer plausibly confirm the top suggestion at face value? "
              f"{'MAYBE -- score is in the range real MIT confirmations scored at' if risky else 'UNLIKELY -- score is well below the range this session treated as worth a close look'}")
    else:
        print("Zero candidates scored against the KPI dictionary (all table cells present, but none "
              "token-overlapped any of the 229 real KPI codes).")

    print(f"\nT3b is a stress test, not an acceptance gate -- reporting the actual mechanism behavior, "
          f"not a PASS/FAIL verdict. See gate/P2E-profiles.md's T3b section for the full analysis.")


if __name__ == "__main__":
    main()
