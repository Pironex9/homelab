#!/usr/bin/env python3
"""Fails if a subsetted font in brand/ dropped a character the properties need.

Run: python3 brand/check-fonts.py

The subsetting command lives in the plan and in BRAND.md, and it is easy to
run with a narrower --unicodes range than intended. The failure mode is
silent: the page renders, and only the affected glyph falls back to a system
face. This check turns that into an error.
"""
import pathlib
import sys

from fontTools.ttLib import TTFont

BRAND = pathlib.Path(__file__).resolve().parent

# Latin, digits, the punctuation the three surfaces actually set, and the
# Hungarian accented letters. Hungarian is the reason the subset range goes
# past Latin-1: o-double-acute and u-double-acute live in Latin Extended-A.
REQUIRED = "ABCXYZabcxyz0123456789.,:;/-()[]&%+'\"áéíóöúüőű"

EXPECTED = [
    "ibm-plex-sans-var.woff2",
    "ibm-plex-mono-400.woff2",
    "ibm-plex-mono-500.woff2",
    "big-shoulders-var.woff2",
]


def main():
    failed = False
    for name in EXPECTED:
        path = BRAND / name
        if not path.exists():
            print(f"MISSING: {name}")
            failed = True
            continue
        cmap = TTFont(path).getBestCmap()
        missing = [c for c in REQUIRED if ord(c) not in cmap]
        if missing:
            print(f"{name}: subset dropped {''.join(missing)}")
            failed = True
        else:
            print(f"ok: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
