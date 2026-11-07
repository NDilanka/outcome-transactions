"""Mutation gate inputs for Exp 6. Written by me from each request's stated outcome, not from any spec.

Bases (positive controls):
- gold<j>: the start root with OSWorld's own gold file placed at the result path. Independent of my construction.
  Used for every subset task that ships a gold file.
- positive: the gate_build.py positive, for tasks without a gold file (21760ecb, ecc2413d, 4d117223).

Mutants: each one changes something the request does not ask for, or undoes the change it asks for.
Each mutant is a file-level edit of a base root. Output: gate/roots_mutants.json for gate_check.py.
Mutants are for the gate only. They are not blind evaluation states.
"""
import glob, json, os, re, shutil, sys

import openpyxl
from docx import Document
from pptx import Presentation
from pptx.dml.color import RGBColor
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gate_build as GB  # noqa: E402
import official_check  # noqa: E402

GOLD_DIR = os.path.join(HERE, 'osworld_gold')
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def ensure_start(task8):
    if not os.path.isdir(os.path.join(GB.GATE, task8, 'start')):
        GB.make_start(task8)
    return os.path.join(GB.GATE, task8, 'start')


def gold_roots(task_full):
    """One root per OSWorld gold file that the official checker compares against."""
    task8 = task_full[:8]
    ev = official_check.config_for(task_full)
    results = ev['result'] if isinstance(ev['result'], list) else [ev['result']]
    expected = ev['expected'] if isinstance(ev['expected'], list) else [ev['expected']]
    paths = {r['path'] for r in results if isinstance(r, dict) and r.get('type') == 'vm_file'}
    if len(paths) != 1:
        return []
    path = paths.pop()
    out = []
    for j, exp in enumerate(expected):
        if not (isinstance(exp, dict) and exp.get('type') == 'cloud_file'):
            continue
        gold = os.path.join(GOLD_DIR, task8, exp['dest'])
        if not os.path.exists(gold):
            continue
        dst = GB.fresh(task8, f'gold{j + 1}', ensure_start(task8))
        shutil.copyfile(gold, GB.ubuntu(dst, path))
        out.append((f'gold{j + 1}', dst))
    return out


def copy_base(base, task8, name):
    dst = os.path.join(GB.GATE, task8, 'mut_' + name)
    if os.path.exists(dst): shutil.rmtree(dst)
    shutil.copytree(base, dst, symlinks=True)
    return dst


def pick_nonempty(ws, col, skip=lambda v: False):
    for r in range(1, ws.max_row + 1):
        v = ws.cell(r, col).value
        if v not in (None, '') and not skip(v): return r
    raise ValueError('no suitable cell')


# ---------------------------------------------------------------- mutant definitions

def m_a9f325aa(root, name):
    p = GB.ubuntu(root, '/home/user/Movie_title_garbage_clean.xlsx')
    wb = openpyxl.load_workbook(p); ws = wb['Sheet1']
    if name == 'wrong_value': ws['C5'] = 'Wrong Title'
    elif name == 'lowercase_title': ws['C4'] = 'enemy of the stuke'
    elif name == 'source_changed': ws['B2'] = 'Changed Source'
    elif name == 'stray_cell': ws['E3'] = 'x'
    elif name == 'header_removed': ws['C1'] = None
    else: raise KeyError(name)
    save_xlsx(wb, p)


def save_xlsx(wb, p):
    """openpyxl drops cached formula values on save; a LibreOffice re-save recalculates them, as a GUI save does."""
    wb.save(p)
    GB.lo_roundtrip(p)


def m_42e0a640(root, name):
    p = GB.ubuntu(root, '/home/user/NetIncome.xlsx')
    wb = openpyxl.load_workbook(p); s1, s2 = wb['Sheet1'], wb['Sheet2']
    if name == 'wrong_sum': s2['A2'] = '=SUM(Sheet1!A2:A19)'  # last revenue row left out
    elif name == 'swapped_columns': s2['A2'], s2['B2'] = s2['B2'].value, s2['A2'].value
    elif name == 'sheet_renamed': s2.title = 'Sheet 2'
    elif name == 'source_changed': s1['B3'] = s1['B3'].value + 5
    else: raise KeyError(name)
    save_xlsx(wb, p)


def m_1273e544(root, name):
    p = GB.ubuntu(root, '/home/user/NetIncome.xlsx')
    wb = openpyxl.load_workbook(p); s1, s2 = wb['Sheet1'], wb['Sheet2']
    if name == 'wrong_value': s2['A5'] = 0
    elif name == 'header_removed': s2['A1'] = None
    elif name == 'source_changed': s1['A3'] = 0
    elif name == 'sheet_renamed': s2.title = 'Sheet 2'
    else: raise KeyError(name)
    save_xlsx(wb, p)


def m_6054afcb(root, name):
    p = GB.ubuntu(root, '/home/user/Date_Budget_Variance_HideNA.xlsx')
    wb = openpyxl.load_workbook(p); ws = wb['Sheet1']
    if name == 'unhide_all':
        for r, d in ws.row_dimensions.items(): d.hidden = False
    elif name == 'hide_extra':
        r = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 4).value not in (None, '') and ws.cell(r, 4).value != '=NA()')
        ws.row_dimensions[r].hidden = True
    elif name == 'row_deleted':
        r = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 4).value == '=NA()')
        ws.delete_rows(r)
    else: raise KeyError(name)
    save_xlsx(wb, p)


def m_f23acfd2(root, name):
    p = GB.ubuntu(root, '/home/user/Desktop/69_4.pptx')
    prs = Presentation(p)
    if name == 'bullet_removed':
        sh = next(s for s in prs.slides[0].shapes if s.name == 'PlaceHolder 2')
        pPr = sh.text_frame.paragraphs[0]._p.find(A + 'pPr')
        for c in list(pPr):
            if etree.QName(c).localname in ('buChar', 'buAutoNum'): pPr.remove(c)
        etree.SubElement(pPr, A + 'buNone')
    elif name == 'text_changed':
        sh = next(s for s in prs.slides[0].shapes if s.name == 'PlaceHolder 2')
        sh.text_frame.paragraphs[0].runs[0].text = 'Changed content text'
    elif name == 'extra_slide':
        prs.slides.add_slide(prs.slides[0].slide_layout)
    else: raise KeyError(name)
    prs.save(p)


def m_57667013(root, name):
    p = GB.ubuntu(root, '/home/user/Desktop/1_2.pptx')
    prs = Presentation(p)
    sl = prs.slides[4]
    if name == 'light_yellow':
        for sh in sl.shapes:
            if sh.has_text_frame:
                for para in sh.text_frame.paragraphs:
                    for r in para.runs: r.font.color.rgb = RGBColor(0xFF, 0xFF, 0x99)
    elif name == 'one_reverted':
        sh = next(s for s in sl.shapes if s.name == 'Google Shape;166;p 1')
        for para in sh.text_frame.paragraphs:
            for r in para.runs: r.font.color.rgb = RGBColor(0, 0, 0)
    elif name == 'other_slide':
        sh = next(s for s in prs.slides[2].shapes if s.has_text_frame and s.text_frame.text.strip())
        for r in sh.text_frame.paragraphs[0].runs: r.font.color.rgb = RGBColor(0xFF, 0xFF, 0x00)
    else: raise KeyError(name)
    prs.save(p)


def m_21760ecb(root, name):
    p = GB.ubuntu(root, '/home/user/Desktop/Ch4 Video Effect.pptx')
    prs = Presentation(p)
    s1 = prs.slides[0]._element
    tr = s1.find(P + 'transition')
    if name == 'wrong_effect':
        for c in list(tr): tr.remove(c)
        etree.SubElement(tr, P + 'fade')
    elif name == 'wrong_slide':
        s1.remove(tr)
        s2 = prs.slides[1]._element
        t2 = etree.Element(P + 'transition'); t2.set('spd', 'med'); etree.SubElement(t2, P + 'dissolve')
        anchor = s2.find(P + 'clrMapOvr')
        (anchor.addnext(t2) if anchor is not None else s2.insert(1, t2))
    else: raise KeyError(name)
    prs.save(p)


def m_d53ff5ee(root, name):
    p = GB.ubuntu(root, '/home/user/Desktop/presentation_instruction_2023_Feb.docx')
    doc = Document(p)
    if name == 'first_letter_upper':
        para = next(pp for pp in doc.paragraphs if len(pp.text) > 3 and pp.text[0].islower() and pp.runs)
        para.runs[0].text = para.runs[0].text[0].upper() + para.runs[0].text[1:]
    elif name == 'table_upper':
        cell = next(c for t in doc.tables for row in t.rows for c in row.cells
                    for pp in c.paragraphs if pp.runs and any(ch.islower() for ch in pp.text))
        for r in cell.paragraphs[0].runs: r.text = r.text.upper()
    elif name == 'paragraph_deleted':
        para = next(pp for pp in doc.paragraphs if len(pp.text.strip()) > 20)
        para._p.getparent().remove(para._p)
    else: raise KeyError(name)
    doc.save(p)


def m_88fe4b2d(root, name):
    p = GB.ubuntu(root, '/home/user/Desktop/CCCH9003_Tutorial_guidelines.docx')
    doc = Document(p)
    if name == 'blank_lines_removed':
        for para in list(doc.paragraphs[:16]):
            if not para.text.strip() and para.text == '': para._p.getparent().remove(para._p)
    elif name == 'word_changed':
        para = next(pp for pp in doc.paragraphs if 'Discussions play' in pp.text)
        for r in para.runs:
            if 'Discussions' in r.text: r.text = r.text.replace('Discussions', 'Discussion', 1); break
        else: raise ValueError('word not in a single run')
    elif name == 'table_changed':
        doc.tables[0].rows[0].cells[0].paragraphs[0].runs[0].text = 'Session'
    else: raise KeyError(name)
    doc.save(p)


def m_936321ce(root, name):
    p = GB.ubuntu(root, '/home/user/Desktop/Graphemes_Sound_Letter_Patterns.docx')
    doc = Document(p)
    if name == 'table_cell_changed':
        doc.tables[0].rows[1].cells[1].paragraphs[0].runs[0].text = 'Grap'
    elif name == 'table_removed':
        t = doc.tables[0]._tbl; t.getparent().remove(t)
    elif name == 'comma_line_restored':
        anchor = doc.paragraphs[0]
        newp = etree.Element(W + 'p'); r = etree.SubElement(newp, W + 'r')
        etree.SubElement(r, W + 't').text = 'Sound-Letter Pattern, Grapheme, Example Grapheme, Example Word'
        anchor._p.addprevious(newp)
    else: raise KeyError(name)
    doc.save(p)


def _page_break_paras(doc):
    return [pp for pp in doc.paragraphs if not pp.text and pp._p.findall('.//' + W + 'br[@' + W + 'type="page"]')]


def m_ecc2413d(root, name):
    p = GB.ubuntu(root, '/home/user/Desktop/Sample_Statutory_Declaration.docx')
    doc = Document(p)
    if name == 'one_break':
        brk = _page_break_paras(doc)
        if not brk: raise ValueError('no break in positive')
        brk[-1]._p.getparent().remove(brk[-1]._p)
    elif name == 'three_breaks':
        brk = _page_break_paras(doc)[-1]._p
        newp = etree.Element(W + 'p'); r = etree.SubElement(newp, W + 'r')
        etree.SubElement(r, W + 'br').set(W + 'type', 'page')
        brk.addnext(newp)
    elif name == 'text_changed':
        para = next(pp for pp in doc.paragraphs if len(pp.text.strip()) > 10 and pp.runs)
        para.runs[0].text = 'Changed declaration text. ' + para.runs[0].text
    else: raise KeyError(name)
    doc.save(p)


def m_4d117223(root, name):
    base = GB.ubuntu(root, '/home/user/testDir')
    if name == 'one_file_755':
        os.chmod(os.path.join(base, 'subDir1', 'file2.txt'), 0o755)
    elif name == 'one_file_600':
        os.chmod(os.path.join(base, 'file1.txt'), 0o600)
    elif name == 'extra_file':
        fp = os.path.join(base, 'new.txt'); open(fp, 'w').close(); os.chmod(fp, 0o644)
    else: raise KeyError(name)


MUTANTS = {
    'a9f325aa': (m_a9f325aa, ['wrong_value', 'lowercase_title', 'source_changed', 'stray_cell', 'header_removed']),
    '42e0a640': (m_42e0a640, ['wrong_sum', 'swapped_columns', 'sheet_renamed', 'source_changed']),
    '1273e544': (m_1273e544, ['wrong_value', 'header_removed', 'source_changed', 'sheet_renamed']),
    '6054afcb': (m_6054afcb, ['unhide_all', 'hide_extra', 'row_deleted']),
    'f23acfd2': (m_f23acfd2, ['bullet_removed', 'text_changed', 'extra_slide']),
    '57667013': (m_57667013, ['light_yellow', 'one_reverted', 'other_slide']),
    '21760ecb': (m_21760ecb, ['wrong_effect', 'wrong_slide']),
    'd53ff5ee': (m_d53ff5ee, ['first_letter_upper', 'table_upper', 'paragraph_deleted']),
    '88fe4b2d': (m_88fe4b2d, ['blank_lines_removed', 'word_changed', 'table_changed']),
    '936321ce': (m_936321ce, ['table_cell_changed', 'table_removed', 'comma_line_restored']),
    'ecc2413d': (m_ecc2413d, ['one_break', 'three_breaks', 'text_changed']),
    '4d117223': (m_4d117223, ['one_file_755', 'one_file_600', 'extra_file']),
}



# Gold decks from OSWorld were saved by Google Slides and rename every shape. The mutants address the start file's
# shape names, so their base is my positive (the same LibreOffice re-save a user would produce). The gold row stays.
POSITIVE_MUT_BASE = {'f23acfd2'}


def build_all(task_fulls):
    """Returns the root list for gate_check.py: gold and positive rows, starts, and mutants of one base each."""
    recs = []
    for full in task_fulls:
        t8 = full[:8]
        start = ensure_start(t8)
        golds = gold_roots(full)
        fn, names = MUTANTS[t8]
        recs.append({'task': full, 'state': 'start', 'kind': 'start', 'root': start, 'start_root': start})
        for label, base in golds:
            recs.append({'task': full, 'state': label, 'kind': 'gold', 'root': base, 'start_root': start})
        if not golds or t8 in POSITIVE_MUT_BASE:
            pos = GB.build_positive(t8)
            recs.append({'task': full, 'state': 'positive', 'kind': 'positive', 'root': pos, 'start_root': start})
            mut_base, mut_label = pos, 'positive'
        else:
            mut_base, mut_label = golds[0][1], golds[0][0]
        for n in names:
            mroot = copy_base(mut_base, t8, n)
            fn(mroot, n)
            recs.append({'task': full, 'state': 'mut_' + n, 'kind': 'mutant', 'base': mut_label,
                         'root': mroot, 'start_root': start})
    return recs


if __name__ == '__main__':
    import yaml
    specs = {}
    for f in sorted(glob.glob(os.path.join(HERE, '..', 'exp5-grounded', 'specs', 'batch_*.yaml'))):
        d = yaml.safe_load(open(f))
        for t in (d if isinstance(d, list) else d.get('tasks', d)):
            specs[str(t['id'])[:8]] = str(t['id'])
    fulls = [specs[t8] for t8 in MUTANTS]
    recs = build_all(fulls)
    out = os.path.join(GB.GATE, 'roots_mutants.json')
    json.dump(recs, open(out, 'w'), indent=1)
    print('wrote', len(recs), 'roots to', out)
