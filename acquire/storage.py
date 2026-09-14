"""Content-addressed raw store. Write-once (P-4): a path under raw/ is never
overwritten and never deleted; a re-fetch producing different bytes gets a
different sha256 and therefore a different path -- it is a NEW artifact, not
an update to this one.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

RAW_ROOT = Path("raw/sha256")

# [ASSUMED] fitted to the three iteration-1 sources' observed Content-Type
# headers only (PDF from NIRF/Sandip, HTML from MIT CDS). This is HTTP
# header bookkeeping for a local filename, not content sniffing -- the bytes
# themselves are never opened or interpreted here (P-3). Anything not in
# this map falls back to .bin rather than guessing; real type detection from
# magic bytes belongs to classify/ in P2B, not here.
_EXT_BY_CONTENT_TYPE = {
    "application/pdf": ".pdf",
    "text/html": ".html",
    "application/json": ".json",
}


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ext_for(content_type: str | None) -> str:
    if not content_type:
        return ".bin"
    base = content_type.split(";", 1)[0].strip().lower()
    return _EXT_BY_CONTENT_TYPE.get(base, ".bin")


def raw_path(sha256: str, content_type: str | None) -> Path:
    return RAW_ROOT / sha256[:2] / sha256[2:4] / f"{sha256}{ext_for(content_type)}"


def write_once(path: Path, data: bytes) -> bool:
    """Write iff the path is absent. Returns True iff a new file was
    created. Never overwrites (P-4): if the path already exists, content
    addressing already guarantees the bytes on disk equal `data`, so no
    write (and no re-verification of that guarantee) happens here."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    tmp.rename(path)  # atomic on a POSIX filesystem, avoids a half-written file at `path`
    return True
