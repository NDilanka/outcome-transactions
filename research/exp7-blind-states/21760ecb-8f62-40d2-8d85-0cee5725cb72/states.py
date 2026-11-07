"""End states for task 21760ecb-8f62-40d2-8d85-0cee5725cb72 (Ch4 Video Effect.pptx)."""

import os

import pptx
from pptx.oxml.ns import qn
from lxml import etree

from statekit import (
    NS,
    copy_snapshot,
    read_member,
    parse_xml,
    set_transition,
    set_transition_member,
)

SLIDE = ("home", "user", "Desktop", "Ch4 Video Effect.pptx")
DISSOLVE = "<p:dissolve/>"


def _deck(out_dir, name="Ch4 Video Effect.pptx", folder=None):
    return os.path.join(out_dir, *(folder or SLIDE[:-1]), name)


def _save_without_slides(path, keep_first_only=False):
    prs = pptx.Presentation(path)
    if keep_first_only:
        for slide_id in list(prs.slides._sldIdLst)[1:]:
            rel_id = slide_id.get(qn("r:id"))
            prs.part.drop_rel(rel_id)
            prs.slides._sldIdLst.remove(slide_id)
    prs.save(path)


def _drop_shape(path, slide_index, shape_name):
    prs = pptx.Presentation(path)
    slide = prs.slides[slide_index - 1]
    for shape in list(slide.shapes):
        if shape.name == shape_name:
            shape._element.getparent().remove(shape._element)
    prs.save(path)


def _clear_slide(path, slide_index):
    prs = pptx.Presentation(path)
    slide = prs.slides[slide_index - 1]
    tree = slide.shapes._spTree
    for child in list(tree):
        if etree.QName(child).localname not in ("nvGrpSpPr", "grpSpPr"):
            tree.remove(child)
    prs.save(path)


def _layout_member(package_path, slide_index=1):
    rels = parse_xml(read_member(package_path, "ppt/slides/_rels/slide%d.xml.rels" % slide_index))
    for rel in rels:
        target = rel.get("Target") or ""
        if "slideLayout" in target:
            return "ppt/" + target.replace("../", "")
    raise LookupError("no slide layout relationship")


def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    set_transition(_deck(out_dir), 1, DISSOLVE)


def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    for index in range(1, 25):
        set_transition(path, index, DISSOLVE)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    set_transition(_deck(out_dir), 24, DISSOLVE)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    set_transition(_deck(out_dir), 1, DISSOLVE, attrs={"spd": "slow"})


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    set_transition(_deck(out_dir), 2, DISSOLVE)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    set_transition(_deck(out_dir), 1, "<p:fade/>")


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    set_transition_member(path, _layout_member(path), DISSOLVE)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    set_transition(_deck(out_dir), 1, "")


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    set_transition(path, 1, DISSOLVE)
    set_transition(path, 2, DISSOLVE)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    set_transition(_deck(out_dir), 1, '<p14:prstTrans prst="dissolve"/>')


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    set_transition(_deck(out_dir), 1, DISSOLVE, attrs={"spd": "med"})


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    set_transition(path, 1, "<p:checker/>")


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    set_transition(path, 1, DISSOLVE)
    _save_without_slides(path, keep_first_only=True)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    set_transition(_deck(out_dir), 1, DISSOLVE)
    target = os.path.join(out_dir, "home", "user", "Desktop", "Ch4 Video Effect copy.pptx")
    with open(_deck(out_dir), "rb") as source, open(target, "wb") as sink:
        sink.write(source.read())


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    set_transition(_deck(out_dir), 1, DISSOLVE, where="inside_cSld")


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    set_transition(path, 1, DISSOLVE)
    set_transition(path, 24, DISSOLVE)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    _drop_shape(path, 1, "TextBox 1")
    set_transition(path, 1, DISSOLVE)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    _clear_slide(path, 1)
    set_transition(path, 1, DISSOLVE)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    set_transition(_deck(out_dir), 1, DISSOLVE, attrs={"spd": "fast"})


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    set_transition(_deck(out_dir), 1, '<a:dissolve xmlns:a="%s"/>' % NS["a"])


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    set_transition_member(_deck(out_dir), "ppt/slideMasters/slideMaster1.xml", DISSOLVE)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    for index in range(2, 25):
        set_transition(path, index, DISSOLVE)
