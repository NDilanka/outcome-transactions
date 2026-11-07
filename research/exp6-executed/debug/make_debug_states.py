"""DEBUG ONLY (Exp 6 harness check). These states are written by me, so they are excluded from all Exp 6 results.
Builds a correct state, one plausible wrong state, and a copy of the start state for three tasks."""
import os, shutil, glob
import openpyxl
from pptx import Presentation
from pptx.util import Pt
from docx import Document
from pptx.dml.color import RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, '..', '..', 'exp5-grounded', 'snapshots')
OUT = os.path.join(HERE, 'states')


def snap(prefix):
    return glob.glob(os.path.join(SNAP, prefix + '*'))[0]


def fresh(task, name, src_root):
    dst = os.path.join(OUT, task, name)
    if os.path.exists(dst): shutil.rmtree(dst)
    shutil.copytree(src_root, dst)
    return dst


def calc(task):
    src = snap('42e0a640')
    wb = openpyxl.load_workbook(os.path.join(src, 'home/user/NetIncome.xlsx'))
    ws = wb['Sheet1']
    hdr = {c.value: c.column_letter for c in ws[1] if c.value}
    rev_col, exp_col = hdr.get('Revenue', 'A'), hdr.get('Total Expenses')
    last = ws.max_row
    while ws[f'{rev_col}{last}'].value in (None, ''): last -= 1
    rev = sum(ws[f'{rev_col}{r}'].value or 0 for r in range(2, last + 1))
    exp = sum(ws[f'{exp_col}{r}'].value or 0 for r in range(2, last + 1))
    for name, rsum in (('correct', rev), ('wrong_sum_off_by_one', rev - ws[f'{rev_col}{last}'].value)):
        root = fresh(task, name, src)
        wb2 = openpyxl.load_workbook(os.path.join(root, 'home/user/NetIncome.xlsx'))
        s2 = wb2.create_sheet('Sheet2')
        s2['A1'], s2['B1'] = 'Total Revenue', 'Total Expenses'
        s2['A2'], s2['B2'] = rsum, exp
        wb2.save(os.path.join(root, 'home/user/NetIncome.xlsx'))
    fresh(task, 'start', src)
    print('calc done', rev, exp, last, exp_col)


def impress(task):
    src = snap('57667013')
    for name in ('correct', 'wrong_one_shape_only'):
        root = fresh(task, name, src)
        p = os.path.join(root, 'home/user/Desktop/1_2.pptx')
        prs = Presentation(p)
        s5 = prs.slides[4]
        targets = ['Google Shape;166;p 1'] if name.startswith('wrong') else ['Google Shape;166;p 1', 'Google Shape;167;p 1']
        for sh in s5.shapes:
            if sh.name in targets and sh.has_text_frame:
                for para in sh.text_frame.paragraphs:
                    for r in para.runs: r.font.color.rgb = RGBColor(0xFF, 0xFF, 0x00)
        prs.save(p)
    fresh(task, 'start', src)


def writer(task):
    src = snap('d53ff5ee')
    for name in ('correct', 'wrong_body_only'):
        root = fresh(task, name, src)
        p = os.path.join(root, 'home/user/Desktop/presentation_instruction_2023_Feb.docx')
        doc = Document(p)
        for para in doc.paragraphs:
            for r in para.runs: r.text = r.text.lower()
        if name == 'correct':
            for t in doc.tables:
                for row in t.rows:
                    for c in row.cells:
                        for para in c.paragraphs:
                            for r in para.runs: r.text = r.text.lower()
        doc.save(p)
    fresh(task, 'start', src)


if __name__ == '__main__':
    calc('42e0a640'); impress('57667013'); writer('d53ff5ee')
    print('states written under', OUT)
