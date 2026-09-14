"""Generic profile interpreter — reads a profiles/*.yaml block and a
docs/<sha8>/docling.json and produces value/checksum rows driven entirely by
the YAML's declared rules, never by code specific to one profile.

This is the "config, not code" proof PROMPTS.md P2E's first task demands:
extract/docling_source.py + extract/values.py + extract/checksums.py (P2C,
hand-written) encode exactly one set of geometric rules today. This module
reads those same rules out of profiles/nirf_submission_v2020_2026.yaml and
applies them generically -- if a second profile needed different geometry
(e.g. a per-section anchor instead of ANY_TABLE), it would be a new YAML
file, not a new code path here.

scripts/run_p2e_proof.py runs this engine against the two IIT Bombay
artifacts and diffs its output against P2C's own values.jsonl row by row.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILES_ROOT = REPO_ROOT / "profiles"

CONFIRMED, CONFLICTING, UNVERIFIED = "CONFIRMED", "CONFLICTING", "UNVERIFIED"
_DIGITS_WORDS_RE = re.compile(r"(\d[\d,]{2,})\s*\(([^()]{4,220}?)\)")
_DASH_RE = re.compile(r"^-+$")
_PURE_NUMBER_RE = re.compile(r"^\s*\d[\d,]*(?:\.\d+)?\s*$")
_LEADING_NUMBER_RE = re.compile(r"^\s*(\d[\d,]*(?:\.\d+)?)")


@dataclass(frozen=True)
class ProfileValueRow:
    sha256: str
    item_id: str
    page_no: int | None
    bbox: dict | None
    table_ref: str
    row_index: int
    col_index: int
    row_label: str | None
    column_label: str | None
    period_type: str | None
    period_value: str | None
    raw_value: str
    dash_state: str
    normalized_value: float | None
    has_word_form: bool


@dataclass(frozen=True)
class ProfileChecksumRow:
    sha256: str
    item_id: str
    page_no: int | None
    bbox: dict | None
    raw_value: str
    raw_digits: str
    raw_words: str
    digits_value: int
    words_value: int | None
    abstain_reason: str | None
    state: str


@dataclass
class ProfileRunResult:
    profile_id: str
    matched_fingerprint: bool
    value_rows: list[ProfileValueRow] = field(default_factory=list)
    checksum_rows: list[ProfileChecksumRow] = field(default_factory=list)
    incomplete: bool = False


def load_profile(profile_id: str) -> dict:
    path = PROFILES_ROOT / f"{profile_id}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def fingerprint_matches(profile: dict, docling_doc: dict) -> bool:
    """text_anchor present anywhere in texts[] (substring, or regex per
    text_anchor_match -- 2026-09-14 (v4), see
    profiles/nirf_submission_v2020_2026.yaml's own fingerprint comment for
    why the NIRF profile needs regex: a fixed substring fitted on one
    institution's copy of the form does not match a second institution's
    differently-worded copy of the identical form, P-14 applied one level
    up from column labels), AND the page that anchor is on carries the
    declared rotation. Geometry (rotation) comes from docling.json pages
    metadata (which carries the per-page rotation computed upstream via
    classify/pdf_profile.py's pypdfium2 walk and persisted during conversion)
    -- never from re-parsing raw PDF bytes (that would cross back into P-3
    territory)."""
    fp = profile["fingerprint"]
    anchor = fp["text_anchor"]
    match_mode = fp.get("text_anchor_match", "substring")
    texts = docling_doc.get("texts", [])
    matching_texts = []
    if match_mode == "regex":
        pattern = re.compile(anchor)
        matching_texts = [t for t in texts if pattern.search(t.get("text") or "")]
    elif match_mode == "substring":
        matching_texts = [t for t in texts if anchor in (t.get("text") or "")]
    else:
        raise ValueError(f"unknown fingerprint.text_anchor_match {match_mode!r}")
    if not matching_texts:
        return False

    declared_rotation = fp.get("page_rotation")
    if declared_rotation is None:
        # Profile does not declare a rotation requirement (e.g. HTML sources
        # like US CDS where page rotation is inapplicable).
        return True

    pages = docling_doc.get("pages", {})
    # Enforce declared page_rotation against the page(s) where the anchor was found.
    # Matching text prov gives the 1-indexed page_no.
    anchor_on_matching_page = False
    for t in matching_texts:
        prov = t.get("prov") or []
        for p in prov:
            p_no = p.get("page_no")
            if p_no is not None:
                page_entry = pages.get(str(p_no)) or pages.get(p_no) or {}
                page_rot = page_entry.get("page_rotation")
                if page_rot is None:
                    page_rot = page_entry.get("rotation")
                if page_rot == declared_rotation:
                    anchor_on_matching_page = True
                    break
        if anchor_on_matching_page:
            break

    # If anchor text items carried no provenance (e.g. synthetic or test dicts),
    # fall back to checking if pages carry the declared rotation.
    if not anchor_on_matching_page and not any(t.get("prov") for t in matching_texts):
        for p_key, page_entry in pages.items():
            page_rot = page_entry.get("page_rotation")
            if page_rot is None:
                page_rot = page_entry.get("rotation")
            if page_rot == declared_rotation:
                anchor_on_matching_page = True
                break

    return anchor_on_matching_page


def _classify_dash_state(raw: str) -> tuple[str, float | None]:
    stripped = raw.strip()
    if stripped == "":
        return "EMPTY", None
    if _DASH_RE.match(stripped):
        return "DASH", None
    if _PURE_NUMBER_RE.match(stripped):
        n = float(stripped.replace(",", ""))
        return ("ZERO", 0.0) if n == 0 else ("NUMBER", n)
    m = _LEADING_NUMBER_RE.match(stripped)
    if m:
        return "TEXT", float(m.group(1).replace(",", ""))
    return "TEXT", None


def _classify_period(label: str | None, rules: list[dict]) -> tuple[str | None, str | None]:
    if label is None:
        return None, None
    stripped = label.strip()
    for rule in rules:
        if re.match(rule["regex"], stripped):
            return rule["period_type"], stripped
    return None, None


def _apply_block(profile: dict, sha256: str, table: dict) -> tuple[list[ProfileValueRow], list[ProfileChecksumRow]]:
    block = profile["blocks"][0]  # ANY_TABLE: the one declared block applies to every table
    geometry = block["geometry"]
    period_rules = block["columns"]["period"]["rules"]

    table_ref = table.get("self_ref", "?")
    prov = table.get("prov") or []
    page_no = prov[0].get("page_no") if prov else None
    grid = table.get("data", {}).get("grid", [])
    if not grid:
        return [], []

    if geometry["header_row_rule"] == "single_row_where_every_cell_is_column_header":
        header_rows = [ri for ri, row in enumerate(grid) if row and all(c.get("column_header") for c in row)]
        header_row_idx = header_rows[0] if len(header_rows) == 1 else None
    else:
        raise ValueError(f"unknown header_row_rule {geometry['header_row_rule']!r}")

    label_col = geometry["label_column_index"]

    value_rows: list[ProfileValueRow] = []
    checksum_rows: list[ProfileChecksumRow] = []

    for ri, row in enumerate(grid):
        row_label = row[0].get("text") if row else None
        for ci, cell in enumerate(row):
            text = cell.get("text", "")
            column_label = None
            if header_row_idx is not None and ri != header_row_idx and ci < len(grid[header_row_idx]):
                column_label = grid[header_row_idx][ci].get("text")
            period_type, period_value = _classify_period(column_label, period_rules)
            bbox = cell.get("bbox")
            item_id = f"{sha256}:{table_ref}:r{ri}c{ci}"

            # --- checksum rule: every cell, regardless of role ---
            m = _DIGITS_WORDS_RE.search(text)
            if m is not None:
                raw_digits, raw_words = m.group(1), m.group(2).strip()
                digits_value = int(raw_digits.replace(",", ""))
                from extract.word_number import parse_words_to_number
                parsed = parse_words_to_number(raw_words)
                if parsed.value is None:
                    state = UNVERIFIED
                elif digits_value == parsed.value:
                    state = CONFIRMED
                else:
                    state = CONFLICTING
                checksum_rows.append(
                    ProfileChecksumRow(
                        sha256=sha256, item_id=item_id, page_no=page_no, bbox=bbox,
                        raw_value=text, raw_digits=raw_digits, raw_words=raw_words,
                        digits_value=digits_value, words_value=parsed.value,
                        abstain_reason=parsed.abstain_reason, state=state,
                    )
                )

            # --- role: is this cell a value? ---
            is_header_flagged = bool(cell.get("column_header")) or bool(cell.get("row_header"))
            if is_header_flagged or ci == label_col:
                continue  # label, not a value -- same rule as extract/values.py

            dash_state, normalized_value = _classify_dash_state(text)
            has_word_form = bool(_DIGITS_WORDS_RE.search(text))
            value_rows.append(
                ProfileValueRow(
                    sha256=sha256, item_id=item_id, page_no=page_no, bbox=bbox,
                    table_ref=table_ref, row_index=ri, col_index=ci,
                    row_label=row_label, column_label=column_label,
                    period_type=period_type, period_value=period_value,
                    raw_value=text, dash_state=dash_state,
                    normalized_value=normalized_value, has_word_form=has_word_form,
                )
            )
    return value_rows, checksum_rows


def _mechanically_applicable(profile: dict) -> bool:
    """This engine's _apply_block() only knows one block shape: a single
    ANY_TABLE block with geometry.header_row_rule + columns.period.rules
    (profiles/nirf_submission_v2020_2026.yaml's shape). A profile emitted
    from a completed T2 review (e.g. profiles/us_cds_v2025.yaml) records a
    small list of source_label -> kpi_code fragments instead -- a real,
    different shape, deliberately not force-fitted into this engine (that
    would mean guessing a geometry the review process never established).
    Checked structurally, not by profile_id, so this stays true for any
    future profile of either shape."""
    blocks = profile.get("blocks") or []
    if not blocks:
        return False
    first = blocks[0]
    return isinstance(first.get("geometry"), dict) and "period" in (first.get("columns") or {})


def run_profile(profile_id: str, sha256: str, docling_doc: dict) -> ProfileRunResult:
    profile = load_profile(profile_id)
    matched = fingerprint_matches(profile, docling_doc)
    result = ProfileRunResult(profile_id=profile_id, matched_fingerprint=matched)
    if not matched:
        return result
    if not _mechanically_applicable(profile):
        # Fingerprint matched (this document IS e.g. a CDS), but this
        # profile's blocks aren't in a shape this generic engine can walk
        # automatically -- report the match honestly without fabricating
        # value/checksum rows from a geometry nobody verified.
        result.incomplete = True
        return result
    for table in docling_doc.get("tables", []):
        vrows, crows = _apply_block(profile, sha256, table)
        result.value_rows.extend(vrows)
        result.checksum_rows.extend(crows)
    return result
