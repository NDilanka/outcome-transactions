"""Mutation-gate inputs for Exp 6. Written by me, not by the spec writers or the blind generator.

1. positive(task): one correct end state per subset task, built with python libraries (independent of the spec's logic).
   It is the gate's positive control only. It is never used as a blind evaluation state.
2. mutants(task): generic file-level mutants applied to the positive state (wrong by construction: each changes
   something the request does not ask for, or undoes the requested change).
Outputs go under research/exp6-executed/gate/<task8>/{start,positive,mut_<op>}/home/user/...
"""
import copy, glob, os, shutil, stat, subprocess, sys
import openpyxl
from docx import Document
from pptx import Presentation
from pptx.dml.color import RGBColor
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, '..', 'exp5-grounded', 'snapshots')
GATE = os.path.join(HERE, 'gate')
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def snap(prefix):
    return glob.glob(os.path.join(SNAP, prefix + '*'))[0]


def fresh(task8, name, src):
    dst = os.path.join(GATE, task8, name)
    if os.path.exists(dst): shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True)
    return dst


def ubuntu(root, p):
    return os.path.join(root, p.lstrip('/'))


def lo_roundtrip(path):
    """Re-save through LibreOffice headless, as a GUI save would (recalculates formulas, writes its own XML)."""
    out = os.path.join(os.path.dirname(path), '_lo')
    os.makedirs(out, exist_ok=True)
    subprocess.run(['soffice', '--headless', '--convert-to', os.path.splitext(path)[1][1:], '--outdir', out, path],
                   check=True, capture_output=True, timeout=240)
    shutil.move(os.path.join(out, os.path.basename(path)), path)
    shutil.rmtree(out)


# ---------------------------------------------------------------- positives (one correct state per task)

def pos_1273e544(root):
    p = ubuntu(root, '/home/user/NetIncome.xlsx')
    wb = openpyxl.load_workbook(p)
    src, dst = wb['Sheet1'], wb.create_sheet('Sheet2')
    for r in range(1, 21):
        dst.cell(r, 1).value = src.cell(r, 1).value
    wb.save(p); lo_roundtrip(p)


def pos_42e0a640(root):
    p = ubuntu(root, '/home/user/NetIncome.xlsx')
    wb = openpyxl.load_workbook(p)
    ws = wb['Sheet1']
    s2 = wb.create_sheet('Sheet2')
    s2['A1'], s2['B1'] = 'Total Revenue', 'Total Expenses'
    s2['A2'] = sum(ws.cell(r, 1).value for r in range(2, 21))
    s2['B2'] = sum(ws.cell(r, 2).value for r in range(2, 21))
    wb.save(p); lo_roundtrip(p)


def pos_6054afcb(root):
    p = ubuntu(root, '/home/user/Date_Budget_Variance_HideNA.xlsx')
    wb = openpyxl.load_workbook(p)
    ws = wb['Sheet1']
    for r in range(1, ws.max_row + 1):
        if ws.cell(r, 4).value == '=NA()': ws.row_dimensions[r].hidden = True
    wb.save(p); lo_roundtrip(p)


def pos_a9f325aa(root):
    p = ubuntu(root, '/home/user/Movie_title_garbage_clean.xlsx')
    wb = openpyxl.load_workbook(p)
    ws = wb['Sheet1']
    ws['C1'] = 'Clean Movie Titles'
    for r in range(2, 30):
        raw = ws.cell(r, 2).value or ''
        words = ' '.join(raw.split()).split(' ')
        out = []
        for w in words:
            i = next((k for k, ch in enumerate(w) if ch.isalpha()), None)
            out.append(w if i is None else w[:i] + w[i].upper() + w[i + 1:].lower())
        ws.cell(r, 3).value = ' '.join(out)
    wb.save(p); lo_roundtrip(p)


def pos_f23acfd2(root):
    p = ubuntu(root, '/home/user/Desktop/69_4.pptx')
    prs = Presentation(p)
    sh = next(s for s in prs.slides[0].shapes if s.name == 'PlaceHolder 2')
    para = sh.text_frame.paragraphs[0]._p
    pPr = para.get_or_add_pPr() if hasattr(para, 'get_or_add_pPr') else para.find(A + 'pPr')
    if pPr is None:
        pPr = etree.SubElement(para, A + 'pPr'); para.insert(0, pPr)
    for child in list(pPr):
        if etree.QName(child).localname in ('buNone', 'buChar', 'buAutoNum'): pPr.remove(child)
    pPr.set('marL', '342900'); pPr.set('indent', '-342900')
    bu = etree.Element(A + 'buChar'); bu.set('char', '\u2022')
    pPr.append(bu)
    prs.save(p); lo_roundtrip(p)


def pos_57667013(root):
    p = ubuntu(root, '/home/user/Desktop/1_2.pptx')
    prs = Presentation(p)
    for sh in prs.slides[4].shapes:
        if sh.name in ('Google Shape;166;p 1', 'Google Shape;167;p 1') and sh.has_text_frame:
            for para in sh.text_frame.paragraphs:
                for r in para.runs: r.font.color.rgb = RGBColor(0xFF, 0xFF, 0x00)
    prs.save(p); lo_roundtrip(p)


def pos_21760ecb(root):
    p = ubuntu(root, '/home/user/Desktop/Ch4 Video Effect.pptx')
    prs = Presentation(p)
    s1 = prs.slides[0]._element
    tr = etree.Element(P + 'transition'); tr.set('spd', 'med')
    etree.SubElement(tr, P + 'dissolve')
    anchor = s1.find(P + 'clrMapOvr')
    (anchor.addnext(tr) if anchor is not None else s1.insert(1, tr))
    prs.save(p); lo_roundtrip(p)


def pos_d53ff5ee(root):
    p = ubuntu(root, '/home/user/Desktop/presentation_instruction_2023_Feb.docx')
    doc = Document(p)
    paras = list(doc.paragraphs) + [pp for t in doc.tables for row in t.rows for c in row.cells for pp in c.paragraphs]
    for para in paras:
        for r in para.runs: r.text = r.text.lower()
    doc.save(p); lo_roundtrip(p)


def _para_with_text(src_p, text):
    new = copy.deepcopy(src_p)
    runs = new.findall(W + 'r')
    for r in runs[1:]: new.remove(r)
    if runs:
        for t in runs[0].findall(W + 't'): runs[0].remove(t)
        t = etree.SubElement(runs[0], W + 't'); t.text = text
    else:
        r = etree.SubElement(new, W + 'r'); t = etree.SubElement(r, W + 't'); t.text = text
    return new


def pos_88fe4b2d(root):
    import re
    p = ubuntu(root, '/home/user/Desktop/CCCH9003_Tutorial_guidelines.docx')
    doc = Document(p)
    p1 = doc.paragraphs[0]
    sents = [s for s in re.split(r'(?<=[.!?])\s+', p1.text.strip()) if s]
    anchor = p1._p
    for s in sents:
        newp = _para_with_text(p1._p, s); anchor.addnext(newp); anchor = newp
        blank = _para_with_text(p1._p, ''); anchor.addnext(blank); anchor = blank
    p1._p.getparent().remove(p1._p)
    doc.save(p); lo_roundtrip(p)


def pos_936321ce(root):
    p = ubuntu(root, '/home/user/Desktop/Graphemes_Sound_Letter_Patterns.docx')
    doc = Document(p)
    paras = doc.paragraphs[4:9]  # paragraphs 5-9: the comma-separated block
    rows = [[c.strip() for c in pp.text.split(',')] for pp in paras]
    tbl = doc.add_table(rows=len(rows), cols=4)
    for i, row in enumerate(rows):
        for j, cell in enumerate(row): tbl.cell(i, j).text = cell
    paras[0]._p.addprevious(tbl._tbl)
    for pp in paras: pp._p.getparent().remove(pp._p)
    doc.save(p); lo_roundtrip(p)


def pos_ecc2413d(root):
    p = ubuntu(root, '/home/user/Desktop/Sample_Statutory_Declaration.docx')
    doc = Document(p)
    anchor = doc.paragraphs[4]._p
    for _ in range(2):  # Ctrl+Enter twice: one empty page between page 1 and the next
        newp = etree.Element(W + 'p'); r = etree.SubElement(newp, W + 'r')
        etree.SubElement(r, W + 'br').set(W + 'type', 'page')
        anchor.addnext(newp); anchor = newp
    doc.save(p); lo_roundtrip(p)


def pos_4d117223(root):
    base = ubuntu(root, '/home/user/testDir')
    for dp, dns, fns in os.walk(base):
        for f in fns:
            fp = os.path.join(dp, f)
            os.chmod(fp, 0o644)


POSITIVE = {'1273e544': pos_1273e544, '42e0a640': pos_42e0a640, '6054afcb': pos_6054afcb, 'a9f325aa': pos_a9f325aa,
            'f23acfd2': pos_f23acfd2, '57667013': pos_57667013, '21760ecb': pos_21760ecb, 'd53ff5ee': pos_d53ff5ee,
            '88fe4b2d': pos_88fe4b2d, '936321ce': pos_936321ce, 'ecc2413d': pos_ecc2413d, '4d117223': pos_4d117223}
SOURCE = {'1273e544': '1273e544', '42e0a640': '42e0a640', '6054afcb': '6054afcb', 'a9f325aa': 'a9f325aa',
          'f23acfd2': 'f23acfd2', '57667013': '57667013', '21760ecb': '21760ecb', 'd53ff5ee': 'd53ff5ee',
          '88fe4b2d': '88fe4b2d', '936321ce': '936321ce', 'ecc2413d': 'ecc2413d', '4d117223': '4d117223'}


def make_start(task8):
    """Start root for a subset task. 4d117223 is built the way its setup.sh builds it."""
    if task8 != '4d117223':
        return fresh(task8, 'start', snap(task8))
    root = os.path.join(GATE, task8, 'start')
    if os.path.exists(root): shutil.rmtree(root)
    base = os.path.join(root, 'home/user/testDir')
    os.makedirs(os.path.join(base, 'subDir1')); os.makedirs(os.path.join(base, 'subDir2'))
    for rel, mode in [('file1.txt', 0o755), ('subDir1/file2.txt', 0o644), ('subDir2/file3.txt', 0o777)]:
        fp = os.path.join(base, rel); open(fp, 'w').close(); os.chmod(fp, mode)
    for d in ('testDir', 'testDir/subDir1', 'testDir/subDir2'):
        os.chmod(os.path.join(root, 'home/user', d), 0o755)
    return root


def build_positive(task8):
    start = make_start(task8)
    dst = fresh(task8, 'positive', start)
    POSITIVE[task8](dst)
    return dst


if __name__ == '__main__':
    for t in POSITIVE:
        build_positive(t)
        print('positive built', t)
