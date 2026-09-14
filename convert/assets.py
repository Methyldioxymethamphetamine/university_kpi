"""Extract every embedded picture Docling recovered into
docs/<sha8>/assets/ -- "every extracted image, none skipped" (PROMPTS.md
P2B). Requires PdfPipelineOptions.generate_picture_images=True (set in
convert/docling_wrapper.py) -- without it, `picture.image` is None and
there is nothing to write. IIT Bombay's document has zero pictures (P1
CHECK B / classify/'s own per-page profile both agree: 0 images on all 4
pages), so this runs empty against iteration 1's real PDF; it exists so a
future document with real figures does not need a re-crawl to get them out.
"""
from __future__ import annotations

from pathlib import Path

from docling_core.types.doc.document import DoclingDocument


def extract_assets(document: DoclingDocument, assets_dir: Path) -> list[Path]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for i, picture in enumerate(document.pictures, start=1):
        pil_image = picture.get_image(document)
        if pil_image is None:
            continue
        out_path = assets_dir / f"{i:03d}.png"
        pil_image.save(out_path)
        written.append(out_path)
    return written
