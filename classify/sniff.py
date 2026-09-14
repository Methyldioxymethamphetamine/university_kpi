"""MIME detection from magic bytes. Never trust the URL/file extension --
`iteration-1-source-investigation.md` and CLAUDE.md both call this out
explicitly: an extension is a claim made by the server or the acquisition
layer's content-type-to-extension map (`acquire/storage.py`), not a fact
about the bytes. This module looks at the bytes.

`filetype` (magic-byte signature matching, same library Docling itself uses
internally to guess format -- see docling/datamodel/document.py) covers
binary formats: PDF, the OOXML/legacy Office formats, images, archives.
It returns None for text-based formats (HTML, JSON, XML, CSV) because those
have no fixed binary signature -- for those we look at the actual leading
bytes ourselves, after stripping BOM/whitespace, which is the same category
of inspection, just done by hand because there is no signature table for it.
"""
from __future__ import annotations

import re

import filetype

# Canonical MIME strings this project's routing logic understands. Anything
# filetype/our own sniff returns outside this set still gets passed through
# verbatim -- classify_label() below maps unrecognised MIME to "unknown"
# rather than raising, per PROMPTS.md P2B ("recognise everything").
PDF = "application/pdf"
HTML = "text/html"
JSON = "application/json"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
DOC = "application/msword"
XLS = "application/vnd.ms-excel"
PPT = "application/vnd.ms-powerpoint"

OFFICE_MIMES = {DOCX, XLSX, PPTX, DOC, XLS, PPT}

_UTF8_BOM = b"\xef\xbb\xbf"
_LEADING_WS = re.compile(rb"^\s*")


def sniff_mime(data: bytes) -> str | None:
    """Return a canonical MIME string derived from the bytes themselves, or
    None if nothing recognisable was found. `data` may be a truncated head
    of the file -- filetype only needs the first few hundred bytes for every
    format it knows, and the text-sniff below only looks at the first
    non-whitespace bytes."""
    guessed = filetype.guess_mime(data)
    if guessed:
        return guessed

    if data.startswith(_UTF8_BOM):
        data = data[len(_UTF8_BOM) :]
    stripped = _LEADING_WS.sub(b"", data)[:512]
    if not stripped:
        return None

    lowered = stripped.lower()
    if lowered.startswith(b"<!doctype html") or lowered.startswith(b"<html") or b"<html" in lowered[:200]:
        return HTML
    if lowered.startswith(b"<?xml") and b"html" in lowered[:300]:
        return HTML
    if stripped[:1] in (b"{", b"["):
        # Not proof it parses (that's convert/'s job) -- just that the byte
        # stream opens like a JSON document rather than claiming to be one
        # via an HTTP header that may lie.
        return JSON
    return None
