"""Document structure section detection for NIRF submission documents.

Runs on docling.json's document structure (text elements outside of tables,
which Docling preserves as section headers) BEFORE table extraction, tagging
each table with the section and optional sub-block it falls under.

Known stable headers:
- Sanctioned (Approved) Intake
- Total Actual Student Strength
- Placement & Higher Studies (sub-blocks dynamically discovered from '...Program(s)]:')
- Ph.D Student Details
- Financial Resources: Capital expenditure
- Financial Resources: Operational expenditure
- Sponsored Research Details
- Consultancy Project Details
- PCS Facilities: Facilities of Physically Challenged Students
- Faculty Details
- Plus optional / own-site copy sections: EDP/MDP, Multiple Entry/Exit, Sustainability,
  IPR/Patents, Accreditation, PG Medical.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Main canonical section definitions: (canonical_name, regex)
SECTION_PATTERNS = [
    ("Sanctioned (Approved) Intake", re.compile(r"^Sanctioned\s+\(Approved\)\s+Intake", re.I)),
    ("Total Actual Student Strength", re.compile(r"^Total\s+Actual\s+Student\s+Strength", re.I)),
    ("Placement & Higher Studies", re.compile(r"^Placement\s+&\s+Higher\s+Studies", re.I)),
    ("Ph.D Student Details", re.compile(r"^Ph\.?D\s+Student\s+Details", re.I)),
    ("Financial Resources: Capital expenditure", re.compile(r"^Financial\s+Resources:.*Capital\s+expenditure", re.I)),
    ("Financial Resources: Operational expenditure", re.compile(r"^Financial\s+Resources:.*Operational\s+expenditure", re.I)),
    ("Sponsored Research Details", re.compile(r"^Sponsored\s+Research\s+Details", re.I)),
    ("Consultancy Project Details", re.compile(r"^Consultancy\s+Project\s+Details", re.I)),
    ("PCS Facilities: Facilities of Physically Challenged Students", re.compile(r"^PCS\s+Facilities", re.I)),
    ("Faculty Details", re.compile(r"^Faculty\s+Details", re.I)),
    # Additional sections (e.g. portal copy variants or own-site copies)
    ("Executive Development Program/Management Development Programs", re.compile(r"^(Executive\s+Development\s+Program|EDP/MDP)", re.I)),
    ("Multiple Entry/Exit and Indian Knowledge System", re.compile(r"^Multiple\s+Entry/Exit", re.I)),
    ("Sustainability Details / Sustainable Living Practices", re.compile(r"^(Sustainability|Sustainable\s+Living)", re.I)),
    ("IPR/Patents", re.compile(r"^(IPR|Patent\s+Details|Patents)", re.I)),
    ("Accreditation", re.compile(r"^(NAAC|NBA|Accreditation)", re.I)),
    ("PG Medical", re.compile(r"^PG\s+Medical", re.I)),
]

# Running headers/footers to ignore so they do not reset section state
IGNORE_PATTERNS = [
    re.compile(r"^Data\s+Submitted\s+by\s+Institution", re.I),
    re.compile(r"^National\s+Institutional\s+Ranking\s+Framework", re.I),
    re.compile(r"^Ministry\s+of\s+Education", re.I),
    re.compile(r"^Government\s+of\s+India", re.I),
    re.compile(r"^Institute\s+Name:", re.I),
    re.compile(r"^India\s+Rankings", re.I),
]

SUB_BLOCK_RE = re.compile(r"^(.*?)\s*Program\(s\)\]:", re.I)


@dataclass(frozen=True)
class SectionTag:
    section: str
    sub_block: str | None = None
    section_label: str = ""

    def __post_init__(self) -> None:
        if not self.section_label:
            if self.sub_block:
                label = f"{self.section}: {self.sub_block}"
            else:
                label = self.section
            object.__setattr__(self, "section_label", label)


def extract_sub_block(text: str) -> str | None:
    """Dynamically extract program-level label preceding 'Program(s)]:'.
    Handles UG [4 Years], PG [2 Years], PG-Integrated [5 Years], etc.
    without a closed hardcoded list.
    """
    m = SUB_BLOCK_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    if "[" in raw and not raw.endswith("]"):
        raw = raw + "]"
    return raw


def match_section_header(text: str) -> str | None:
    """Return canonical section name if text matches a section header pattern."""
    for sec_name, pattern in SECTION_PATTERNS:
        if pattern.search(text):
            return sec_name
    return None


def _flatten_children(docling_doc: dict[str, Any]) -> list[dict[str, Any]]:
    groups = {f"#/groups/{i}": g for i, g in enumerate(docling_doc.get("groups", []))}
    texts = {f"#/texts/{i}": t for i, t in enumerate(docling_doc.get("texts", []))}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _walk(children: list[dict[str, Any]]) -> None:
        for c in children:
            ref = c.get("$ref", "")
            if not ref or ref in seen:
                continue
            seen.add(ref)
            result.append(c)
            if ref.startswith("#/groups/"):
                g = groups.get(ref)
                if g and "children" in g:
                    _walk(g["children"])
            elif ref.startswith("#/texts/"):
                t = texts.get(ref)
                if t and "children" in t:
                    _walk(t["children"])

    body_children = docling_doc.get("body", {}).get("children", [])
    _walk(body_children)
    return result


def detect_table_sections(docling_doc: dict[str, Any]) -> dict[str, SectionTag]:
    """Inspect docling_doc document structure and tag each table with its section.

    Returns a dict mapping table_ref (e.g. '#/tables/0') to SectionTag.
    Unmatched tables are recorded with section='UNMATCHED' and logged explicitly.
    """
    texts = {f"#/texts/{i}": t for i, t in enumerate(docling_doc.get("texts", []))}
    tables = {f"#/tables/{i}": t for i, t in enumerate(docling_doc.get("tables", []))}

    # Determine traversal order: walk flattened tree children if available, otherwise document order
    traversal_items = _flatten_children(docling_doc)
    table_sections: dict[str, SectionTag] = {}

    current_section: str | None = None
    current_sub_block: str | None = None

    if traversal_items:
        for item in traversal_items:
            ref = item.get("$ref", "")
            if ref in texts:
                t = texts[ref]
                text_content = (t.get("text") or "").strip()
                if not text_content or any(p.search(text_content) for p in IGNORE_PATTERNS):
                    continue

                # Check if this is a sub-block under Placement & Higher Studies
                if current_section == "Placement & Higher Studies":
                    sub = extract_sub_block(text_content)
                    if sub:
                        current_sub_block = sub
                        continue

                # Check if this is a main section header
                sec_match = match_section_header(text_content)
                if sec_match:
                    current_section = sec_match
                    if current_section != "Placement & Higher Studies":
                        current_sub_block = None
                    else:
                        # Also check if the header itself carried sub-block info
                        sub = extract_sub_block(text_content)
                        if sub:
                            current_sub_block = sub

            elif ref in tables:
                if current_section is None:
                    prov = (tables[ref].get("prov") or [{}])[0]
                    p_no = prov.get("page_no", "?")
                    logger.warning(f"Table {ref} on page {p_no} does not fall under any section header")
                    table_sections[ref] = SectionTag(section="UNMATCHED", sub_block=None)
                else:
                    table_sections[ref] = SectionTag(
                        section=current_section,
                        sub_block=current_sub_block,
                    )
    else:
        # Fallback: order items by page_no and bbox coordinates
        ordered_items = []
        for ref, t in texts.items():
            prov = (t.get("prov") or [{}])[0]
            p_no = prov.get("page_no", 0)
            bbox = prov.get("bbox") or {}
            top = bbox.get("t", 0.0)
            ordered_items.append((p_no, -top, "text", ref, t))

        for ref, tb in tables.items():
            prov = (tb.get("prov") or [{}])[0]
            p_no = prov.get("page_no", 0)
            bbox = prov.get("bbox") or {}
            top = bbox.get("t", 0.0)
            ordered_items.append((p_no, -top, "table", ref, tb))

        ordered_items.sort(key=lambda x: (x[0], x[1]))

        for _, _, kind, ref, obj in ordered_items:
            if kind == "text":
                text_content = (obj.get("text") or "").strip()
                if not text_content or any(p.search(text_content) for p in IGNORE_PATTERNS):
                    continue
                if current_section == "Placement & Higher Studies":
                    sub = extract_sub_block(text_content)
                    if sub:
                        current_sub_block = sub
                        continue
                sec_match = match_section_header(text_content)
                if sec_match:
                    current_section = sec_match
                    if current_section != "Placement & Higher Studies":
                        current_sub_block = None
            elif kind == "table":
                if current_section is None:
                    prov = obj.get("prov", [{}])[0]
                    p_no = prov.get("page_no", "?")
                    logger.warning(f"Table {ref} on page {p_no} does not fall under any section header")
                    table_sections[ref] = SectionTag(section="UNMATCHED", sub_block=None)
                else:
                    table_sections[ref] = SectionTag(
                        section=current_section,
                        sub_block=current_sub_block,
                    )

    # Ensure all tables in docling_doc have an entry
    for ref in tables:
        if ref not in table_sections:
            logger.warning(f"Table {ref} was missing from traversal sequence")
            table_sections[ref] = SectionTag(section="UNMATCHED", sub_block=None)

    return table_sections
