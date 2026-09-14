"""Docling wrapper: converted-document JSON only (P-2 -- save_as_json(),
never export_to_markdown()/export_to_html(), both lossy: they drop page and
bbox). Runs only for labels iteration 1 needs (pdf_digital, pdf_mixed,
pdf_scan, html_table); everything else classify/ recognised stays a label
and a manifest row, per PROMPTS.md P2B, with no conversion attempted.
"""
