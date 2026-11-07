"""End states for task 550ce7e7-747b-495f-b122-acdc4d0b8e54 (New_Club_Spring_2018_Training.pptx)."""

import os
import shutil

from lxml import etree

from statekit import (
    NS,
    copy_snapshot,
    shape_by_name,
    slide_xml,
    write_slide_xml,
    set_paragraph_strike,
)

DECK = ("home", "user", "Desktop", "New_Club_Spring_2018_Training.pptx")


def _deck(out_dir, name="New_Club_Spring_2018_Training.pptx", folder=None):
    return os.path.join(out_dir, *(folder or DECK[:-1]), name)


def _paras(shape):
    return shape.findall(".//{%s}p" % NS["a"])


def _body(root, name="PlaceHolder 2"):
    return shape_by_name(root, name)


def _strike(paragraph, value="sngStrike"):
    set_paragraph_strike(paragraph, value)


def _strike_runs(paragraph, value="sngStrike"):
    for run in paragraph.findall("{%s}r" % NS["a"]):
        rPr = run.find("{%s}rPr" % NS["a"])
        if rPr is None:
            rPr = etree.Element("{%s}rPr" % NS["a"])
            run.insert(0, rPr)
        rPr.set("strike", value)


def _strip_no_strike(paragraph):
    for run in paragraph.findall("{%s}r" % NS["a"]):
        rPr = run.find("{%s}rPr" % NS["a"])
        if rPr is not None and rPr.get("strike") is not None:
            del rPr.attrib["strike"]


def _def_rpr(paragraph, value="sngStrike"):
    pPr = paragraph.find("{%s}pPr" % NS["a"])
    if pPr is None:
        pPr = etree.Element("{%s}pPr" % NS["a"])
        paragraph.insert(0, pPr)
    defRpr = pPr.find("{%s}defRPr" % NS["a"])
    if defRpr is None:
        defRpr = etree.SubElement(pPr, "{%s}defRPr" % NS["a"])
    defRpr.set("strike", value)
    return defRpr


def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    body = _body(root)
    for paragraph in _paras(body)[:2]:
        _strike_runs(paragraph)
    write_slide_xml(path, member, root)


def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    for paragraph in _paras(_body(root))[1:3]:
        _strike(paragraph)
    write_slide_xml(path, member, root)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    _strike(_paras(_body(root))[0])
    write_slide_xml(path, member, root)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    for paragraph in _paras(_body(root))[:2]:
        _strike(paragraph)
        end = paragraph.find("{%s}endParaRPr" % NS["a"])
        if end is not None:
            end.set("strike", "sngStrike")
    write_slide_xml(path, member, root)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    body = _body(root)
    for paragraph in _paras(body):
        _strike(paragraph)
    write_slide_xml(path, member, root)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    title = _body(root, "PlaceHolder 1")
    for paragraph in _paras(title)[:2]:
        _strike(paragraph)
    write_slide_xml(path, member, root)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 2)
    for paragraph in _paras(_body(root))[:2]:
        _strike(paragraph)
    write_slide_xml(path, member, root)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    for paragraph in _paras(_body(root))[:2]:
        for run in paragraph.findall("{%s}r" % NS["a"]):
            rPr = run.find("{%s}rPr" % NS["a"])
            rPr.set("u", "sng")
    write_slide_xml(path, member, root)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    for paragraph in _paras(_body(root))[:2]:
        for run in paragraph.findall("{%s}r" % NS["a"]):
            rPr = run.find("{%s}rPr" % NS["a"])
            rPr.set("b", "1")
    write_slide_xml(path, member, root)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    for paragraph in _paras(_body(root))[:2]:
        _strike(paragraph, "dblStrike")
    write_slide_xml(path, member, root)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    for paragraph in _paras(_body(root))[:2]:
        _def_rpr(paragraph)
    write_slide_xml(path, member, root)


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    for paragraph in _paras(_body(root))[:2]:
        _strike(paragraph)
        end = paragraph.find("{%s}endParaRPr" % NS["a"])
        if end is not None:
            end.set("strike", "sngStrike")
        _def_rpr(paragraph)
    write_slide_xml(path, member, root)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    paragraphs = _paras(_body(root))
    for paragraph in paragraphs[:2]:
        _strike(paragraph)
    body = _body(root)
    body.find(".//{%s}txBody" % NS["p"]).remove(paragraphs[2])
    write_slide_xml(path, member, root)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    for paragraph in _paras(_body(root))[:2]:
        _strike(paragraph)
        for run in paragraph.findall("{%s}r" % NS["a"]):
            text = run.find("{%s}t" % NS["a"])
            if text is not None and text.text:
                text.text = text.text + " (done)"
    write_slide_xml(path, member, root)


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    for paragraph in _paras(_body(root))[:2]:
        for run in paragraph.findall("{%s}r" % NS["a"]):
            rPr = run.find("{%s}rPr" % NS["a"])
            for old in rPr.findall("{%s}solidFill" % NS["a"]):
                rPr.remove(old)
            fill = etree.SubElement(rPr, "{%s}solidFill" % NS["a"])
            etree.SubElement(fill, "{%s}srgbClr" % NS["a"]).set("val", "808080")
    write_slide_xml(path, member, root)


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    paragraphs = _paras(_body(root))
    _strike(paragraphs[0])
    _strike(paragraphs[-1])
    write_slide_xml(path, member, root)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    for index in range(1, 8):
        member, root = slide_xml(path, index)
        body = _body(root)
        if body is None:
            continue
        for paragraph in _paras(body)[:2]:
            _strike(paragraph)
        write_slide_xml(path, member, root)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    for paragraph in _paras(_body(root))[:2]:
        end = paragraph.find("{%s}endParaRPr" % NS["a"])
        if end is not None:
            end.set("strike", "sngStrike")
    write_slide_xml(path, member, root)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    for paragraph in _paras(_body(root))[:2]:
        _strip_no_strike(paragraph)
        _def_rpr(paragraph)
    write_slide_xml(path, member, root)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    for paragraph in _paras(_body(root))[:2]:
        _strike(paragraph)
        pPr = paragraph.find("{%s}pPr" % NS["a"])
        for bullet in pPr.findall("{%s}buChar" % NS["a"]):
            pPr.remove(bullet)
        if pPr.find("{%s}buNone" % NS["a"]) is None:
            etree.SubElement(pPr, "{%s}buNone" % NS["a"])
    write_slide_xml(path, member, root)


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = slide_xml(path, 5)
    for paragraph in _paras(_body(root))[:3]:
        _strike(paragraph)
    write_slide_xml(path, member, root)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    target = _deck(out_dir, name="New_Club_Spring_2018_Training copy.pptx")
    shutil.copyfile(path, target)
    member, root = slide_xml(target, 5)
    for paragraph in _paras(_body(root))[:2]:
        _strike(paragraph)
    write_slide_xml(target, member, root)
