"""docs/<sha8>/manifest.json bookkeeping.

docs/ is regenerable (CLAUDE.md), so unlike raw/ a manifest file may be
rewritten -- but never to lose a prior run's row. Each manifest.json holds
one document identity (keyed by its content sha256) and a `runs` list that
grows by one entry every time that URL is fetched again, whether the result
was a fresh 200, a 304, or a 200 with unchanged content.

Also home to the blocked/error report: PROMPTS.md P2A's stop condition is
"do not silently skip an institution" -- a request refused by robots.txt or
one that errors out gets a file here instead of vanishing.
"""
from __future__ import annotations

import glob
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DOCS_ROOT = Path("docs")
BLOCKED_ROOT = DOCS_ROOT / "_blocked"


def manifest_dir(sha256: str) -> Path:
    return DOCS_ROOT / sha256[:8]


def _iter_manifests():
    for path in glob.glob(str(DOCS_ROOT / "*" / "manifest.json")):
        try:
            with open(path, encoding="utf-8") as f:
                yield path, json.load(f)
        except (json.JSONDecodeError, OSError):
            continue


def find_by_url(url: str) -> dict[str, Any] | None:
    """The most recently-run manifest whose canonical URL or any prior run's
    URL matches `url`. Used to (a) attach conditional-fetch headers and (b)
    carry the sha256 forward when the next fetch comes back 304."""
    best = None
    best_fetched_at = ""
    for _, doc in _iter_manifests():
        urls = {doc.get("canonical_url")} | {r.get("url") for r in doc.get("runs", [])}
        if url not in urls:
            continue
        runs = doc.get("runs", [])
        latest = runs[-1] if runs else {}
        fetched_at = latest.get("fetched_at") or ""
        if best is None or fetched_at > best_fetched_at:
            best = {
                "sha256": doc["sha256"],
                "etag": latest.get("etag"),
                "last_modified": latest.get("last_modified"),
            }
            best_fetched_at = fetched_at
    return best


def append_run(
    *,
    sha256: str,
    source_id: str,
    institution_code: str,
    institution_name: str,
    country: str,
    canonical_url: str,
    period_type: str | None,
    period_value: str | None,
    run_entry: dict[str, Any],
) -> Path:
    path = manifest_dir(sha256) / "manifest.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    else:
        doc = {
            "sha256": sha256,
            "source_id": source_id,
            "institution_code": institution_code,
            "institution_name": institution_name,
            "country": country,
            "canonical_url": canonical_url,
            "period_type": period_type,
            "period_value": period_value,
            "runs": [],
        }
    doc["runs"].append(run_entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
    return path


def record_blocked(target, url: str, reason: str, run_id: str) -> Path:
    BLOCKED_ROOT.mkdir(parents=True, exist_ok=True)
    source_id = getattr(target, "source_id", None) or "unknown"
    period = (getattr(target, "period_value", None) or "na")
    path = BLOCKED_ROOT / f"{source_id}-{period}-{run_id}.json"
    path.write_text(
        json.dumps(
            {
                "source_id": source_id,
                "institution_code": getattr(target, "institution_code", None),
                "url": url,
                "reason": reason,
                "run_id": run_id,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path
