"""End states for task 57667013-ea97-417c-9dce-2713091e6e2a (1_2.pptx).

Slide 5 (index 4) holds two text-bearing shapes: a headline block and a
caption line. Yellow is sRGB FFFF00.
"""

import os
import shutil

from lxml import etree

from statekit import NS, copy_snapshot, read_member, parse_xml, rewrite_members, xml_bytes

DECK = ("home", "user", "Desktop", "1_2.pptx")
HEADLINE = "Google Shape;166;p 1"
CAPTION = "Google Shape;167;p 1"
SLIDE = 5
YELLOW = "FFFF00"
FILL_TAGS = ("noFill", "solidFill", "gradFill", "blipFill", "pattFill", "grpFill")


def _path(out_dir, name="1_2.pptx"):
    return os.path.join(out_dir, *DECK[:-1], name)


def _slide(out_dir, index=SLIDE, name="1_2.pptx"):
    member = "ppt/slides/slide%d.xml" % index
    return member, parse_xml(read_member(_path(out_dir, name), member))


def _write(out_dir, member, root, name="1_2.pptx"):
    rewrite_members(_path(out_dir, name), {member: xml_bytes(root)})


def _shape(root, name):
    for sp in root.iter("{%s}sp" % NS["p"]):
        cNvPr = sp.find(".//{%s}cNvPr" % NS["p"])
        if cNvPr is not None and cNvPr.get("name") == name:
            return sp
    raise LookupError(name)


def _text_shapes(root):
    out = []
    for sp in root.iter("{%s}sp" % NS["p"]):
        if sp.find(".//{%s}t" % NS["a"]) is not None:
            out.append(sp)
    return out


def _runs(shape):
    return shape.findall(".//{%s}r" % NS["a"])


def _rPr(run):
    rPr = run.find("{%s}rPr" % NS["a"])
    if rPr is None:
        rPr = etree.Element("{%s}rPr" % NS["a"])
        run.insert(0, rPr)
    return rPr


def _colour(properties, element):
    for child in list(properties):
        if etree.QName(child).localname in FILL_TAGS:
            properties.remove(child)
    index = 0
    for position, child in enumerate(properties):
        if etree.QName(child).localname == "ln":
            index = position + 1
    properties.insert(index, element)


def _srgb(hex_value):
    fill = etree.Element("{%s}solidFill" % NS["a"])
    etree.SubElement(fill, "{%s}srgbClr" % NS["a"]).set("val", hex_value)
    return fill


def _prst(name):
    fill = etree.Element("{%s}solidFill" % NS["a"])
    etree.SubElement(fill, "{%s}prstClr" % NS["a"]).set("val", name)
    return fill


def _scheme(name):
    fill = etree.Element("{%s}solidFill" % NS["a"])
    etree.SubElement(fill, "{%s}schemeClr" % NS["a"]).set("val", name)
    return fill


def yellow_shapes(root, shapes=None, colour=None):
    for shape in shapes if shapes is not None else _text_shapes(root):
        for run in _runs(shape):
            _colour(_rPr(run), colour if colour is not None else _srgb(YELLOW))


def _paragraph_defaults(shape, hex_value=YELLOW):
    for paragraph in shape.findall(".//{%s}p" % NS["a"]):
        pPr = paragraph.find("{%s}pPr" % NS["a"])
        if pPr is None:
            pPr = etree.Element("{%s}pPr" % NS["a"])
            paragraph.insert(0, pPr)
        defRpr = pPr.find("{%s}defRPr" % NS["a"])
        if defRpr is None:
            defRpr = etree.SubElement(pPr, "{%s}defRPr" % NS["a"])
        _colour(defRpr, _srgb(hex_value))


def _end_marks(shape, hex_value=YELLOW):
    for end in shape.findall(".//{%s}endParaRPr" % NS["a"]):
        _colour(end, _srgb(hex_value))


# --- correct states ---------------------------------------------------------

def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    yellow_shapes(root)
    _write(out_dir, member, root)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    for shape in _text_shapes(root):
        for run in _runs(shape):
            _colour(_rPr(run), _srgb(YELLOW))
        _end_marks(shape)
        _paragraph_defaults(shape)
    _write(out_dir, member, root)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    for shape in _text_shapes(root):
        for run in _runs(shape):
            _colour(_rPr(run), _prst("yellow"))
    _write(out_dir, member, root)


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    for shape in _text_shapes(root):
        for run in _runs(shape):
            rPr = _rPr(run)
            for child in list(rPr):
                if etree.QName(child).localname in FILL_TAGS:
                    rPr.remove(child)
        _paragraph_defaults(shape)
    _write(out_dir, member, root)


# --- wrong states -----------------------------------------------------------

def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir, 4)
    yellow_shapes(root)
    _write(out_dir, member, root)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    yellow_shapes(root, [_shape(root, HEADLINE)])
    _write(out_dir, member, root)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for index in range(1, 6):
        member, root = _slide(out_dir, index)
        yellow_shapes(root)
        _write(out_dir, member, root)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    yellow_shapes(root, colour=_srgb("FFFF99"))
    _write(out_dir, member, root)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    yellow_shapes(root, colour=_srgb("FFC000"))
    _write(out_dir, member, root)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    yellow_shapes(root, colour=_scheme("accent4"))
    _write(out_dir, member, root)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    for shape in _text_shapes(root):
        spPr = shape.find("{%s}spPr" % NS["p"])
        _colour(spPr, _srgb(YELLOW))
    _write(out_dir, member, root)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    for shape in _text_shapes(root):
        spPr = shape.find("{%s}spPr" % NS["p"])
        line = spPr.find("{%s}ln" % NS["a"])
        if line is None:
            line = etree.SubElement(spPr, "{%s}ln" % NS["a"])
        _colour(line, _srgb(YELLOW))
        line.set("w", "25400")
    _write(out_dir, member, root)


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    for shape in _text_shapes(root):
        for run in _runs(shape):
            rPr = _rPr(run)
            highlight = etree.Element("{%s}highlight" % NS["a"])
            etree.SubElement(highlight, "{%s}srgbClr" % NS["a"]).set("val", YELLOW)
            index = len(rPr)
            for position, child in enumerate(rPr):
                if etree.QName(child).localname in ("latin", "ea", "cs", "sym", "hlinkClick"):
                    index = position
                    break
            rPr.insert(index, highlight)
    _write(out_dir, member, root)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    groups = []
    for group in root.iter("{%s}grpSp" % NS["p"]):
        for sp in group.iter("{%s}sp" % NS["p"]):
            groups.append(sp)
    for shape in groups:
        for run in _runs(shape):
            _colour(_rPr(run), _srgb(YELLOW))
    _write(out_dir, member, root)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    for shape in _text_shapes(root):
        _end_marks(shape)
    _write(out_dir, member, root)


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    name = "1_2 copy.pptx"
    shutil.copyfile(_path(out_dir), _path(out_dir, name))
    member, root = _slide(out_dir, name=name)
    yellow_shapes(root)
    _write(out_dir, member, root, name=name)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    yellow_shapes(root)
    _write(out_dir, member, root)
    shutil.copyfile(_path(out_dir), _path(out_dir, "1_2.odp"))
    shutil.copyfile(os.path.join(snapshot_dir, *DECK), _path(out_dir))


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    yellow_shapes(root)
    caption = _shape(root, CAPTION)
    for run in _runs(caption):
        text = run.find("{%s}t" % NS["a"])
        if text is not None:
            text.text = text.text[:20]
    _write(out_dir, member, root)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    for shape in _text_shapes(root):
        for run in _runs(shape):
            fill = _srgb(YELLOW)
            etree.SubElement(fill.find("{%s}srgbClr" % NS["a"]), "{%s}alpha" % NS["a"]).set("val", "0")
            _colour(_rPr(run), fill)
    _write(out_dir, member, root)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    for shape in _text_shapes(root):
        for run in _runs(shape):
            fill = _srgb(YELLOW)
            etree.SubElement(fill.find("{%s}srgbClr" % NS["a"]), "{%s}lumMod" % NS["a"]).set("val", "60000")
            _colour(_rPr(run), fill)
    _write(out_dir, member, root)


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    yellow_shapes(root, [_shape(root, CAPTION)])
    _write(out_dir, member, root)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir)
    yellow_shapes(root)
    for sp in root.iter("{%s}sp" % NS["p"]):
        spPr = sp.find("{%s}spPr" % NS["p"])
        if spPr is not None:
            _colour(spPr, _srgb("000000"))
    _write(out_dir, member, root)
