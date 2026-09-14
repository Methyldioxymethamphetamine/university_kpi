"""Orchestrate value + checksum extraction over every converted artifact and
write values/run={ts}/values.jsonl + checksums.jsonl.

Scope: reads docs/<sha8>/docling.json (P2B's output) and, for pdf_* labels,
cross-checks the digits(words) pairs found there against an independent
pypdfium2 geometric extraction (P-11). Touches nothing under raw/ or
Postgres, assigns no kpi_code (forbidden this phase).
"""
from __future__ import annotations

import glob
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from classify.artifact import find_raw_path
from classify.labels import HTML_TABLE, PDF_DIGITAL, PDF_MIXED, PDF_SCAN
from extract import pdf_geometry
from extract.checksums import ChecksumRow, build_checksum_rows
from extract.docling_source import iter_table_cells, load_docling_json
from extract.values import ValueRow, build_value_rows

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"
VALUES_ROOT = REPO_ROOT / "values"

PDF_LABELS = {PDF_DIGITAL, PDF_MIXED, PDF_SCAN}


@dataclass
class CrossCheckResult:
    sha256: str
    docling_pair_count: int
    geometric_pair_count: int
    docling_only: list[tuple[str, str]]
    geometric_only: list[tuple[str, str]]

    @property
    def agrees(self) -> bool:
        return not self.docling_only and not self.geometric_only


@dataclass
class ArtifactResult:
    sha256: str
    label: str
    institution_code: str | None
    source_id: str | None
    value_rows: list[ValueRow]
    checksum_rows: list[ChecksumRow]
    cross_check: CrossCheckResult | None
    error: str | None = None


def _iter_convertible_manifests() -> list[dict]:
    manifests = []
    for mp in sorted(glob.glob(str(DOCS_ROOT / "*" / "manifest.json"))):
        manifest = json.loads(Path(mp).read_text(encoding="utf-8"))
        if manifest.get("convert"):
            manifests.append(manifest)
    return manifests


def _cross_check_pdf(sha256: str, checksum_rows: list[ChecksumRow]) -> CrossCheckResult:
    raw_path = find_raw_path(sha256)
    docling_pairs = {(r.raw_digits, r.raw_words) for r in checksum_rows}
    if raw_path is None:
        return CrossCheckResult(sha256, len(docling_pairs), 0, sorted(docling_pairs), [])
    geometric_pairs = {(p.digits, p.words) for p in pdf_geometry.extract_pairs(raw_path)}
    return CrossCheckResult(
        sha256=sha256,
        docling_pair_count=len(docling_pairs),
        geometric_pair_count=len(geometric_pairs),
        docling_only=sorted(docling_pairs - geometric_pairs),
        geometric_only=sorted(geometric_pairs - docling_pairs),
    )


def extract_artifact(manifest: dict) -> ArtifactResult:
    sha256 = manifest["sha256"]
    label = manifest["classify"]["label"]
    institution_code = manifest.get("institution_code")
    source_id = manifest.get("source_id")

    doc = load_docling_json(sha256)
    if doc is None:
        return ArtifactResult(sha256, label, institution_code, source_id, [], [], None, error="docling.json missing")

    cells = iter_table_cells(sha256, doc)
    value_rows = build_value_rows(cells)
    checksum_rows = build_checksum_rows(cells)

    cross_check = None
    if label in PDF_LABELS and checksum_rows:
        cross_check = _cross_check_pdf(sha256, checksum_rows)

    return ArtifactResult(sha256, label, institution_code, source_id, value_rows, checksum_rows, cross_check)


def run_extraction() -> tuple[str, list[ArtifactResult]]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results = [extract_artifact(m) for m in _iter_convertible_manifests()]
    return run_id, results


def write_run(run_id: str, results: list[ArtifactResult]) -> tuple[Path, Path]:
    run_dir = VALUES_ROOT / f"run={run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    values_path = run_dir / "values.jsonl"
    checksums_path = run_dir / "checksums.jsonl"

    now = datetime.now(timezone.utc).isoformat()
    with open(values_path, "w", encoding="utf-8") as vf:
        for res in results:
            for row in res.value_rows:
                record = asdict(row)
                record.update(run_id=run_id, institution_code=res.institution_code, source_id=res.source_id, extracted_at=now)
                vf.write(json.dumps(record, sort_keys=True) + "\n")

    with open(checksums_path, "w", encoding="utf-8") as cf:
        for res in results:
            for row in res.checksum_rows:
                record = asdict(row)
                record.update(run_id=run_id, institution_code=res.institution_code, source_id=res.source_id, extracted_at=now)
                record["hand_verified_pypdfium2"] = res.cross_check.agrees if res.cross_check else None
                cf.write(json.dumps(record, sort_keys=True) + "\n")

    return values_path, checksums_path
