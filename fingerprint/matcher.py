"""Match a converted document against every known profile in profiles/.

PROMPTS.md P2E: "fingerprint/ match a converted document against known
profiles." This module owns the "try every profile, report the outcome"
loop; profiles/engine.py owns applying ONE profile once matched (kept
separate so adding a second profile is a new YAML file, never a change to
this loop).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from profiles.engine import ProfileRunResult, run_profile

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILES_ROOT = REPO_ROOT / "profiles"

NO_MATCH = "NO_MATCH"
MATCHED = "MATCHED"


@dataclass
class FingerprintResult:
    sha256: str
    outcome: str  # MATCHED | NO_MATCH
    profile_id: str | None
    run: ProfileRunResult | None


def known_profile_ids() -> list[str]:
    return sorted(p.stem for p in PROFILES_ROOT.glob("*.yaml"))


def match_document(sha256: str, docling_doc: dict) -> FingerprintResult:
    """Try every known profile in turn. First fingerprint match wins -- if
    two profiles ever both matched the same document this would need a
    tie-break rule, but with one NIRF profile in this iteration that case
    does not exist yet (flagged rather than built against speculatively,
    CLAUDE.md: don't design for hypothetical requirements)."""
    for profile_id in known_profile_ids():
        result = run_profile(profile_id, sha256, docling_doc)
        if result.matched_fingerprint:
            return FingerprintResult(sha256, MATCHED, profile_id, result)
    return FingerprintResult(sha256, NO_MATCH, None, None)
