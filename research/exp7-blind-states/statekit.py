"""Shared helpers for the exp7 blind end-state generators.

Each ``states.py`` module imports from here. Nothing in this module knows about
task requests; it only gives the generators plain-Python ways to copy a
snapshot and rewrite the parts of an OOXML/ODF package that openpyxl,
python-docx and python-pptx cannot reach.
"""

import os
import shutil
import zipfile

from lxml import etree

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "p14": "http://schemas.microsoft.com/office/powerpoint/2010/main",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "loext": "urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
}


def copy_snapshot(snapshot_dir, out_dir):
    """Materialise a pristine copy of the snapshot in out_dir."""
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    elif os.path.exists(out_dir):
        os.remove(out_dir)
    shutil.copytree(snapshot_dir, out_dir)
    return out_dir


def path(out_dir, *parts):
    return os.path.join(out_dir, *parts)


def rewrite_members(package_path, replacements):
    """Replace named members of a zip package, keeping member order.

    ``mimetype`` stays first and stored, which ODF requires.
    """
    with zipfile.ZipFile(package_path) as zin:
        entries = [(info.filename, zin.read(info.filename)) for info in zin.infolist()]
    tmp = package_path + ".tmp"
    with zipfile.ZipFile(tmp, "w") as zout:
        for name, data in entries:
            data = replacements.get(name, data)
            if name == "mimetype":
                zout.writestr(zipfile.ZipInfo("mimetype"), data, compress_type=zipfile.ZIP_STORED)
            else:
                zout.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    os.replace(tmp, package_path)


def read_member(package_path, name):
    with zipfile.ZipFile(package_path) as z:
        return z.read(name)


ODS_MIMETYPE = "application/vnd.oasis.opendocument.spreadsheet"
ODT_MIMETYPE = "application/vnd.oasis.opendocument.text"


def write_odt(path, paragraphs):
    """Write a genuine ODT text document from a list of (text, style) pairs."""
    body = []
    for text in paragraphs:
        escaped = str(text).replace("&", "&amp;").replace("<", "&lt;")
        body.append('<text:p text:style-name="Standard">%s</text:p>' % escaped)
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
        'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
        'office:version="1.2">'
        '<office:automatic-styles>'
        '<style:style style:name="Standard" style:family="paragraph"/>'
        '</office:automatic-styles>'
        '<office:body><office:text>%s</office:text></office:body>'
        '</office:document-content>' % "".join(body)
    )
    styles = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-styles '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
        'office:version="1.2"><office:styles>'
        '<style:style style:name="Standard" style:family="paragraph"/>'
        '</office:styles></office:document-styles>'
    )
    manifest = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
        'manifest:version="1.2">'
        '<manifest:file-entry manifest:full-path="/" manifest:media-type="%s"/>'
        '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
        '<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>'
        '</manifest:manifest>' % ODT_MIMETYPE
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), ODT_MIMETYPE, compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/manifest.xml", manifest, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("content.xml", content, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("styles.xml", styles, compress_type=zipfile.ZIP_DEFLATED)
    return path


def write_ods(path, sheet_name, rows):
    """Write a small but genuine ODS workbook, for wrong-file-format states."""
    cells = []
    for row in rows:
        out = []
        for value in row:
            if value is None:
                out.append("<table:table-cell/>")
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                out.append(
                    '<table:table-cell office:value-type="float" office:value="%s"><text:p>%s</text:p></table:table-cell>'
                    % (repr(value), repr(value))
                )
            else:
                text = str(value).replace("&", "&amp;").replace("<", "&lt;")
                out.append(
                    '<table:table-cell office:value-type="string"><text:p>%s</text:p></table:table-cell>' % text
                )
        cells.append("<table:table-row>%s</table:table-row>" % "".join(out))
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'office:version="1.2"><office:body><office:spreadsheet>'
        '<table:table table:name="%s">%s</table:table>'
        '</office:spreadsheet></office:body></office:document-content>' % (sheet_name, "".join(cells))
    )
    manifest = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
        'manifest:version="1.2">'
        '<manifest:file-entry manifest:full-path="/" manifest:media-type="%s"/>'
        '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
        '</manifest:manifest>' % ODS_MIMETYPE
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), ODS_MIMETYPE, compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/manifest.xml", manifest, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("content.xml", content, compress_type=zipfile.ZIP_DEFLATED)
    return path


def parse_xml(data):
    parser = etree.XMLParser(remove_blank_text=False, huge_tree=True)
    return etree.fromstring(data, parser)


def xml_bytes(root):
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


# --- presentationml ---------------------------------------------------------

def set_transition(package_path, slide_index, transition_xml, attrs=None, where="end"):
    """Replace the effect inside slide N's <p:transition>, in both the
    mc:Choice and the mc:Fallback copy so either reader path sees it."""
    return set_transition_member(
        package_path, "ppt/slides/slide%d.xml" % slide_index, transition_xml, attrs, where)


def set_transition_member(package_path, member, transition_xml, attrs=None, where="end"):
    root = parse_xml(read_member(package_path, member))
    transitions = [el for el in root.iter("{%s}transition" % NS["p"])]
    if not transitions:
        parent = root
        if where == "inside_cSld":
            parent = root.find("{%s}cSld" % NS["p"])
        transitions = [etree.SubElement(parent, "{%s}transition" % NS["p"])]
        if where == "start":
            parent.remove(transitions[0])
            parent.insert(0, transitions[0])
    for tr in transitions:
        for child in list(tr):
            tr.remove(child)
        for piece in parse_xml(
            b"<wrap xmlns:p='%s' xmlns:p14='%s'>%s</wrap>"
            % (NS["p"].encode(), NS["p14"].encode(), transition_xml.encode())
        ):
            tr.append(piece)
        for key, value in (attrs or {}).items():
            tr.set(key, value)
    rewrite_members(package_path, {member: xml_bytes(root)})


def slide_xml(package_path, slide_index):
    member = "ppt/slides/slide%d.xml" % slide_index
    return member, parse_xml(read_member(package_path, member))


def write_slide_xml(package_path, member, root):
    rewrite_members(package_path, {member: xml_bytes(root)})


def shape_by_name(root, name):
    for sp in root.iter("{%s}sp" % NS["p"]):
        cNvPr = sp.find(".//{%s}cNvPr" % NS["p"])
        if cNvPr is not None and cNvPr.get("name") == name:
            return sp
    return None


FILL_TAGS = ("noFill", "solidFill", "gradFill", "blipFill", "pattFill", "grpFill")


def paint_fill(properties, hex_value):
    """Put a solid sRGB colour in a DrawingML properties element, in schema order."""
    for child in list(properties):
        if etree.QName(child).localname in FILL_TAGS:
            properties.remove(child)
    fill = etree.Element("{%s}solidFill" % NS["a"])
    etree.SubElement(fill, "{%s}srgbClr" % NS["a"]).set("val", hex_value)
    index = 0
    for position, child in enumerate(properties):
        if etree.QName(child).localname == "ln":
            index = position + 1
    properties.insert(index, fill)
    return fill


def set_run_color(shape, hex_value, also_end=False):
    """Set a solid sRGB font colour on every run of a shape."""
    for run in shape.findall(".//{%s}r" % NS["a"]):
        rPr = run.find("{%s}rPr" % NS["a"])
        if rPr is None:
            rPr = etree.Element("{%s}rPr" % NS["a"])
            run.insert(0, rPr)
        paint_fill(rPr, hex_value)
    if also_end:
        for end in shape.findall(".//{%s}endParaRPr" % NS["a"]):
            paint_fill(end, hex_value)


def set_paragraph_strike(paragraph, value="sngStrike"):
    for run in paragraph.findall("{%s}r" % NS["a"]):
        rPr = run.find("{%s}rPr" % NS["a"])
        if rPr is None:
            rPr = etree.Element("{%s}rPr" % NS["a"])
            run.insert(0, rPr)
        rPr.set("strike", value)
    end = paragraph.find("{%s}endParaRPr" % NS["a"])
    if end is not None:
        end.set("strike", value)


def set_shape_strike(shape, value="sngStrike"):
    body = shape.find("{%s}txBody" % NS["p"])
    if body is None:
        return
    for para in body.findall("{%s}p" % NS["a"]):
        set_paragraph_strike(para, value)


def text_paragraphs(shape):
    return shape.findall(".//{%s}p" % NS["a"]) if shape is not None else []
