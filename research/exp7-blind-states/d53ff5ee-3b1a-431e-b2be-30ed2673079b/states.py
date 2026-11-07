"""End states for task d53ff5ee-3b1a-431e-b2be-30ed2673079b.

Two places in the document carry all-capital text: the course code on
paragraph 1 and the instruction paragraph 7.
"""

import os
import re
import shutil

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from statekit import copy_snapshot, write_odt

SRC = ("home", "user", "Desktop", "presentation_instruction_2023_Feb.docx")
CAPS_PARAGRAPH = 7
CODE_PARAGRAPH = 1


def _path(out_dir, name="presentation_instruction_2023_Feb.docx"):
    return os.path.join(out_dir, *SRC[:-1], name)


def _open(out_dir, name="presentation_instruction_2023_Feb.docx"):
    return docx.Document(_path(out_dir, name))


def _save(document, out_dir, name="presentation_instruction_2023_Feb.docx"):
    document.save(_path(out_dir, name))


def _is_caps(text):
    letters = [character for character in text if character.isalpha()]
    return bool(letters) and all(character.isupper() for character in letters)


def _runs(paragraph):
    return paragraph.findall(qn("w:r"))


def _run_text(run):
    return "".join(node.text or "" for node in run.findall(qn("w:t")))


def _set_text(run, text, keep_breaks=True):
    nodes = run.findall(qn("w:t"))
    for node in nodes[1:]:
        run.remove(node)
    breaks = run.findall(qn("w:br")) if keep_breaks else []
    if not nodes:
        node = OxmlElement("w:t")
        node.set(qn("xml:space"), "preserve")
        run.append(node)
        nodes = [node]
    nodes[0].text = text
    nodes[0].set(qn("xml:space"), "preserve")


def _paragraphs(document):
    return [paragraph._p for paragraph in document.paragraphs]


def _lower_run(run):
    _set_text(run, _run_text(run).lower())


# --- correct states ---------------------------------------------------------

def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for index in (CODE_PARAGRAPH, CAPS_PARAGRAPH):
        for run in _runs(document.paragraphs[index]._p):
            if _is_caps(_run_text(run)):
                _lower_run(run)
    _save(document, out_dir)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for index in (CODE_PARAGRAPH, CAPS_PARAGRAPH):
        for run in _runs(document.paragraphs[index]._p):
            if not _is_caps(_run_text(run)):
                continue
            _lower_run(run)
            rPr = run.find(qn("w:rPr"))
            if rPr is None:
                rPr = OxmlElement("w:rPr")
                run.insert(0, rPr)
            caps = OxmlElement("w:caps")
            caps.set(qn("w:val"), "0")
            rPr.append(caps)
    _save(document, out_dir)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for index in (CODE_PARAGRAPH, CAPS_PARAGRAPH):
        for run in _runs(document.paragraphs[index]._p):
            text = _run_text(run)
            if not _is_caps(text):
                continue
            rPr = run.find(qn("w:rPr"))
            pieces = text.split(" ")
            _set_text(run, pieces[0].lower())
            anchor = run
            for piece in pieces[1:]:
                fresh = OxmlElement("w:r")
                if rPr is not None:
                    fresh.append(_copy(rPr))
                node = OxmlElement("w:t")
                node.set(qn("xml:space"), "preserve")
                node.text = " " + piece.lower()
                fresh.append(node)
                anchor.addnext(fresh)
                anchor = fresh
    _save(document, out_dir)


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for index in (CODE_PARAGRAPH, CAPS_PARAGRAPH):
        for run in _runs(document.paragraphs[index]._p):
            if _is_caps(_run_text(run)):
                _lower_run(run)
    for paragraph in document.paragraphs:
        for run in _runs(paragraph._p):
            if not _run_text(run).strip():
                paragraph._p.remove(run)
    _save(document, out_dir)


# --- wrong states -----------------------------------------------------------

def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for run in _runs(document.paragraphs[CAPS_PARAGRAPH]._p):
        if _is_caps(_run_text(run)):
            _lower_run(run)
    _save(document, out_dir)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for paragraph in document.paragraphs:
        for run in _runs(paragraph._p):
            text = _run_text(run)
            if text:
                _set_text(run, text.lower())
    _save(document, out_dir)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for run in _runs(document.paragraphs[CAPS_PARAGRAPH]._p):
        text = _run_text(run)
        if _is_caps(text):
            _set_text(run, text[:10].lower())
    _save(document, out_dir)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for index in (CODE_PARAGRAPH, CAPS_PARAGRAPH):
        for run in _runs(document.paragraphs[index]._p):
            text = _run_text(run)
            if _is_caps(text):
                _set_text(run, text.title())
    _save(document, out_dir)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraph = document.paragraphs[CAPS_PARAGRAPH]._p
    paragraph.getparent().remove(paragraph)
    _save(document, out_dir)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for index in (CODE_PARAGRAPH, CAPS_PARAGRAPH):
        for run in _runs(document.paragraphs[index]._p):
            if _is_caps(_run_text(run)):
                _lower_run(run)
    for index in (CODE_PARAGRAPH, CAPS_PARAGRAPH):
        pPr = document.paragraphs[index]._p.find(qn("w:pPr"))
        if pPr is not None:
            for node in pPr.findall(qn("w:jc")):
                pPr.remove(node)
            jc = OxmlElement("w:jc")
            jc.set(qn("w:val"), "left")
            pPr.append(jc)
    _save(document, out_dir)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    name = "presentation_instruction_2023_Feb copy.docx"
    document = _open(out_dir)
    for index in (CODE_PARAGRAPH, CAPS_PARAGRAPH):
        for run in _runs(document.paragraphs[index]._p):
            if _is_caps(_run_text(run)):
                _lower_run(run)
    _save(document, out_dir, name=name)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for index in (CODE_PARAGRAPH, CAPS_PARAGRAPH):
        for run in _runs(document.paragraphs[index]._p):
            if _is_caps(_run_text(run)):
                _lower_run(run)
    lines = [paragraph.text for paragraph in document.paragraphs]
    write_odt(os.path.join(out_dir, *SRC[:-1], "presentation_instruction_2023_Feb.odt"), lines)
    shutil.copyfile(os.path.join(snapshot_dir, *SRC), _path(out_dir))


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for index in (CODE_PARAGRAPH, CAPS_PARAGRAPH):
        for run in _runs(document.paragraphs[index]._p):
            if not _is_caps(_run_text(run)):
                continue
            _lower_run(run)
            rPr = run.find(qn("w:rPr"))
            if rPr is None:
                rPr = OxmlElement("w:rPr")
                run.insert(0, rPr)
            caps = OxmlElement("w:caps")
            caps.set(qn("w:val"), "1")
            rPr.append(caps)
    _save(document, out_dir)


def _first_sentence_lower(paragraph):
    seen_period = False
    for run in _runs(paragraph):
        text = _run_text(run)
        if not text or seen_period:
            continue
        cut = text.find(".")
        if cut < 0:
            _set_text(run, text.lower())
            continue
        seen_period = True
        _set_text(run, text[:cut + 1].lower() + text[cut + 1:])


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    _first_sentence_lower(document.paragraphs[CAPS_PARAGRAPH]._p)
    _save(document, out_dir)


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraph = document.paragraphs[CAPS_PARAGRAPH]._p
    text = "".join(_run_text(run) for run in _runs(paragraph))
    text = text.replace("POWERPOINT", "POWERPOITN").lower()
    runs = _runs(paragraph)
    if runs:
        _set_text(runs[0], text)
        for run in runs[1:]:
            paragraph.remove(run)
    _save(document, out_dir)


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for index, paragraph in enumerate(document.paragraphs):
        if index == CAPS_PARAGRAPH:
            continue
        for run in _runs(paragraph._p):
            text = _run_text(run)
            if text and text.isupper():
                _lower_run(run)
    _save(document, out_dir)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    paragraph = document.paragraphs[CAPS_PARAGRAPH]._p
    runs = _runs(paragraph)
    if runs:
        text = "".join(_run_text(run) for run in runs).lower()
        _set_text(runs[0], text, keep_breaks=False)
        for run in runs[1:]:
            paragraph.remove(run)
    _save(document, out_dir)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for index in (CODE_PARAGRAPH, CAPS_PARAGRAPH):
        for run in _runs(document.paragraphs[index]._p):
            if _is_caps(_run_text(run)):
                _lower_run(run)
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            run.font.name = "Arial"
    _save(document, out_dir)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for index in (CODE_PARAGRAPH, CAPS_PARAGRAPH):
        for run in _runs(document.paragraphs[index]._p):
            text = _run_text(run)
            if _is_caps(text):
                _set_text(run, re.sub(r"[^A-Za-z ]", "", text).lower())
    _save(document, out_dir)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for run in _runs(document.paragraphs[CAPS_PARAGRAPH]._p):
        text = _run_text(run)
        if _is_caps(text):
            _set_text(run, re.sub(r"POWERPOINT", "powerpoint", text))
    _save(document, out_dir)


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    for index in (CODE_PARAGRAPH, CAPS_PARAGRAPH):
        for run in _runs(document.paragraphs[index]._p):
            text = _run_text(run)
            if _is_caps(text):
                _set_text(run, text.lower()[:60])
    _save(document, out_dir)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    document = _open(out_dir)
    runs = _runs(document.paragraphs[CAPS_PARAGRAPH]._p)
    if runs:
        _lower_run(runs[0])
    _save(document, out_dir)


def _copy(element):
    from lxml import etree

    return etree.fromstring(etree.tostring(element))


def _false(tag):
    node = OxmlElement(tag)
    node.set(qn("w:val"), "0")
    return node
