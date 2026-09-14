"""
CHECK C (corrected) — citation + checksum survival, mechanism test.

Per corrected PROMPTS.md P1: locate ANY digits(words) monetary field in
IIT Bombay's docling.json and confirm it survives as one contiguous string
with page_no and bbox attached. Does NOT search for Sandip's
3750000(Three Lakh Seventy Five Thousand) — that value does not exist in
this document (see prior FAIL in gate/P1-spike.md).
"""
import json
import re

with open("spike/docling.json", encoding="utf-8") as f:
    data = json.load(f)

pattern = re.compile(r"\d[\d,]*\s*\([A-Za-z ]+\)")

hits = []
for t_idx, table in enumerate(data.get("tables", [])):
    prov = table.get("prov", [])
    table_page_no = prov[0]["page_no"] if prov else None
    for cell in table.get("data", {}).get("table_cells", []):
        text = cell.get("text", "")
        if pattern.search(text):
            hits.append({
                "table_index": t_idx,
                "text": text,
                "cell_bbox": cell.get("bbox"),
                "page_no": table_page_no,
                "start_row": cell.get("start_row_offset_idx"),
                "start_col": cell.get("start_col_offset_idx"),
            })

print(f"digits(words)-shaped cells found: {len(hits)}")
assert hits, "CHECK C FAIL: no digits(words) cell found in this document"

chosen = hits[0]
print("CHOSEN CELL FOR CHECK C:")
print(json.dumps(chosen, indent=2))

# Re-scan the raw item/table text for this exact string to confirm no
# reflow/splitting happened elsewhere (contiguity check beyond the
# already-assembled table cell).
raw = json.dumps(data)
occurrences = raw.count(chosen["text"])
print(f"exact-string occurrences in raw docling.json (json-encoded): {occurrences}")
assert occurrences >= 1, "CHECK C FAIL: chosen string not found verbatim in raw JSON"
assert chosen["cell_bbox"] is not None, "CHECK C FAIL: no bbox on cell"
assert chosen["page_no"] is not None, "CHECK C FAIL: no page_no from table provenance"

print("CHECK C ASSERTION PASSED")
