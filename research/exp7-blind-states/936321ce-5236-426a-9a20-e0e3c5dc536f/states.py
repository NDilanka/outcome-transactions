"""End states for task 936321ce-5236-426a-9a20-e0e3c5dc536f.

Paragraphs 4 to 8 of the document are five rows of comma separated text; the
request is to convert that text into a table.
"""

import copy
import os
import shutil

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Twips

from statekit import copy_snapshot, write_odt

SRC = ("home", "user", "Desktop", "Graphemes_Sound_Letter_Patterns.docx")
FIRST, LAST = 4, 8


def _path(out_dir, name="Graphemes_Sound_Letter_Patterns.docx"):
    return os.path.join(out_dir, *SRC[:-1], name)


def _open(out_dir, name="Graphemes_Sound_Letter_Patterns.docx"):
    return docx.Document(_path(out_dir, name))


def _save(document, out_dir, name="Graphemes_Sound_Letter_Patterns.docx"):
    document.save(_path(out_dir, name))


def _rows(document):
    return [document.paragraphs[index].text for index in range(FIRST, LAST + 1)]


def _borders(table):
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement("w:%s" % edge)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        borders.append(element)
    table._tbl.tblPr.append(borders)


def _drop(document, first, last):
    for _index in range(first, last + 1):
        paragraph = document.paragraphs[first]._p
        paragraph.getparent().remove(paragraph)


def _drop_source(document):
    _drop(document, FIRST, LAST)


def _cells(rows, trim=True, width=None):
    table_rows = []
    for row in rows:
        parts = row.split(",")
        if trim:
            parts = [part.replace("\xa0", "").strip() for part in parts]
        table_rows.append(parts)
    if width:
        table_rows = [row + [""] * (width - len(row)) for row in table_rows]
    return table_rows


def _build(document, rows, trim=True, width=None, header_bold=False, borders=False, keep_nbsp=False):
    table_rows = _cells(rows, trim=trim, width=width)
    table = document.add_table(rows=len(table_rows), cols=max(len(row) for row in table_rows))
    for row_index, row in enumerate(table_rows):
        for column_index, value in enumerate(row):
            if keep_nbsp:
                value = rows[row_index].split(",")[column_index] if column_index < len(rows[row_index].split(",")) else ""
            table.rows[row_index].cells[column_index].text = value
    if header_bold:
        for cell in table.rows[0].cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = True
    if borders:
        _borders(table)
    document.paragraphs[FIRST]._p.addprevious(table._tbl)
    return table


# --- correct states ---------------------------------------------------------

def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    _build(document, _rows(document))
    _drop_source(document)
    _save(document, out_dir)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    _build(document, _rows(document), header_bold=True)
    _drop_source(document)
    _save(document, out_dir)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    _build(document, _rows(document), borders=True)
    _drop_source(document)
    _save(document, out_dir)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table = _build(document, _rows(document), header_bold=True, borders=True, keep_nbsp=True)
    for column in table.columns:
        column.width = Twips(1800)
    _drop_source(document)
    _save(document, out_dir)


# --- wrong states -----------------------------------------------------------

def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    _build(document, _rows(document)[:1])
    _drop(document, FIRST, FIRST)
    _save(document, out_dir)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    rows = _rows(document)
    table_rows = _cells(rows[1:])
    table = document.add_table(rows=len(table_rows), cols=4)
    for row_index, row in enumerate(table_rows):
        for column_index, value in enumerate(row):
            table.rows[row_index].cells[column_index].text = value
    document.paragraphs[FIRST + 1]._p.addprevious(table._tbl)
    _drop(document, FIRST + 1, LAST)
    _save(document, out_dir)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table_rows = _cells(_rows(document))
    table = document.add_table(rows=4, cols=5)
    for row_index, row in enumerate(table_rows):
        for column_index, value in enumerate(row):
            table.rows[column_index].cells[row_index].text = value
    document.paragraphs[FIRST]._p.addprevious(table._tbl)
    _drop_source(document)
    _save(document, out_dir)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    rows = _rows(document)
    table = document.add_table(rows=len(rows), cols=1)
    for row_index, row in enumerate(rows):
        table.rows[row_index].cells[0].text = row.replace("\xa0", "").strip()
    document.paragraphs[FIRST]._p.addprevious(table._tbl)
    _drop_source(document)
    _save(document, out_dir)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    split_rows = [[token.replace("\xa0", "") for token in row.split() if token] for row in _rows(document)]
    table = document.add_table(rows=len(split_rows), cols=max(len(row) for row in split_rows))
    for row_index, row in enumerate(split_rows):
        for column_index, value in enumerate(row):
            table.rows[row_index].cells[column_index].text = value
    document.paragraphs[FIRST]._p.addprevious(table._tbl)
    _drop_source(document)
    _save(document, out_dir)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    _build(document, _rows(document)[:4])
    _drop(document, FIRST, LAST - 1)
    _save(document, out_dir)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for paragraph in list(document.paragraphs):
        if len(paragraph.text.split(",")) < 2:
            continue
        values = [value.replace("\xa0", "").strip() for value in paragraph.text.split(",")]
        table = document.add_table(rows=1, cols=len(values))
        for column_index, value in enumerate(values):
            table.rows[0].cells[column_index].text = value
        paragraph._p.addprevious(table._tbl)
        paragraph._p.getparent().remove(paragraph._p)
    _save(document, out_dir)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table_rows = _cells(_rows(document))
    table = document.add_table(rows=len(table_rows), cols=4)
    for row_index, row in enumerate(table_rows):
        for column_index, value in enumerate(row):
            table.rows[row_index].cells[column_index].text = value
    _save(document, out_dir)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    _build(document, _rows(document), width=5)
    _drop_source(document)
    _save(document, out_dir)


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    rows = _rows(document)
    table = document.add_table(rows=len(rows), cols=4)
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row.split("\t")):
            table.rows[row_index].cells[column_index].text = value.replace("\xa0", "").strip()
    document.paragraphs[FIRST]._p.addprevious(table._tbl)
    _drop_source(document)
    _save(document, out_dir)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    _build(document, _rows(document))
    _drop_source(document)
    lines = [paragraph.text for paragraph in document.paragraphs]
    write_odt(os.path.join(out_dir, *SRC[:-1], "Graphemes_Sound_Letter_Patterns.odt"), lines)
    shutil.copyfile(os.path.join(snapshot_dir, *SRC), _path(out_dir))


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    name = "Graphemes_Sound_Letter_Patterns copy.docx"
    document = _open(out_dir)
    _build(document, _rows(document))
    _drop_source(document)
    _save(document, out_dir, name=name)


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table = _build(document, _rows(document))
    _drop_source(document)
    body = document.element.body
    started = False
    for element in list(body.iterchildren()):
        if element is table._tbl:
            started = True
            continue
        if started and element.tag != qn("w:sectPr"):
            body.remove(element)
    _save(document, out_dir)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    rows = _rows(_open(out_dir))
    other = docx.Document()
    table_rows = _cells(rows)
    table = other.add_table(rows=len(table_rows), cols=4)
    for row_index, row in enumerate(table_rows):
        for column_index, value in enumerate(row):
            table.rows[row_index].cells[column_index].text = value
    other.save(os.path.join(out_dir, *SRC[:-1], "Graphemes_table.docx"))


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table_rows = _cells(_rows(document))
    table = document.add_table(rows=len(table_rows), cols=3)
    for row_index, row in enumerate(table_rows):
        for column_index, value in enumerate(row[:3]):
            table.rows[row_index].cells[column_index].text = value
    document.paragraphs[FIRST]._p.addprevious(table._tbl)
    _drop_source(document)
    _save(document, out_dir)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table_rows = _cells(list(reversed(_rows(document))))
    table = document.add_table(rows=len(table_rows), cols=4)
    for row_index, row in enumerate(table_rows):
        for column_index, value in enumerate(row):
            table.rows[row_index].cells[column_index].text = value
    document.paragraphs[FIRST]._p.addprevious(table._tbl)
    _drop_source(document)
    _save(document, out_dir)


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table = _build(document, _rows(document))
    saved = document.tables[0]._tbl
    saved.addprevious(copy.deepcopy(table._tbl))
    _drop_source(document)
    _save(document, out_dir)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    table_rows = _cells(_rows(document))
    table = document.add_table(rows=len(table_rows), cols=4)
    for row_index, row in enumerate(table_rows):
        for column_index, value in enumerate(row):
            table.rows[row_index].cells[column_index].text = value
    body = document.element.body
    for element in list(body.iterchildren()):
        if element.tag == qn("w:sectPr"):
            continue
        body.remove(element)
    body.insert(0, table._tbl)
    _save(document, out_dir)
