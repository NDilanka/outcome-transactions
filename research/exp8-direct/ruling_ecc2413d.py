"""Exp 8: LibreOffice render check for ecc2413d (page layout request). POST-HOC GT check, not pre-registered.

Ruling (orchestrator): for a page-layout request the ground truth is the rendered page, not the XML. This script
renders the input and the four end states to PDF with LibreOffice (one profile per file) and compares pages.
The Word render is NOT checked here (no Word available), so it is unverified.

For each file it prints the page count, the blank pages, and, for each output page, the input page with the same
text (or none).

Run with the exp8 venv (pypdf):
  /home/factory-user/venvs/exp8/bin/python ruling_ecc2413d.py
"""
import os
import shutil
import subprocess

from pypdf import PdfReader

WORK = '/tmp/exp8_render'
EXEC = '/home/factory-user/exp8/exec'
INPUT = '/home/factory-user/exp8/run/476b080a/input/Sample_Statutory_Declaration.docx'
CODES = ['476b080a', 'eeb4b683', '02d030c7', '7b72ebd1']  # method 1, 2, 3, 4


def render(name, src_docx):
    d = os.path.join(WORK, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    src = os.path.join(d, 'doc.docx')
    shutil.copy(src_docx, src)
    cmd = ['soffice', f'-env:UserInstallation=file://{WORK}/profile_{name}', '--headless',
           '--convert-to', 'pdf', '--outdir', d, src]
    subprocess.run(cmd, check=True, timeout=240, capture_output=True)
    return [' '.join((p.extract_text() or '').split()) for p in PdfReader(os.path.join(d, 'doc.pdf')).pages]


def main():
    inp = render('input', INPUT)
    print(f'input: {len(inp)} pages, blank pages {[i + 1 for i, t in enumerate(inp) if not t]}')
    for code in CODES:
        end = __import__('json').load(open(os.path.join(EXEC, code, 'result.json')))['end_state']
        pages = render(code, end)
        blank = [i + 1 for i, t in enumerate(pages) if not t]
        matches = []
        for i, t in enumerate(pages):
            same = [j + 1 for j, u in enumerate(inp) if u == t and t]
            matches.append(f'p{i + 1}={same[0] if same else ("blank" if not t else "-")}')
        print(f'{code}: {len(pages)} pages, blank pages {blank}; output page -> input page with same text: '
              + ', '.join(matches))
        print(f'  page 1 text equals input page 1: {pages[0] == inp[0]}')


if __name__ == '__main__':
    main()
