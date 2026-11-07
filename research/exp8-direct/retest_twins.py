"""Exp 8: for each judge-flipped packet, find end states with identical content (its twins) and their verdicts.

Content is compared per format, on the end state files:
  xlsx: every cell value or formula, plus the set of hidden rows (openpyxl)
  docx: the text of every paragraph in word/document.xml, including table cells
  directory (LibreOffice profile): sha256 of each file, by relative path
Other formats are reported as not compared.
For a flipped profile, the files that differ from each other end state of the same task are listed.

Also checks, for the 6054afcb task, that the hidden rows are exactly the rows containing the =NA() formula.

Run with the exp8 venv:
  /home/factory-user/venvs/exp8/bin/python retest_twins.py > retest_twins_output.txt
"""
import hashlib
import json
import os
import sys
import zipfile
from xml.etree import ElementTree as ET

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import retest as rt  # noqa: E402

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
MAP = '/home/factory-user/exp8/private/map.json'
EXEC = '/home/factory-user/exp8/exec'


def files_of(root):
    out = {}
    for d, _, names in os.walk(root):
        for n in names:
            p = os.path.join(d, n)
            out[os.path.relpath(p, root)] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    return out


def content(path):
    if os.path.isdir(path):
        return ('dir', tuple(sorted(files_of(path).items())))
    ext = os.path.splitext(path)[1].lower()
    if ext == '.xlsx':
        wb = openpyxl.load_workbook(path)
        out = []
        for ws in wb.worksheets:
            hidden = tuple(sorted(r for r, d in ws.row_dimensions.items() if d.hidden))
            vals = tuple(sorted((c.coordinate, str(c.value)) for row in ws.iter_rows() for c in row if c.value is not None))
            out.append((ws.title, hidden, vals))
        return ('xlsx', tuple(out))
    if ext == '.docx':
        root = ET.fromstring(zipfile.ZipFile(path).read('word/document.xml'))
        paras = tuple(''.join(t.text or '' for t in p.iter(W + 't')) for p in root.iter(W + 'p'))
        return ('docx', paras)
    return (ext, None)


def main():
    bm = json.load(open(rt.BLIND_MAP))
    cb = {v: k for k, v in bm.items()}
    first = rt.read_pass(rt.FIRST)
    second = rt.read_pass(rt.SECOND)
    mp = json.load(open(MAP))
    end = {e['code']: json.load(open(os.path.join(EXEC, e['code'], 'result.json')))['end_state'] for e in mp}
    contents = {e['code']: content(end[e['code']]) for e in mp}
    flips = sorted(b for b in first if first[b]['verdict'] != second[b]['verdict'])
    for b in flips:
        code = bm[b]
        short = next(e['short'] for e in mp if e['code'] == code)
        print(f'== flipped {code} (task {short}, GT label from v3 file)')
        if contents[code][0] not in ('xlsx', 'docx', 'dir'):
            print('  format not compared')
            continue
        twins = [e for e in mp if e['short'] == short and e['code'] != code and contents[e['code']] == contents[code]]
        print('  identical end states in this task: ' + (', '.join(
            f"{t['code']} (m{t['method_idx']}, first {first[cb[t['code']]]['verdict']} {first[cb[t['code']]]['confidence']}, "
            f"second {second[cb[t['code']]]['verdict']} {second[cb[t['code']]]['confidence']})" for t in twins) or 'none'))
        if contents[code][0] == 'dir':
            mine = files_of(end[code])
            for e in mp:
                if e['short'] == short and e['code'] != code:
                    other = files_of(end[e['code']])
                    diff = sorted(f for f in set(mine) | set(other) if mine.get(f) != other.get(f))
                    print(f"  files differing from {e['code']} (m{e['method_idx']}): {', '.join(diff) or 'none'}")
    print()
    # 6054afcb: hidden rows vs the rows that contain =NA()
    for e in (x for x in mp if x['short'] == '6054afcb'):
        ws = openpyxl.load_workbook(end[e['code']]).worksheets[0]
        na_rows = sorted({c.row for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.upper() == '=NA()'})
        hidden = sorted(r for r, d in ws.row_dimensions.items() if d.hidden)
        print(f'6054afcb m{e["method_idx"]} ({e["code"]}): rows with =NA(): {na_rows}')
        print(f'  hidden rows: {hidden}')
        print(f'  hidden rows are exactly the =NA() rows: {na_rows == hidden}')


if __name__ == '__main__':
    main()
