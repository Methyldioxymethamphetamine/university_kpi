"""P1 CHECK B (part 1) — convert with Docling, save_as_json(), per P-2."""
from pathlib import Path

from docling.document_converter import DocumentConverter

SRC = Path("spike/raw/sha256/e9a1d469ba17262f052948f22d8a15b6f4c37a4646af72efea77e0a7e0b1e019")
OUT = Path("spike/docling.json")

converter = DocumentConverter()
result = converter.convert(str(SRC))
result.document.save_as_json(OUT)
print(f"wrote {OUT}, {OUT.stat().st_size} bytes")
print(f"num_pages: {len(result.document.pages)}")
