"""Value extraction and the digits/words checksum, per PROMPTS.md P2C.

Reimplements work that already failed once (notes/methodology.md Sec6.3,
findings/digits-words-checksum-analysis.md). Read those before touching this
package -- the bugs they document (scale mis-absorption, spoken-idiom
misparse, wrapped-cell truncation, two-state accuse/confirm collapse) are
exactly what the modules here are built to not repeat.
"""
