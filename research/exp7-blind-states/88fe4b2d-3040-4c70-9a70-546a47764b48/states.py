"""End states for task 88fe4b2d-3040-4c70-9a70-546a47764b48.

The first paragraph of the guideline document holds seven sentences. The
request is to separate each sentence with one empty line.
"""

import copy
import os
import re
import shutil

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from statekit import copy_snapshot, write_odt

SRC = ("home", "user", "Desktop", "CCCH9003_Tutorial_guidelines.docx")
SPLIT = re.compile(r"(?<=[.!?])\s+")


def _path(out_dir, name="CCCH9003_Tutorial_guidelines.docx"):
    return os.path.join(out_dir, *SRC[:-1], name)


def _open(out_dir, name="CCCH9003_Tutorial_guidelines.docx"):
    return docx.Document(_path(out_dir, name))


def _save(document, out_dir, name="CCCH9003_Tutorial_guidelines.docx"):
    document.save(_path(out_dir, name))


def _text(paragraph_element):
    return "".join(node.text or "" for node in paragraph_element.iter(qn("w:t")))


def _sentences(text):
    return [sentence for sentence in SPLIT.split(text.strip()) if sentence]


def _runs(paragraph_element):
    return paragraph_element.findall(qn("w:r"))


def _sentence_paragraph(template, text):
    paragraph = copy.deepcopy(template)
    for run in _runs(paragraph):
        paragraph.remove(run)
    runs = _runs(template)
    if runs:
        run = copy.deepcopy(runs[0])
        for node in run.findall(qn("w:t")):
            run.remove(node)
        node = OxmlElement("w:t")
        node.set(qn("xml:space"), "preserve")
        node.text = text
        run.append(node)
        paragraph.append(run)
    return paragraph


def _empty_paragraph(template):
    paragraph = copy.deepcopy(template)
    for run in _runs(paragraph):
        paragraph.remove(run)
    return paragraph


def _plain_paragraph(text=""):
    paragraph = OxmlElement("w:p")
    if text:
        run = OxmlElement("w:r")
        node = OxmlElement("w:t")
        node.set(qn("xml:space"), "preserve")
        node.text = text
        run.append(node)
        paragraph.append(run)
    return paragraph


def _replace_with_sequence(paragraph_element, elements):
    if not elements:
        return []
    parent = paragraph_element.getparent()
    for element in elements:
        paragraph_element.addprevious(element)
    parent.remove(paragraph_element)
    return elements


# --- correct states ---------------------------------------------------------

def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    following = first.getnext()
    pieces = []
    for sentence in _sentences(_text(first)):
        pieces.append(_sentence_paragraph(first, sentence))
        pieces.append(_empty_paragraph(first))
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    if following is not None and not _text(following).strip():
        following.getparent().remove(following)
    _save(document, out_dir)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    sentences = _sentences(_text(first))
    pieces = []
    for index, sentence in enumerate(sentences):
        pieces.append(_sentence_paragraph(first, sentence))
        if index < len(sentences) - 1:
            pieces.append(_empty_paragraph(first))
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    _save(document, out_dir)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    following = first.getnext()
    pieces = []
    for sentence in _sentences(_text(first)):
        pieces.append(_sentence_paragraph(first, sentence))
        pieces.append(_plain_paragraph())
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    if following is not None and not _text(following).strip():
        following.getparent().remove(following)
    _save(document, out_dir)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    sentences = _sentences(_text(first))
    pieces = []
    for index, sentence in enumerate(sentences):
        pieces.append(_sentence_paragraph(first, sentence))
        if index < len(sentences) - 1:
            pieces.append(_plain_paragraph())
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    _save(document, out_dir)


# --- wrong states -----------------------------------------------------------

def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    sentences = _sentences(_text(first))
    runs = _runs(first)
    for run in runs[1:]:
        first.remove(run)
    run = runs[0]
    for node in run.findall(qn("w:t")):
        run.remove(node)
    for index, sentence in enumerate(sentences):
        node = OxmlElement("w:t")
        node.set(qn("xml:space"), "preserve")
        node.text = sentence + (" " if index < len(sentences) - 1 else "")
        run.append(node)
        if index < len(sentences) - 1:
            run.append(OxmlElement("w:br"))
    _save(document, out_dir)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    sentences = _sentences(_text(first))
    pieces = []
    for index, sentence in enumerate(sentences):
        if index < 2:
            pieces.append(_sentence_paragraph(first, sentence))
            pieces.append(_empty_paragraph(first))
        elif index == 2:
            pieces.append(_sentence_paragraph(first, " ".join(sentences[index:])))
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    _save(document, out_dir)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    anchor = first
    for _index in range(7):
        element = _empty_paragraph(first)
        anchor.addnext(element)
        anchor = element
    _save(document, out_dir)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for paragraph in list(document.paragraphs):
        element = paragraph._p
        sentences = _sentences(_text(element))
        if len(sentences) < 2:
            continue
        pieces = []
        for index, sentence in enumerate(sentences):
            pieces.append(_sentence_paragraph(element, sentence))
            if index < len(sentences) - 1:
                pieces.append(_empty_paragraph(element))
        for run in _runs(element):
            element.remove(run)
        _replace_with_sequence(element, pieces)
    _save(document, out_dir)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    text = _text(first)
    pieces_text = [piece for piece in re.split(r"(?<=[.!?,])\s+", text.strip()) if piece]
    pieces = []
    for index, sentence in enumerate(pieces_text):
        pieces.append(_sentence_paragraph(first, sentence))
        if index < len(pieces_text) - 1:
            pieces.append(_empty_paragraph(first))
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    _save(document, out_dir)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    sentences = []
    for sentence in _sentences(_text(first)):
        sentences.extend([sentence, sentence])
    pieces = []
    for index, sentence in enumerate(sentences):
        pieces.append(_sentence_paragraph(first, sentence))
        if index < len(sentences) - 1:
            pieces.append(_empty_paragraph(first))
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    _save(document, out_dir)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    sentences = _sentences(_text(first))
    del sentences[3]
    pieces = []
    for index, sentence in enumerate(sentences):
        pieces.append(_sentence_paragraph(first, sentence))
        if index < len(sentences) - 1:
            pieces.append(_empty_paragraph(first))
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    _save(document, out_dir)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    sentences = _sentences(_text(first))
    pieces = []
    for index, sentence in enumerate(sentences):
        pieces.append(_sentence_paragraph(first, sentence))
        if index < len(sentences) - 1:
            pieces.append(_empty_paragraph(first))
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    lines = [paragraph.text for paragraph in document.paragraphs]
    write_odt(os.path.join(out_dir, *SRC[:-1], "CCCH9003_Tutorial_guidelines.odt"), lines)
    shutil.copyfile(os.path.join(snapshot_dir, *SRC), _path(out_dir))


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    name = "CCCH9003_Tutorial_guidelines copy.docx"
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    sentences = _sentences(_text(first))
    pieces = []
    for index, sentence in enumerate(sentences):
        pieces.append(_sentence_paragraph(first, sentence))
        if index < len(sentences) - 1:
            pieces.append(_empty_paragraph(first))
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    _save(document, out_dir, name=name)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    body = document.element.body
    elements = list(body.iterchildren())
    started = False
    for element in elements:
        if element is first:
            started = True
            continue
        if started and etree.QName(element).localname != "sectPr":
            body.remove(element)
    sentences = _sentences(_text(first))
    pieces = []
    for index, sentence in enumerate(sentences):
        pieces.append(_sentence_paragraph(first, sentence))
        if index < len(sentences) - 1:
            pieces.append(_empty_paragraph(first))
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    _save(document, out_dir)


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    sentences = _sentences(_text(first))
    pieces = []
    for sentence in sentences:
        piece = _sentence_paragraph(first, sentence)
        pPr = piece.find(qn("w:pPr"))
        if pPr is None:
            pPr = etree.SubElement(piece, qn("w:pPr"))
            piece.remove(pPr)
            piece.insert(0, pPr)
        spacing = pPr.find(qn("w:spacing"))
        if spacing is None:
            spacing = etree.SubElement(pPr, qn("w:spacing"))
        spacing.set(qn("w:after"), "240")
        spacing.set(qn("w:line"), "259")
        spacing.set(qn("w:lineRule"), "auto")
        pieces.append(piece)
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    _save(document, out_dir)


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    pieces = [_empty_paragraph(first) for _index in range(7)]
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    _save(document, out_dir)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    sentences = _sentences(_text(first))
    pieces = []
    for index, sentence in enumerate(sentences):
        pieces.append(_sentence_paragraph(first, sentence))
        if index < len(sentences) - 1:
            pieces.append(_empty_paragraph(first))
            pieces.append(_empty_paragraph(first))
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    _save(document, out_dir)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    sentences = _sentences(_text(first))
    pieces = []
    for index, sentence in enumerate(sentences):
        pieces.append(_sentence_paragraph(first, sentence))
        if index < len(sentences) - 1:
            pieces.append(_empty_paragraph(first))
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            run.font.name = "Times New Roman"
    _save(document, out_dir)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    sentences = _sentences(_text(first))
    table = document.add_table(rows=len(sentences), cols=1)
    for row, sentence in zip(table.rows, sentences):
        row.cells[0].text = sentence
    first.addprevious(table._tbl)
    first.getparent().remove(first)
    _save(document, out_dir)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    sentences = _sentences(_text(first))
    pieces = []
    for sentence in sentences:
        pieces.append(_empty_paragraph(first))
        pieces.append(_sentence_paragraph(first, sentence))
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    _save(document, out_dir)


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    target = document.paragraphs[3]._p
    sentences = _sentences(_text(target))
    pieces = []
    for index, sentence in enumerate(sentences):
        pieces.append(_sentence_paragraph(target, sentence))
        if index < len(sentences) - 1:
            pieces.append(_empty_paragraph(target))
    for run in _runs(target):
        target.remove(run)
    _replace_with_sequence(target, pieces)
    _save(document, out_dir)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    first = document.paragraphs[0]._p
    sentences = _sentences(_text(first))
    pieces = [_sentence_paragraph(first, " ".join(sentences[:4]))]
    pieces.append(_empty_paragraph(first))
    for sentence in sentences[4:]:
        pieces.append(_sentence_paragraph(first, sentence))
        pieces.append(_empty_paragraph(first))
    for run in _runs(first):
        first.remove(run)
    _replace_with_sequence(first, pieces)
    _save(document, out_dir)
