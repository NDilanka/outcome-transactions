"""Exp 10 table row check: every docx table row against the render, for each docx attempt, both sides.

Frozen at the lock commit; see exp10-preregistration.md (renderability section, table row check). Scope: docx tables
only. The pptx, odt and xlsx files of Exp 8 contain no tables (checked: python-pptx has_table is false for every slide,
and the odt files have no table element). Spreadsheet print output is covered by the Exp 9 limits.

A row is checkable if one of its cells has at least 3 characters of text after whitespace is removed. A checkable row
is drawn if every such cell text appears in the text of the rendered PDF pages (whitespace removed). A row with no
checkable cell is reported as not checkable. This is a presence test on text, not a test of borders: a row can be
present in the text and still be hidden, so "drawn" here means "its text is in the render". Mismatches are rows whose
text is not in the render. Output holds row numbers and counts only, never cell text.

Usage: exp10_rowcheck.py --work DIR --out FILE
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
EXP8_MAP = '/home/factory-user/exp8/private/map.json'
EXP8_EXEC = '/home/factory-user/exp8/exec'

import docx  # noqa: E402
from docx.table import _Cell  # noqa: E402
import pymupdf  # noqa: E402
import hashlib  # noqa: E402


def norm(s):
    return re.sub(r'\s+', '', s)


def bid10(salt, code):
    return hashlib.sha256((salt + '|exp10|' + code).encode()).hexdigest()[:12]


def file_tables(path):
    """Per table: the rows, each a list of normalised cell texts (unique cells, merged cells once)."""
    d = docx.Document(path)
    out, nested = [], 0
    for t in d.tables:
        nested += sum(len(c.tables) for r in t.rows for c in r.cells)
        rows = []
        for r in t.rows:
            cells = [norm(_Cell(tc, t).text) for tc in r._tr.tc_lst]
            rows.append([c for c in cells if len(c) >= 3])
        out.append(rows)
    return out, nested


def pdf_text(pdf):
    doc = pymupdf.open(pdf)
    text = ''.join(page.get_text() for page in doc)
    doc.close()
    return norm(text)


def check_side(path, pdf):
    tables, nested = file_tables(path)
    text = pdf_text(pdf)
    res = []
    for ti, rows in enumerate(tables, 1):
        checkable = [ri for ri, cells in enumerate(rows, 1) if cells]
        missing = [ri for ri, cells in enumerate(rows, 1) if cells and any(c not in text for c in cells)]
        res.append({'table': ti, 'rows': len(rows), 'checkable': len(checkable),
                    'not_checkable': len(rows) - len(checkable), 'missing': missing})
    return {'tables': res, 'nested_tables': nested}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salt-file', required=True)
    ap.add_argument('--work', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    salt = open(args.salt_file, encoding='utf-8').read().rstrip('\n')
    out = {}
    for e in json.load(open(EXP8_MAP)):
        if e['kind'] != 'docx':
            continue
        bid = bid10(salt, e['code'])
        res = json.load(open(os.path.join(EXP8_EXEC, e['code'], 'result.json'), encoding='utf-8'))
        sides = {'start': e['input_path'], 'end': res['end_state']}
        entry = {}
        for side, path in sides.items():
            pdfs = glob.glob(os.path.join(args.work, bid, side, 'f01', 'pdf', '*.pdf'))
            if len(pdfs) != 1:
                raise SystemExit(f'{bid} {side}: expected one PDF, found {len(pdfs)}')
            entry[side] = check_side(path, pdfs[0])
        out[bid] = entry
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(dict(sorted(out.items())), fh, indent=1)
        fh.write('\n')
    mism = [(b, s, t['table'], t['missing']) for b, v in out.items() for s, r in v.items()
            for t in r['tables'] if t['missing']]
    print('docx attempts checked:', len(out), '| sides:', 2 * len(out),
          '| tables:', sum(len(r['tables']) for v in out.values() for r in v.values()),
          '| tables with a missing row:', len(mism))
    for b, s, t, miss in sorted(mism):
        print(' mismatch', b, s, 'table', t, 'rows', miss)


if __name__ == '__main__':
    main()
