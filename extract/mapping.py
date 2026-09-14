"""Static mapping logic from NIRF extracted table cells to KPI dictionary codes.

Per requirements:
1. Load kpi-to-nirf-mapping.csv's existing DIRECT/DERIVED/ANNEXURE/PARTIAL
   classifications as a static lookup keyed on concept name (the 33 hand-mapped concepts).
2. For any extracted concept not found in that lookup:
   kpi_code = None, mapping_status = 'ORPHAN', domain = section's domain.
3. Every row receives a non-null domain derived from its section.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAPPING_CSV_PATH = REPO_ROOT / "kpi-to-nirf-mapping.csv"

# Allowed mapping statuses
DIRECT = "DIRECT"
DERIVED = "DERIVED"
ANNEXURE = "ANNEXURE"
PARTIAL = "PARTIAL"
ORPHAN = "ORPHAN"
ANOMALY = "ANOMALY"

VALID_STATUSES = {DIRECT, DERIVED, ANNEXURE, PARTIAL, ORPHAN, ANOMALY}

# Canonical domain set per findings/nirf-coverage-of-229-kpis.md
DOMAINS = {"FAC", "STU", "RES", "FIN", "PLC", "X", "ACA", "INT", "INF", "GOV", "ESG"}


@dataclass(frozen=True)
class ConceptMapping:
    concept_name: str
    kpi_code: str | None
    mapping_status: str
    domain: str
    notes: str = ""


def resolve_domain(section: str | None) -> str | None:
    """Derive one of FAC/STU/RES/FIN/PLC/X/ACA/INT/INF/GOV/ESG from section name.
    Base this on the domain breakdown documented in findings/nirf-coverage-of-229-kpis.md.
    """
    if not section:
        return None
    sec = section.strip()

    # Student domain
    if any(k in sec for k in ("Sanctioned (Approved) Intake", "Total Actual Student Strength", "PG Medical")):
        return "STU"

    # Placement domain
    if "Placement" in sec or "Higher Studies" in sec:
        return "PLC"

    # Research domain
    if any(k in sec for k in ("Ph.D Student", "Sponsored Research", "Consultancy Project", "IPR", "Patents")):
        return "RES"

    # Financial domain
    if "Financial Resources" in sec or "Capital expenditure" in sec or "Operational expenditure" in sec:
        return "FIN"

    # Infrastructure domain
    if "PCS Facilities" in sec or "Physically Challenged" in sec:
        return "INF"

    # Faculty domain
    if "Faculty Details" in sec:
        return "FAC"

    # Academic domain
    if "Executive Development" in sec or "Multiple Entry" in sec or "Indian Knowledge" in sec:
        return "ACA"

    # Sustainability / ESG domain
    if "Sustainability" in sec or "Sustainable Living" in sec:
        return "ESG"

    # Cross-cutting / Accreditation
    if "Accreditation" in sec or "NAAC" in sec or "NBA" in sec:
        return "X"

    return "STU"  # fallback default for unclassified NIRF tables


def load_mapping_lookup(path: Path = MAPPING_CSV_PATH) -> dict[str, ConceptMapping]:
    """Load kpi-to-nirf-mapping.csv as a static lookup keyed on concept_name."""
    if not path.exists():
        raise FileNotFoundError(f"Mapping CSV not found: {path}")

    mappings = {}
    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            c_name = row["concept_name"].strip()
            mappings[c_name] = ConceptMapping(
                concept_name=c_name,
                kpi_code=row.get("kpi_code") or None,
                mapping_status=row["mapping_status"].strip(),
                domain=row["domain"].strip(),
                notes=row.get("notes", "").strip(),
            )
    return mappings


_STATIC_LOOKUP: dict[str, ConceptMapping] | None = None


def get_static_lookup() -> dict[str, ConceptMapping]:
    global _STATIC_LOOKUP
    if _STATIC_LOOKUP is None:
        _STATIC_LOOKUP = load_mapping_lookup()
    return _STATIC_LOOKUP


def identify_concept(row: dict) -> str | None:
    """Identify concept name from row metadata (section, row_label, column_label)."""
    section = (row.get("section") or "").strip()
    row_label = (row.get("row_label") or "").strip()
    col_label = (row.get("column_label") or "").strip()

    # 1. Placement & Higher Studies
    if "Placement & Higher Studies" in section:
        if "Median salary" in col_label:
            return "Median salary of placed graduates"
        if "No. of students placed" in col_label:
            return "No. of students placed"
        if "selected for Higher Studies" in col_label:
            return "No. of students selected for Higher Studies"
        if "students intake" in col_label:
            return "No. of first year students intake in the year"
        if "students admitted" in col_label and "Lateral" not in col_label:
            return "No. of first year students admitted in the year"
        if "graduating in minimum stipulated time" in col_label:
            return "No. of students graduating in minimum stipulated time"
        if "Lateral entry" in col_label:
            return "Lateral entry admissions"

    # 2. Sanctioned (Approved) Intake
    if "Sanctioned (Approved) Intake" in section:
        return "Sanctioned Intake"

    # 3. Total Actual Student Strength
    if "Total Actual Student Strength" in section:
        if "Total Students" in col_label:
            return "Total Students"
        if "No. of Male Students" in col_label:
            if "UG" in row_label:
                return "No. of UG Students"
            if "PG" in row_label:
                return "No. of PG Students"
            return "Total Students"
        if "No. of Female Students" in col_label:
            return "No. of Female Students"
        if "Outside State" in col_label:
            return "Outside State"
        if "Outside Country" in col_label:
            return "Outside Country"
        if "Economically Backward" in col_label:
            return "Economically Backward"
        if "Socially Challenged" in col_label:
            return "Socially Challenged"
        if "tuition fee reimbursement" in col_label:
            return col_label

    # 4. Ph.D Student Details
    if "Ph.D Student Details" in section:
        if "Full Time" in row_label:
            return "Full Time PhD scholars"
        if "graduated" in row_label:
            return "No. of Ph.D students graduated (including Integrated Ph.D)"
        if "Part Time" in row_label:
            return "Part Time PhD scholars"

    # 5. Faculty Details
    if "Faculty Details" in section:
        if col_label == "Designation":
            return "Faculty Designation"
        if col_label == "Gender":
            return "Faculty Gender"
        if col_label == "Age":
            return "Faculty Age"
        if col_label == "Qualification":
            return "Faculty Qualification"
        if "Experience" in col_label:
            return "Faculty Experience"
        if "Currently working" in col_label:
            return "Faculty Currently Working"
        if col_label in ("Name of the Faculty", "Name"):
            return "Total full-time faculty"
        # Table cells without clear col_label might be serial count
        return f"Faculty {col_label or 'item'}"

    # 6. Patents
    if "IPR" in section or "Patents" in section:
        if "Published" in row_label:
            return "No. of Patents Published"
        if "Granted" in row_label:
            return "No. of Patents Granted"

    # 7. Sponsored Research Details
    if "Sponsored Research Details" in section:
        if "Total Amount Received (Amount in Rupees)" in row_label:
            return "Sponsored Research Total Amount"
        if "Total no. of Sponsored Projects" in row_label:
            return "Total no. of Sponsored Projects"
        if "Funding Agencies" in row_label:
            return "Funding Agencies count"
        if "Words" in row_label:
            return "Sponsored Research Amount in Words"

    # 8. Financial Resources
    if "Capital expenditure" in section:
        if "Annual Capital Expenditure" in row_label:
            return "Annual Capital Expenditure"
        return row_label  # Library, Engineering Workshops, Studios, etc.
    if "Operational expenditure" in section:
        if "Annual Operational Expenditure" in row_label:
            return "Annual Operational Expenditure"
        return row_label  # Salaries, Maintenance, Seminars, etc.

    # 9. PCS Facilities
    if "PCS Facilities" in section:
        return "PCS Facilities"

    # 10. Multiple Entry / Grievance / Sustainability
    if "Multiple Entry" in section or "Sustainability" in section:
        if "Grievance" in row_label:
            return "Grievance Redressal Cell"
        if "multiple entry/exit" in row_label.lower():
            return "Multiple Entry/Exit"
        if "waste" in row_label.lower():
            return "Waste Management"
        return row_label

    return row_label or col_label or section


def resolve_mapping(row: dict) -> tuple[str | None, str, str | None]:
    """Resolve an extracted row to (kpi_code, mapping_status, domain).

    Returns:
        (kpi_code, mapping_status, domain)
        If anomaly_reason is present or mapping_status is ANOMALY:
            returns (None, 'ANOMALY', domain)
        If concept matched in static lookup:
            returns (mapping.kpi_code, mapping.mapping_status, domain)
        If not matched (orphan):
            returns (None, 'ORPHAN', domain)
    """
    section = row.get("section")
    domain = resolve_domain(section)

    if row.get("anomaly_reason") or row.get("mapping_status") == ANOMALY:
        return None, ANOMALY, domain

    concept = identify_concept(row)

    lookup = get_static_lookup()
    if concept and concept in lookup:
        mapping = lookup[concept]
        return mapping.kpi_code, mapping.mapping_status, domain or mapping.domain

    # Fallback to ORPHAN
    return None, ORPHAN, domain
