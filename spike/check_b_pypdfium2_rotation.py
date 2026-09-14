"""P1 CHECK B (independent) — pypdfium2 raw text-run dump: page rotation + text angle."""
import math

import pypdfium2 as pdfium

SRC = "spike/raw/sha256/e9a1d469ba17262f052948f22d8a15b6f4c37a4646af72efea77e0a7e0b1e019"

pdf = pdfium.PdfDocument(SRC)
page = pdf[0]
rotation = page.get_rotation()

textpage = page.get_textpage()
n = textpage.count_chars()
angles = set()
sample = []
for i in range(min(n, 4000)):
    matrix = textpage.get_charbox(i) if False else None  # not used; matrix comes from loose obj below

# Use the text object matrix directly for angle, per glyph run, via GetCharBox is insufficient;
# pypdfium2 exposes per-object matrices through the page's object list.
for obj in page.get_objects():
    if obj.type != pdfium.raw.FPDF_PAGEOBJ_TEXT:
        continue
    m = obj.get_matrix()
    angle = round(math.degrees(math.atan2(m.b, m.a)))
    angles.add(angle)
    if len(sample) < 5:
        sample.append({"angle": angle, "matrix": (m.a, m.b, m.c, m.d, m.e, m.f)})

print(f"page_rotation_degrees={rotation}")
print(f"distinct_text_angles={sorted(angles)}")
print("sample_text_object_matrices:")
for s in sample:
    print(" ", s)
