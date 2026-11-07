"""End states for task 7ae48c60-f143-4119-b659-15b8f485eb9a (30_1.pptx).

Each of slides 3, 4 and 6 carries one large image: a picture-filled shape on
slide 3 and p:pic elements on slides 4 and 6. Heights are stored in EMU
(1 cm = 360000 EMU).
"""

import os
import shutil

from lxml import etree

from statekit import NS, copy_snapshot, read_member, parse_xml, rewrite_members, xml_bytes

DECK = ("home", "user", "Desktop", "30_1.pptx")
TARGETS = {3: (20, "Google Shape;446;p18"), 4: (30, "Google Shape;466;p19"), 6: (25, "Google Shape;684;p22")}
SLIDE_HEIGHT = 10287000


def _path(out_dir, name="30_1.pptx"):
    return os.path.join(out_dir, *DECK[:-1], name)


def _slide(out_dir, index, name="30_1.pptx"):
    member = "ppt/slides/slide%d.xml" % index
    return member, parse_xml(read_member(_path(out_dir, name), member))


def _write(out_dir, member, root, name="30_1.pptx"):
    rewrite_members(_path(out_dir, name), {member: xml_bytes(root)})


def _shape(root, name):
    for element in root.iter():
        if etree.QName(element).localname not in ("sp", "pic", "grpSp"):
            continue
        cNvPr = element.find(".//{%s}cNvPr" % NS["p"])
        if cNvPr is not None and cNvPr.get("name") == name:
            return element
    raise LookupError(name)


def _xfrm(shape):
    if etree.QName(shape).localname == "grpSp":
        return shape.find("{%s}grpSpPr" % NS["p"]).find("{%s}xfrm" % NS["a"])
    return shape.find("{%s}spPr" % NS["p"]).find("{%s}xfrm" % NS["a"])


def _ext(shape):
    return _xfrm(shape).find("{%s}ext" % NS["a"])


def _off(shape):
    return _xfrm(shape).find("{%s}off" % NS["a"])


def _cm(value):
    return int(round(value * 360000))


def _set_height(root, slide, centimetres, name=None):
    shape = _shape(root, name or TARGETS[slide][1])
    _ext(shape).set("cy", str(_cm(centimetres)))
    return shape


def _set_width(root, slide, centimetres, name=None):
    shape = _shape(root, name or TARGETS[slide][1])
    _ext(shape).set("cx", str(_cm(centimetres)))
    return shape


def _copy_deck(out_dir, name="30_1 copy.pptx"):
    shutil.copyfile(_path(out_dir), _path(out_dir, name))
    return name


# --- correct states ---------------------------------------------------------

def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide, (centimetres, _name) in TARGETS.items():
        member, root = _slide(out_dir, slide)
        _set_height(root, slide, centimetres)
        _write(out_dir, member, root)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide, (centimetres, _name) in TARGETS.items():
        member, root = _slide(out_dir, slide)
        shape = _set_height(root, slide, centimetres)
        _off(shape).set("y", str(int((SLIDE_HEIGHT - _cm(centimetres)) / 2)))
        _write(out_dir, member, root)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide, (centimetres, _name) in TARGETS.items():
        member, root = _slide(out_dir, slide)
        shape = _set_height(root, slide, centimetres)
        _off(shape).set("y", "0")
        _write(out_dir, member, root)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide, (centimetres, name) in TARGETS.items():
        member, root = _slide(out_dir, slide)
        shape = _shape(root, name)
        ratio = _cm(centimetres) / int(_ext(shape).get("cy"))
        _ext(shape).set("cy", str(_cm(centimetres)))
        _ext(shape).set("cx", str(int(int(_ext(shape).get("cx")) * ratio)))
        _write(out_dir, member, root)


# --- wrong states -----------------------------------------------------------

def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide, value in ((2, 20), (3, 30), (4, 25)):
        member, root = _slide(out_dir, slide)
        names = {2: "Google Shape;187;p14", 3: "Google Shape;444;p18", 4: "Google Shape;464;p19"}
        shape = _shape(root, names[slide])
        _ext(shape).set("cy", str(_cm(value)))
        _write(out_dir, member, root)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide, value in ((3, 25), (4, 20), (6, 30)):
        member, root = _slide(out_dir, slide)
        _set_height(root, slide, value)
        _write(out_dir, member, root)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide in TARGETS:
        member, root = _slide(out_dir, slide)
        _set_height(root, slide, 20)
        _write(out_dir, member, root)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide, (centimetres, _name) in TARGETS.items():
        member, root = _slide(out_dir, slide)
        shape = _shape(root, TARGETS[slide][1])
        _ext(shape).set("cy", str(centimetres * 12700))
        _write(out_dir, member, root)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide, (centimetres, _name) in TARGETS.items():
        member, root = _slide(out_dir, slide)
        _set_width(root, slide, centimetres)
        _write(out_dir, member, root)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide, (centimetres, _name) in TARGETS.items():
        member, root = _slide(out_dir, slide)
        _set_height(root, slide, centimetres)
        _set_width(root, slide, centimetres)
        _write(out_dir, member, root)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir, 3)
    for icon in ["Google Shape;45%d;p18" % digit for digit in range(0, 7)]:
        shape = _shape(root, icon)
        _ext(shape).set("cy", "1352880")
    _write(out_dir, member, root)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir, 3)
    _ext(_shape(root, "Google Shape;441;p18")).set("cy", str(_cm(20)))
    _write(out_dir, member, root)
    for slide in (4, 6):
        member, root = _slide(out_dir, slide)
        _set_height(root, slide, TARGETS[slide][0])
        _write(out_dir, member, root)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide, (centimetres, _name) in TARGETS.items():
        member, root = _slide(out_dir, slide)
        inches = round(centimetres / 2.54, 2)
        _ext(_shape(root, TARGETS[slide][1])).set("cy", str(int(round(inches * 914400))))
        _write(out_dir, member, root)


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    firsts = {3: "Google Shape;441;p18", 4: "Google Shape;461;p19", 6: "Google Shape;685;p22"}
    for slide, (centimetres, _name) in TARGETS.items():
        member, root = _slide(out_dir, slide)
        _ext(_shape(root, firsts[slide])).set("cy", str(_cm(centimetres)))
        _write(out_dir, member, root)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    plan = {1: 20, 2: 30, 3: 25, 4: 20, 5: 30, 6: 25}
    for slide, value in plan.items():
        member, root = _slide(out_dir, slide)
        shapes = [element for element in root.iter("{%s}pic" % NS["p"])]
        if not shapes:
            continue
        biggest = max(shapes, key=lambda element: int(element.find(".//{%s}ext" % NS["a"]).get("cy")))
        _ext(biggest).set("cy", str(_cm(value)))
        _write(out_dir, member, root)


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide, (centimetres, _name) in TARGETS.items():
        member, root = _slide(out_dir, slide)
        _set_height(root, slide, centimetres)
        _write(out_dir, member, root)
    shutil.copyfile(_path(out_dir), _path(out_dir, "30_1.odp"))
    shutil.copyfile(os.path.join(snapshot_dir, *DECK), _path(out_dir))


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    name = _copy_deck(out_dir)
    for slide, (centimetres, _name) in TARGETS.items():
        member, root = _slide(out_dir, slide, name=name)
        _set_height(root, slide, centimetres)
        _write(out_dir, member, root, name=name)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide, (centimetres, _name) in TARGETS.items():
        member, root = _slide(out_dir, slide)
        _ext(_shape(root, TARGETS[slide][1])).set("cy", str(centimetres * 36000))
        _write(out_dir, member, root)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide, (centimetres, _name) in TARGETS.items():
        member, root = _slide(out_dir, slide)
        shape = _shape(root, TARGETS[slide][1])
        _ext(shape).set("cy", str(_cm(centimetres)))
        _xfrm(shape).set("flipV", "1")
        _write(out_dir, member, root)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir, 3)
    shape = _shape(root, TARGETS[3][1])
    blip_fill = shape.find("{%s}spPr" % NS["p"]).find("{%s}blipFill" % NS["a"])
    crop = etree.Element("{%s}srcRect" % NS["a"])
    crop.set("b", "26000")
    blip_fill.insert(1, crop)
    _set_height(root, 3, 20)
    _write(out_dir, member, root)
    for slide in (4, 6):
        member, root = _slide(out_dir, slide)
        _set_height(root, slide, TARGETS[slide][0])
        _write(out_dir, member, root)


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    member, root = _slide(out_dir, 3)
    picture = _shape(root, TARGETS[3][1])
    picture.getparent().remove(picture)
    _write(out_dir, member, root)
    for slide in (4, 6):
        member, root = _slide(out_dir, slide)
        _set_height(root, slide, TARGETS[slide][0])
        _write(out_dir, member, root)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    for slide, (centimetres, _name) in TARGETS.items():
        member, root = _slide(out_dir, slide)
        shape = _shape(root, TARGETS[slide][1])
        _ext(shape).set("cy", str(_cm(centimetres + 1)))
        _write(out_dir, member, root)
