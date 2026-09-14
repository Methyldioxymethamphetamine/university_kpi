"""Per-artifact classification: MIME from magic bytes, per-page structural
profile (chars, images, rotation), and a routing label.

P-3 boundary note: P-3 forbids parsing *inside acquisition* (acquire/).
Classification is not acquisition -- it is the layer PROMPTS.md P2B exists
to build -- so inspecting bytes here (magic-byte sniffing, per-page text/
image counts) is in scope, not a violation.
"""
