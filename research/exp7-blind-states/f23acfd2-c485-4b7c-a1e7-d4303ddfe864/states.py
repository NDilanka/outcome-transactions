"""End states for task f23acfd2-c485-4b7c-a1e7-d4303ddfe864 (69_4.pptx).

The slide has a title placeholder and one body placeholder holding a single
paragraph of content.
"""

import os
import shutil

from lxml import etree

from statekit import NS, copy_snapshot, read_member, parse_xml, rewrite_members, xml_bytes

DECK = ("home", "user", "Desktop", "69_4.pptx")
TITLE = "PlaceHolder 1"
BODY = "PlaceHolder 2"


def _deck(out_dir, name="69_4.pptx"):
    return os.path.join(out_dir, *DECK[:-1], name)


def _slide(path):
    return "ppt/slides/slide1.xml", parse_xml(read_member(path, "ppt/slides/slide1.xml"))


def _write(path, member, root):
    rewrite_members(path, {member: xml_bytes(root)})


def _shape(root, name):
    for sp in root.iter("{%s}sp" % NS["p"]):
        cNvPr = sp.find(".//{%s}cNvPr" % NS["p"])
        if cNvPr is not None and cNvPr.get("name") == name:
            return sp
    raise LookupError(name)


def _paragraphs(shape):
    return shape.find(".//{%s}txBody" % NS["p"]).findall("{%s}p" % NS["a"])


def _pPr(paragraph):
    pPr = paragraph.find("{%s}pPr" % NS["a"])
    if pPr is None:
        pPr = etree.Element("{%s}pPr" % NS["a"])
        paragraph.insert(0, pPr)
    return pPr


def _drop_children(parent, names):
    for child in list(parent):
        if etree.QName(child).localname in names:
            parent.remove(child)


def _bullet(paragraph, char="\u2022", mar_l="342900", indent="-342900", font=None, size=None):
    pPr = _pPr(paragraph)
    _drop_children(pPr, ("buNone", "buChar", "buAutoNum", "buBlip", "buFont", "buSzPct"))
    pPr.set("marL", mar_l)
    pPr.set("indent", indent)
    if font:
        etree.SubElement(pPr, "{%s}buFont" % NS["a"]).set("typeface", font)
    if size:
        etree.SubElement(pPr, "{%s}buSzPct" % NS["a"]).set("val", size)
    etree.SubElement(pPr, "{%s}buChar" % NS["a"]).set("char", char)
    return pPr


def _content_text():
    return (
        "Art is a diverse range of human activities in creating visual, auditory or performing "
        "artifacts, expressing the author's imaginative, conceptual ideas, or technical skill, "
        "intended to be appreciated primarily for their beauty or emotional power."
    )


def _set_text(shape, text):
    run = shape.find(".//{%s}r" % NS["a"])
    run.find("{%s}t" % NS["a"]).text = text


def _copy_deck(out_dir, name="69_4 copy.pptx"):
    shutil.copyfile(_deck(out_dir), _deck(out_dir, name=name))
    return _deck(out_dir, name=name)


# --- correct states ---------------------------------------------------------

def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    _bullet(_paragraphs(_shape(root, BODY))[0])
    _write(path, member, root)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    _bullet(_paragraphs(_shape(root, BODY))[0], font="Arial", size="100000")
    _write(path, member, root)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    _bullet(_paragraphs(_shape(root, BODY))[0], char="\u25cf", font="Arial")
    _write(path, member, root)


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    body = _shape(root, BODY)
    paragraph = _paragraphs(body)[0]
    _drop_children(_pPr(paragraph), ("buNone",))
    txBody = body.find("{%s}txBody" % NS["p"])
    lst = txBody.find("{%s}lstStyle" % NS["a"])
    if lst is None:
        lst = etree.SubElement(txBody, "{%s}lstStyle" % NS["a"])
        txBody.remove(lst)
        txBody.insert(1, lst)
    lvl = etree.SubElement(lst, "{%s}lvl1pPr" % NS["a"])
    lvl.set("marL", "342900")
    lvl.set("indent", "-342900")
    etree.SubElement(lvl, "{%s}buFont" % NS["a"]).set("typeface", "Arial")
    etree.SubElement(lvl, "{%s}buChar" % NS["a"]).set("char", "\u2022")
    _write(path, member, root)


# --- wrong states -----------------------------------------------------------

def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    paragraph = _paragraphs(_shape(root, BODY))[0]
    run = paragraph.find("{%s}r" % NS["a"])
    run.find("{%s}t" % NS["a"]).text = "\u2022 " + run.find("{%s}t" % NS["a"]).text
    _write(path, member, root)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    _bullet(_paragraphs(_shape(root, TITLE))[0])
    _write(path, member, root)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    body = _shape(root, BODY)
    paragraph = _paragraphs(body)[0]
    pPr = _pPr(paragraph)
    pPr.set("marL", "342900")
    pPr.set("indent", "-342900")
    _write(path, member, root)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    body = _shape(root, BODY)
    txBody = body.find("{%s}txBody" % NS["p"])
    new = etree.SubElement(txBody, "{%s}p" % NS["a"])
    txBody.remove(new)
    txBody.append(new)
    pPr = etree.SubElement(new, "{%s}pPr" % NS["a"])
    pPr.set("marL", "342900")
    pPr.set("indent", "-342900")
    etree.SubElement(pPr, "{%s}buFont" % NS["a"]).set("typeface", "Arial")
    etree.SubElement(pPr, "{%s}buChar" % NS["a"]).set("char", "\u2022")
    etree.SubElement(new, "{%s}endParaRPr" % NS["a"]).set("lang", "en-US")
    _write(path, member, root)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    _bullet(_paragraphs(_shape(root, BODY))[0])
    _bullet(_paragraphs(_shape(root, TITLE))[0])
    _write(path, member, root)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    paragraph = _paragraphs(_shape(root, BODY))[0]
    pPr = _pPr(paragraph)
    pPr.set("marL", "342900")
    pPr.set("indent", "-342900")
    etree.SubElement(pPr, "{%s}buChar" % NS["a"]).set("char", "\u2022")
    _write(path, member, root)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    body = _shape(root, BODY)
    paragraph = _paragraphs(body)[0]
    run = paragraph.find("{%s}r" % NS["a"])
    text = run.find("{%s}t" % NS["a"])
    text.text = text.text[:60].rstrip() + "."
    _bullet(paragraph)
    _write(path, member, root)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    spTree = root.find(".//{%s}spTree" % NS["p"])
    box = etree.SubElement(spTree, "{%s}sp" % NS["p"])
    nv = etree.SubElement(box, "{%s}nvSpPr" % NS["p"])
    etree.SubElement(nv, "{%s}cNvPr" % NS["p"]).set("id", "900")
    etree.SubElement(nv, "{%s}cNvSpPr" % NS["p"]).set("txBox", "1")
    etree.SubElement(nv, "{%s}nvPr" % NS["p"])
    spPr = etree.SubElement(box, "{%s}spPr" % NS["p"])
    xfrm = etree.SubElement(spPr, "{%s}xfrm" % NS["p"])
    off = etree.SubElement(xfrm, "{%s}off" % NS["a"])
    off.set("x", "228600")
    off.set("y", "1600200")
    ext = etree.SubElement(xfrm, "{%s}ext" % NS["a"])
    ext.set("cx", "457200")
    ext.set("cy", "22860000")
    txBody = etree.SubElement(box, "{%s}txBody" % NS["p"])
    etree.SubElement(txBody, "{%s}bodyPr" % NS["a"])
    paragraph = etree.SubElement(txBody, "{%s}p" % NS["a"])
    run = etree.SubElement(paragraph, "{%s}r" % NS["a"])
    etree.SubElement(run, "{%s}rPr" % NS["a"]).set("lang", "en-US")
    etree.SubElement(run, "{%s}t" % NS["a"]).text = "\u2022"
    _write(path, member, root)


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    _bullet(_paragraphs(_shape(root, BODY))[0])
    _write(path, member, root)
    shutil.copyfile(path, os.path.join(out_dir, *DECK[:-1], "69_4.odp"))
    shutil.copyfile(os.path.join(snapshot_dir, *DECK), path)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _copy_deck(out_dir)
    member, root = _slide(path)
    _bullet(_paragraphs(_shape(root, BODY))[0])
    _write(path, member, root)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    paragraph = _paragraphs(_shape(root, BODY))[0]
    pPr = _pPr(paragraph)
    pPr.set("marL", "342900")
    pPr.set("indent", "-342900")
    etree.SubElement(pPr, "{%s}buChar" % NS["a"]).set("char", "")
    _write(path, member, root)


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    body = _shape(root, BODY)
    _bullet(_paragraphs(body)[0])
    xfrm = body.find("{%s}spPr" % NS["p"]).find("{%s}xfrm" % NS["a"])
    xfrm.find("{%s}off" % NS["a"]).set("y", "4946650")
    xfrm.find("{%s}off" % NS["a"]).set("x", "937260")
    _write(path, member, root)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    paragraph = _paragraphs(_shape(root, BODY))[0]
    _bullet(paragraph)
    for run in paragraph.findall("{%s}r" % NS["a"]):
        rPr = run.find("{%s}rPr" % NS["a"])
        fill = rPr.find("{%s}solidFill" % NS["a"])
        fill.find("{%s}srgbClr" % NS["a"]).set("val", "FFFFFF")
    _write(path, member, root)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    paragraph = _paragraphs(_shape(root, BODY))[0]
    pPr = _pPr(paragraph)
    pPr.set("marL", "342900")
    pPr.set("indent", "-342900")
    blip = etree.SubElement(pPr, "{%s}buBlip" % NS["a"])
    etree.SubElement(blip, "{%s}blip" % NS["a"]).set(
        "{%s}embed" % NS["r"], "rId99")
    _write(path, member, root)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    paragraph = _paragraphs(_shape(root, BODY))[0]
    _bullet(paragraph, char="1")
    pPr = paragraph.find("{%s}pPr" % NS["a"])
    _drop_children(pPr, ("buChar",))
    num = etree.SubElement(pPr, "{%s}buAutoNum" % NS["a"])
    num.set("type", "arabicPeriod")
    _write(path, member, root)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    body = _shape(root, BODY)
    paragraph = _paragraphs(body)[0]
    _bullet(paragraph)
    run = paragraph.find("{%s}r" % NS["a"])
    text = run.find("{%s}t" % NS["a"])
    text.text = text.text.upper()
    _write(path, member, root)


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    body = _shape(root, BODY)
    paragraph = _paragraphs(body)[0]
    _bullet(paragraph)
    for solid in body.findall(".//{%s}solidFill" % NS["a"]):
        solid.getparent().remove(solid)
    _write(path, member, root)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    path = _deck(out_dir)
    member, root = _slide(path)
    body = _shape(root, BODY)
    paragraph = _paragraphs(body)[0]
    _bullet(paragraph)
    txBody = body.find("{%s}txBody" % NS["p"])
    duplicate = etree.fromstring(etree.tostring(paragraph))
    txBody.append(duplicate)
    _write(path, member, root)
