"""P1 CHECK B — assertion, not visual inspection, per PROMPTS.md reviewer checklist."""
import json

d = json.load(open("spike/docling.json"))

EXPECTED = ["UG [4 Years Program(s)]", "1161", "1059", "1039", "1030", "-", "-"]
EXPECTED_HEADER = ["Academic Year", "2023-24", "2022-23", "2021-22", "2020-21", "2019-20", "2018-19"]

matches = []
for ti, t in enumerate(d["tables"]):
    grid = t.get("data", {}).get("grid", [])
    for ri, row in enumerate(grid):
        texts = [c.get("text", "") for c in row]
        if texts == EXPECTED:
            header = [c.get("text", "") for c in grid[0]] if ri > 0 else None
            matches.append((ti, ri, header, t.get("prov")))

assert len(matches) >= 1, f"FAIL: expected row {EXPECTED} not found in any table"
ti, ri, header, prov = matches[0]
assert header == EXPECTED_HEADER, f"FAIL: header mismatch: {header}"
assert len(matches) == 1, f"FAIL: row appears in {len(matches)} tables, ambiguous association: {matches}"

print("ASSERTION PASSED")
print(f"table_index={ti} row_index={ri}")
print(f"header={header}")
print(f"row={EXPECTED}")
print(f"provenance={json.dumps(prov)}")
