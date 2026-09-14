"""P-2 enforcement (CLAUDE.md): Docling output must only ever be written via
save_as_json(). export_to_markdown()/export_to_html() are lossy -- they drop
page numbers and bounding boxes, which destroys the citation chain this
project exists to provide. If this test fails, someone called one of those
methods somewhere under convert/; delete the call, don't tune this test.
"""
from __future__ import annotations

import re
from pathlib import Path

CONVERT_DIR = Path(__file__).resolve().parent.parent / "convert"

FORBIDDEN = re.compile(r"\.export_to_(markdown|html)\s*\(")


def test_no_markdown_or_html_export_in_convert():
    offenders = []
    for path in CONVERT_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN.search(line):
                offenders.append(f"{path}:{lineno}: {line.strip()}")
    assert not offenders, "P-2 violation -- lossy Docling export found:\n" + "\n".join(offenders)
