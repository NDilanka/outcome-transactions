"""End states for task ecc2413d-8a48-416e-a3a2-d30106ca36cb.

The declaration opens with a cover page (paragraphs 0 to 4) and paragraph 5
already starts with a page break, so it opens on page 2. A blank page after
the cover page needs a break that lands an empty paragraph on page 2.
"""

import copy
import os
import shutil

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from statekit import copy_snapshot, write_odt

SRC = ("home", "user", "Desktop", "Sample_Statutory_Declaration.docx")
SECOND_PAGE = 5


def _path(out_dir, name="Sample_Statutory_Declaration.docx"):
    return os.path.join(out_dir, *SRC[:-1], name)


def _open(out_dir, name="Sample_Statutory_Declaration.docx"):
    return docx.Document(_path(out_dir, name))


def _save(document, out_dir, name="Sample_Statutory_Declaration.docx"):
    document.save(_path(out_dir, name))


def _paragraphs(document):
    return [paragraph._p for paragraph in document.paragraphs]


def _pPr(paragraph):
    pPr = paragraph.find(qn("w:pPr"))
    if pPr is None:
        pPr = OxmlElement("w:pPr")
        paragraph.insert(0, pPr)
    return pPr


def _empty_like(template):
    paragraph = copy.deepcopy(template)
    for run in paragraph.findall(qn("w:r")):
        paragraph.remove(run)
    for node in paragraph.findall(qn("w:t")):
        paragraph.remove(node)
    return paragraph


def _break_before(paragraph):
    pPr = _pPr(paragraph)
    for node in pPr.findall(qn("w:pageBreakBefore")):
        pPr.remove(node)
    node = OxmlElement("w:pageBreakBefore")
    index = 1 if pPr.find(qn("w:pStyle")) is not None else 0
    for position, child in enumerate(pPr):
        if child.tag in (qn("w:keepNext"), qn("w:keepLines")):
            index = position + 1
    pPr.insert(index, node)
    return paragraph


def _break_run():
    run = OxmlElement("w:r")
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "page")
    run.append(br)
    return run


def _insert_before(anchor, elements):
    for element in elements:
        anchor.addprevious(element)
    return elements


def _blank_paragraph(template, text=""):
    paragraph = _empty_like(template)
    if text:
        run = OxmlElement("w:r")
        node = OxmlElement("w:t")
        node.set(qn("xml:space"), "preserve")
        node.text = text
        run.append(node)
        paragraph.append(run)
    return paragraph


def _find(document, prefix):
    for paragraph in document.paragraphs:
        if paragraph.text.strip().startswith(prefix):
            return paragraph._p
    raise LookupError(prefix)


# --- correct states ---------------------------------------------------------

def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    _insert_before(paragraphs[SECOND_PAGE], [blank])
    _save(document, out_dir)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    first = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    second = _empty_like(paragraphs[SECOND_PAGE])
    _insert_before(paragraphs[SECOND_PAGE], [first, second])
    _save(document, out_dir)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    paragraphs[SECOND_PAGE - 1].append(_break_run())
    blank = _empty_like(paragraphs[SECOND_PAGE])
    _insert_before(paragraphs[SECOND_PAGE], [blank])
    _save(document, out_dir)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    target = paragraphs[SECOND_PAGE]
    blank = _break_before(_empty_like(target))
    for run in target.findall(qn("w:r")):
        if run.find(qn("w:br")) is not None:
            target.remove(run)
    blank.append(_break_run())
    _insert_before(target, [blank])
    _save(document, out_dir)


# --- wrong states -----------------------------------------------------------

def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    paragraphs[-1].addnext(blank)
    _save(document, out_dir)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    _insert_before(_find(document, "EXHIBIT"), [blank])
    _save(document, out_dir)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    first = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    second = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    _insert_before(paragraphs[SECOND_PAGE], [first, second])
    _save(document, out_dir)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _empty_like(paragraphs[SECOND_PAGE])
    _insert_before(paragraphs[SECOND_PAGE], [blank])
    _save(document, out_dir)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    pPr = _pPr(paragraphs[SECOND_PAGE - 1])
    spacing = pPr.find(qn("w:spacing"))
    if spacing is None:
        spacing = OxmlElement("w:spacing")
        pPr.append(spacing)
    spacing.set(qn("w:after"), "720")
    _save(document, out_dir)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    _insert_before(paragraphs[0], [blank])
    _save(document, out_dir)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    _insert_before(paragraphs[15], [blank])
    _save(document, out_dir)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    target = paragraphs[SECOND_PAGE]
    blank = _break_before(_empty_like(target))
    for run in target.findall(qn("w:r")):
        if run.find(qn("w:br")) is not None:
            target.remove(run)
    _insert_before(target, [blank])
    _save(document, out_dir)


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _break_before(_blank_paragraph(paragraphs[SECOND_PAGE], "This page intentionally left blank"))
    _insert_before(paragraphs[SECOND_PAGE], [blank])
    _save(document, out_dir)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    name = "Sample_Statutory_Declaration copy.docx"
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    _insert_before(paragraphs[SECOND_PAGE], [blank])
    _save(document, out_dir, name=name)


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    _insert_before(paragraphs[SECOND_PAGE], [blank])
    lines = [paragraph.text for paragraph in document.paragraphs]
    write_odt(os.path.join(out_dir, *SRC[:-1], "Sample_Statutory_Declaration.odt"), lines)
    shutil.copyfile(os.path.join(snapshot_dir, *SRC), _path(out_dir))


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    _insert_before(paragraphs[SECOND_PAGE], [blank])
    for element in paragraphs[:SECOND_PAGE]:
        element.getparent().remove(element)
    _save(document, out_dir)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    _insert_before(paragraphs[10], [blank])
    _save(document, out_dir)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    runs = paragraphs[SECOND_PAGE - 1].findall(qn("w:r"))
    if runs:
        runs[0].addnext(_break_run())
    _save(document, out_dir)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    _insert_before(paragraphs[SECOND_PAGE], [blank])
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            run.font.size = docx.shared.Pt(10)
    _save(document, out_dir)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    _insert_before(paragraphs[47], [blank])
    _save(document, out_dir)


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    _insert_before(paragraphs[SECOND_PAGE], [blank])
    anchor = _find(document, "EXHIBIT ‘C’")
    started = False
    for element in list(document.element.body.iterchildren()):
        if element is anchor:
            started = True
        if started and element.tag != qn("w:sectPr"):
            element.getparent().remove(element)
    _save(document, out_dir)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraphs = _paragraphs(document)
    blank = _break_before(_empty_like(paragraphs[SECOND_PAGE]))
    _insert_before(paragraphs[SECOND_PAGE], [blank])
    for table in list(document.tables):
        table._tbl.getparent().remove(table._tbl)
    _save(document, out_dir)
