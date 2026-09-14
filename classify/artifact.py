"""Classify one already-acquired artifact (identified by its sha256, per
P2A's content-addressed store) and persist the result:

  docs/<sha8>/pages/NNN.json   per-page (chars, images, rotation) + label
  docs/<sha8>/pages/NNN.png    rendered page, PDF only (see NOTE below)
  docs/<sha8>/manifest.json    gets a "classify" block appended (regenerable,
                                per CLAUDE.md -- docs/ is rewritten, not
                                append-only the way raw/ is)

NOTE on pages/NNN.png for non-PDF artifacts: the settled stack (CLAUDE.md)
has no headless browser / rendering engine for HTML, so html_table artifacts
get a page record with no PNG rather than a faked one. This is recorded
explicitly per artifact (png_available: false) rather than silently omitted,
and flagged [OPEN] in gate/P2B-convert.md -- it is a real gap, not a shortcut
taken quietly.
"""
from __future__ import annotations

import glob
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from classify import sniff
from classify.html_profile import profile_html
from classify.labels import classify_artifact_label, classify_pdf_document
from classify.pdf_profile import profile_pdf, render_page_png

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"
RAW_ROOT = REPO_ROOT / "raw" / "sha256"

# Read enough of the head to cover every filetype signature (largest known
# offset among the formats we care about is well under this) plus a
# generous margin for the text-sniff fallback in classify/sniff.py.
SNIFF_HEAD_BYTES = 8192


def find_raw_path(sha256: str) -> Path | None:
    matches = glob.glob(str(RAW_ROOT / sha256[:2] / sha256[2:4] / f"{sha256}.*"))
    return Path(matches[0]) if matches else None


def manifest_path(sha256: str) -> Path:
    return DOCS_ROOT / sha256[:8] / "manifest.json"


def classify_artifact(sha256: str) -> dict:
    """Returns the classify record written into the manifest. Raises if the
    raw file referenced by a manifest is missing -- a manifest whose bytes
    vanished is a hard failure, not something to route around."""
    raw_path = find_raw_path(sha256)
    if raw_path is None:
        raise FileNotFoundError(f"no raw file found for sha256={sha256} under {RAW_ROOT}")

    head = raw_path.read_bytes()[:SNIFF_HEAD_BYTES]
    mime = sniff.sniff_mime(head)

    pages_dir = DOCS_ROOT / sha256[:8] / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    if mime == sniff.PDF:
        pdf_pages = profile_pdf(raw_path)
        label, per_page_labels = classify_pdf_document(pdf_pages)
        page_records = []
        for page, page_label in zip(pdf_pages, per_page_labels):
            record = {**asdict(page), "label": page_label}
            (pages_dir / f"{page.page_no:03d}.json").write_text(
                json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
            )
            png_path = pages_dir / f"{page.page_no:03d}.png"
            render_page_png(raw_path, page.page_no, png_path)
            page_records.append({**record, "png_available": True})
        page_rotations = {page.page_no: page.rotation for page in pdf_pages}
        n_pages = len(pdf_pages)
    else:
        html_profile = profile_html(raw_path.read_bytes()) if mime == sniff.HTML else None
        label = classify_artifact_label(mime, html_profile=html_profile)
        chars = html_profile.chars if html_profile else None
        images = html_profile.images if html_profile else None
        record = {
            "page_no": 1,
            "chars": chars,
            "images": images,
            "rotation": None,
            "label": label,
        }
        (pages_dir / "001.json").write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        page_records = [{**record, "png_available": False}]
        page_rotations = {1: None}
        n_pages = 1

    classify_record = {
        "mime": mime,
        "label": label,
        "n_pages": n_pages,
        "page_char_threshold_used": None,  # filled in only for pdf_* below
        "page_rotations": {str(k): v for k, v in page_rotations.items()},
        "classified_at": datetime.now(timezone.utc).isoformat(),
    }
    if mime == sniff.PDF:
        from classify.labels import PAGE_CHAR_THRESHOLD

        classify_record["page_char_threshold_used"] = PAGE_CHAR_THRESHOLD

    _write_classify_block(sha256, classify_record)
    return classify_record


def get_page_rotations(sha256: str) -> dict[int, int | None]:
    """Read per-page rotation records for an artifact. Checks manifest's
    classify or convert block first, and falls back to reading
    docs/<sha8>/pages/*.json on disk so previously classified artifacts
    resolve without requiring re-classification.
    """
    mpath = manifest_path(sha256)
    if mpath.exists():
        try:
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
            for block in ("convert", "classify"):
                rots = manifest.get(block, {}).get("page_rotations")
                if rots is not None:
                    return {int(k): v for k, v in rots.items()}
        except Exception:
            pass

    # Fallback to reading docs/<sha8>/pages/*.json
    pages_dir = DOCS_ROOT / sha256[:8] / "pages"
    rotations: dict[int, int | None] = {}
    for p in sorted(pages_dir.glob("*.json")):
        try:
            pdata = json.loads(p.read_text(encoding="utf-8"))
            p_no = pdata.get("page_no")
            if p_no is not None:
                rotations[int(p_no)] = pdata.get("rotation")
        except Exception:
            pass
    return rotations


def _write_classify_block(sha256: str, classify_record: dict) -> None:
    path = manifest_path(sha256)
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    doc["classify"] = classify_record
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, sort_keys=True)


def iter_manifest_shas() -> list[str]:
    shas = []
    for mp in glob.glob(str(DOCS_ROOT / "*" / "manifest.json")):
        with open(mp, encoding="utf-8") as f:
            shas.append(json.load(f)["sha256"])
    return shas
