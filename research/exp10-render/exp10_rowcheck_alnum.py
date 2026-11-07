"""Exp 10 table row check, post hoc alphanumeric variant (Addendum A, labelled post hoc).

Same test as exp10_rowcheck.py (locked), with one change: text is compared as letters and digits only, lower case.
Reason, found after the locked run: the strict test flagged 8 table sides in 4 attempts. In each, the text of a
multi-line list cell is in the render, but LibreOffice draws a list bullet ("- ") that is not in the cell text, and
breaks a page range at a hyphen. Punctuation and line breaks are not what the row check is about, so this variant
ignores them. It is reported next to the locked result, never in place of it.

Usage: exp10_rowcheck_alnum.py --salt-file FILE --work DIR --out FILE
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exp10_rowcheck as rc  # noqa: E402

rc.norm = lambda s: re.sub(r'[^0-9a-z]', '', s.lower())

if __name__ == '__main__':
    rc.main()
