"""End states for task 6a33f9b9-0a56-4844-9c3f-96ec3ffb3ba2.

The ODT carries yellow character highlighting through two automatic text
styles: T9 (seven spans) and T5 (one span). The request is to remove all
highlight.
"""

import os
import shutil

import docx
from lxml import etree

from statekit import NS, copy_snapshot, read_member, parse_xml, rewrite_members, xml_bytes

ODT = ("home", "user", "Desktop", "sample-recruitment-phone-script.odt")
YELLOWS = ("#ffff00",)


def _path(out_dir, name="sample-recruitment-phone-script.odt"):
    return os.path.join(out_dir, *ODT[:-1], name)


def _load(out_dir, name="sample-recruitment-phone-script.odt"):
    root = parse_xml(read_member(_path(out_dir, name), "content.xml"))
    return root


def _save(out_dir, root, name="sample-recruitment-phone-script.odt"):
    rewrite_members(_path(out_dir, name), {"content.xml": xml_bytes(root)})


def _text_props(style):
    return style.find("{%s}text-properties" % NS["style"])


def _background(style):
    props = _text_props(style)
    if props is None:
        return None
    return props.get("{%s}background-color" % NS["fo"])


def _text_styles(root):
    out = {}
    for style in root.iter("{%s}style" % NS["style"]):
        if style.get("{%s}family" % NS["style"]) == "text":
            out[style.get("{%s}name" % NS["style"])] = style
    return out


def _highlighted_names(root):
    return [name for name, style in _text_styles(root).items() if (_background(style) or "").lower() in YELLOWS]


def _highlighted_spans(root, names=None):
    names = names if names is not None else _highlighted_names(root)
    spans = []
    for element in root.iter():
        style = element.get("{%s}style-name" % NS["text"])
        if style in names and etree.QName(element).localname == "span":
            spans.append(element)
    return spans


def _clear_highlight(style, mode="transparent"):
    props = _text_props(style)
    if props is None:
        return
    props.attrib.pop("{%s}char-shading-value" % NS["loext"], None)
    if mode == "transparent":
        props.set("{%s}background-color" % NS["fo"], "transparent")
    elif mode == "drop":
        props.attrib.pop("{%s}background-color" % NS["fo"], None)
    elif mode == "white":
        props.set("{%s}background-color" % NS["fo"], "#ffffff")


def _new_style(root, name, source):
    clone = etree.fromstring(etree.tostring(source))
    clone.set("{%s}name" % NS["style"], name)
    source.getparent().append(clone)
    return clone


def _repoint(root, names, replacements):
    for element in root.iter():
        style = element.get("{%s}style-name" % NS["text"])
        if style in names:
            element.set("{%s}style-name" % NS["text"], replacements[style])


def _paragraph_text(root):
    texts = []
    for paragraph in root.iter("{%s}p" % NS["text"]):
        texts.append("".join(paragraph.itertext()))
    return texts


# --- correct states ---------------------------------------------------------

def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    for name in _highlighted_names(root):
        _clear_highlight(_text_styles(root)[name], mode="transparent")
    _save(out_dir, root)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    for name in _highlighted_names(root):
        _clear_highlight(_text_styles(root)[name], mode="drop")
    _save(out_dir, root)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    styles = _text_styles(root)
    names = _highlighted_names(root)
    replacements = {}
    for index, name in enumerate(names, start=1):
        fresh = _new_style(root, "TX%d" % index, styles[name])
        _clear_highlight(fresh, mode="drop")
        replacements[name] = "TX%d" % index
    _repoint(root, set(names), replacements)
    for name in names:
        styles[name].getparent().remove(styles[name])
    _save(out_dir, root)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    for name in _highlighted_names(root):
        _clear_highlight(_text_styles(root)[name], mode="drop")
    styles = _text_styles(root)
    for name in ("T4", "T8"):
        if name in styles:
            styles[name].getparent().remove(styles[name])
    _save(out_dir, root)


# --- wrong states -----------------------------------------------------------

def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    styles = _text_styles(root)
    _clear_highlight(styles["T9"], mode="transparent")
    _save(out_dir, root)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    styles = _text_styles(root)
    _clear_highlight(styles["T5"], mode="transparent")
    _save(out_dir, root)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    for name in _highlighted_names(root):
        _clear_highlight(_text_styles(root)[name], mode="white")
    _save(out_dir, root)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    for name in _highlighted_names(root):
        props = _text_props(_text_styles(root)[name])
        props.set("{%s}background-color" % NS["fo"], "#fdf6e3")
    _save(out_dir, root)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    for name in _highlighted_names(root):
        props = _text_props(_text_styles(root)[name])
        props.set("{%s}background-color" % NS["fo"], "#ffffcc")
    _save(out_dir, root)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    for span in _highlighted_spans(root):
        for child in list(span):
            span.remove(child)
        span.text = ""
    _save(out_dir, root)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    for name in _highlighted_names(root):
        style = _text_styles(root)[name]
        _clear_highlight(style, mode="drop")
        props = _text_props(style)
        props.set("{%s}font-style" % NS["fo"], "normal")
        props.attrib.pop("{%s}font-style-asian" % NS["style"], None)
    _save(out_dir, root)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    for style in root.iter("{%s}style" % NS["style"]):
        if style.get("{%s}family" % NS["style"]) != "paragraph":
            continue
        props = _text_props(style)
        if props is None:
            props = etree.SubElement(style, "{%s}text-properties" % NS["style"])
        props.set("{%s}background-color" % NS["fo"], "#ffff00")
    _save(out_dir, root)


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    styles = _text_styles(root)
    for name in ("T1", "T2", "T3", "T6", "T7"):
        if name in styles:
            props = _text_props(styles[name])
            if props is not None:
                props.set("{%s}background-color" % NS["fo"], "transparent")
    _save(out_dir, root)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    names = _highlighted_names(root)
    _repoint(root, set(names), {name: "T42" for name in names})
    _save(out_dir, root)


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    for name in _highlighted_names(root):
        _clear_highlight(_text_styles(root)[name], mode="transparent")
    document = docx.Document()
    for line in _paragraph_text(root):
        document.add_paragraph(line)
    os.makedirs(os.path.join(out_dir, *ODT[:-1]), exist_ok=True)
    document.save(os.path.join(out_dir, *ODT[:-1], "sample-recruitment-phone-script.docx"))
    shutil.copyfile(os.path.join(snapshot_dir, *ODT), _path(out_dir))


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    name = "sample-recruitment-phone-script copy.odt"
    shutil.copyfile(_path(out_dir), _path(out_dir, name))
    root = _load(out_dir, name=name)
    for style_name in _highlighted_names(root):
        _clear_highlight(_text_styles(root)[style_name], mode="transparent")
    _save(out_dir, root, name=name)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    for element in root.iter("{%s}span" % NS["text"]):
        element.attrib.pop("{%s}style-name" % NS["text"], None)
    _save(out_dir, root)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    for name in _highlighted_names(root):
        style = _text_styles(root)[name]
        _clear_highlight(style, mode="drop")
        props = _text_props(style)
        props.set("{%s}color" % NS["fo"], "#ffff00")
    _save(out_dir, root)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    for name in _highlighted_names(root):
        style = _text_styles(root)[name]
        _clear_highlight(style, mode="drop")
        props = _text_props(style)
        props.set("{%s}text-underline-style" % NS["style"], "solid")
        props.set("{%s}text-underline-type" % NS["style"], "single")
    _save(out_dir, root)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    styles = _text_styles(root)
    for span in _highlighted_spans(root)[:4]:
        style = styles.get(span.get("{%s}style-name" % NS["text"]))
        if style is not None:
            _clear_highlight(style, mode="transparent")
    _save(out_dir, root)


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    styles = _text_styles(root)
    for name in _highlighted_names(root):
        _clear_highlight(styles[name], mode="drop")
    for name in ("T1", "T2"):
        if name in styles:
            props = _text_props(styles[name])
            props.attrib.pop("{%s}font-weight" % NS["fo"], None)
            props.attrib.pop("{%s}font-weight-asian" % NS["style"], None)
    _save(out_dir, root)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    root = _load(out_dir)
    for name in _highlighted_names(root):
        _clear_highlight(_text_styles(root)[name], mode="drop")
    for paragraph in list(root.iter("{%s}p" % NS["text"])):
        if not "".join(paragraph.itertext()).strip():
            paragraph.getparent().remove(paragraph)
    _save(out_dir, root)
