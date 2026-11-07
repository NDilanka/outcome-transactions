"""End states for task 66399b0d-8fda-4618-95c4-bfc6191617e9.

The request asks for an empty 7 column by 5 row table inserted at the cursor,
which sits at the end of the instruction text.
"""

import copy
import shutil
import os

import docx
from docx.oxml.ns import qn
from docx.shared import Twips
from lxml import etree

from statekit import copy_snapshot, write_odt

SRC = ("home", "user", "Desktop", "Table_Of_Work_Effort_Instructions.docx")
ROWS, COLS = 5, 7


def _path(out_dir, name="Table_Of_Work_Effort_Instructions.docx"):
    return os.path.join(out_dir, *SRC[:-1], name)


def _open(out_dir, name="Table_Of_Work_Effort_Instructions.docx"):
    return docx.Document(_path(out_dir, name))


def _save(document, out_dir, name="Table_Of_Work_Effort_Instructions.docx"):
    document.save(_path(out_dir, name))


def _borders(table):
    tblPr = table._tbl.tblPr
    borders = etree.SubElement(tblPr, "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = etree.SubElement(
            borders, "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}%s" % edge)
        element.set("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val", "single")
        element.set("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz", "4")


def _fill(table, text):
    for row in table.rows:
        for cell in row.cells:
            cell.text = text


def _paragraphs(document):
    return document.paragraphs


# --- correct states ---------------------------------------------------------

def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table = document.add_table(rows=ROWS, cols=COLS)
    document.add_paragraph("")
    _save(document, out_dir)


def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table = document.add_table(rows=ROWS, cols=COLS)
    _borders(table)
    document.add_paragraph("")
    _save(document, out_dir)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table = document.add_table(rows=ROWS, cols=COLS)
    table.autofit = False
    for column in table.columns:
        column.width = Twips(1440)
    document.add_paragraph("")
    _save(document, out_dir)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table = document.add_table(rows=ROWS, cols=COLS)
    last = document.paragraphs[-1]._p
    last.addprevious(table._tbl)
    _save(document, out_dir)


# --- wrong states -----------------------------------------------------------

def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    document.add_table(rows=COLS, cols=ROWS)
    _save(document, out_dir)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table = document.add_table(rows=ROWS, cols=COLS)
    document.paragraphs[0]._p.addprevious(table._tbl)
    _save(document, out_dir)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table = document.add_table(rows=ROWS, cols=COLS)
    document.paragraphs[8]._p.addnext(table._tbl)
    _save(document, out_dir)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table = document.add_table(rows=ROWS, cols=COLS)
    for row in table.rows:
        for index, cell in enumerate(row.cells):
            cell.text = "Column %d" % (index + 1)
    _save(document, out_dir)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    existing = document.tables[0]._tbl
    existing.getparent().remove(existing)
    document.add_table(rows=ROWS, cols=COLS)
    _save(document, out_dir)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for _row in range(ROWS):
        document.add_paragraph(", ".join([""] * COLS))
    _save(document, out_dir)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    other = docx.Document()
    other.add_table(rows=ROWS, cols=COLS)
    other.save(os.path.join(out_dir, *SRC[:-1], "Table.docx"))


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    document.add_table(rows=ROWS, cols=COLS - 1)
    _save(document, out_dir)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    document.add_table(rows=ROWS - 1, cols=COLS)
    _save(document, out_dir)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    document.add_table(rows=ROWS, cols=COLS)
    lines = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            lines.append(" | ".join(cell.text for cell in row.cells))
    write_odt(os.path.join(out_dir, *SRC[:-1], "Table_Of_Work_Effort_Instructions.odt"), lines)
    shutil.copyfile(os.path.join(snapshot_dir, *SRC), _path(out_dir))


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    name = "Table_Of_Work_Effort_Instructions copy.docx"
    document = _open(out_dir)
    document.add_table(rows=ROWS, cols=COLS)
    _save(document, out_dir, name=name)


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    document.add_table(rows=ROWS, cols=COLS)
    for paragraph in document.paragraphs[11:17]:
        paragraph._p.getparent().remove(paragraph._p)
    _save(document, out_dir)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table = document.add_table(rows=ROWS, cols=1)
    grid = table._tbl.tblGrid
    while len(grid.findall(qn("w:gridCol"))) < COLS:
        etree.SubElement(grid, qn("w:gridCol"))
    for row in table.rows:
        tcPr = row.cells[0]._tc.get_or_add_tcPr()
        span = etree.SubElement(tcPr, qn("w:gridSpan"))
        span.set(qn("w:val"), str(COLS))
    _save(document, out_dir)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table = document.add_table(rows=ROWS, cols=COLS)
    cell = document.tables[0].rows[7].cells[0]
    cell._tc.insert(0, copy.deepcopy(table._tbl))
    table._tbl.getparent().remove(table._tbl)
    _save(document, out_dir)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table = document.add_table(rows=ROWS + 1, cols=COLS)
    header = document.tables[0].rows[1]
    for index, cell in enumerate(table.rows[0].cells):
        cell.text = header.cells[index].text
    _save(document, out_dir)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    document.add_table(rows=ROWS, cols=COLS)
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            run.font.name = "Arial"
    _save(document, out_dir)


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    section = document.sections[0]
    section.header.add_table(rows=ROWS, cols=COLS, width=section.page_width)
    _save(document, out_dir)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    document.add_table(rows=ROWS, cols=COLS)
    for row in document.tables[0].rows:
        for cell in row.cells:
            cell.text = ""
    _save(document, out_dir)
