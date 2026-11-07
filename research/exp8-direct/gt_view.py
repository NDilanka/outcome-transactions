"""Uncapped adjudication view for one attempt, written to GT/view/<code>.txt.

The view has the request, UI state and run status (same header as gt_dump.py), then a content-level diff of the
starting copy against the end state: docx paragraphs with run formatting and tables, pptx shapes with positions,
text and run formatting, xlsx cells and hidden rows, odt paragraphs and text styles, and the LibreOffice profile
settings. Unlike the judge packet (CAP_DIFF), nothing is cut. Adjudication only; the judge sees judge packets.
"""
import difflib
import json
import os
import re
import sys
import zipfile

from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_judge_packets as bjp  # noqa: E402
from make_attempts import PRIV  # noqa: E402

GT = "/home/factory-user/exp8/gt"
VIEW = os.path.join(GT, "view")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
OD_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
OD_STYLE = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
OD_FO = "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
EMU_CM = 360000


def cm(v):
    return "None" if v is None else f"{v / EMU_CM:.2f}"


def docx_view(path):
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    d = docx.Document(path)
    out = []
    for child in d.element.body.iterchildren():
        tag = etree.QName(child).localname
        if tag == "p":
            p = Paragraph(child, d)
            breaks = len(child.xpath('.//w:br[@w:type="page"]'))
            runs = []
            for r in p.runs:
                fl = []
                if r.bold:
                    fl.append("b")
                if r.italic:
                    fl.append("i")
                if r.underline:
                    fl.append("u")
                if r.font.strike:
                    fl.append("strike")
                if r.font.highlight_color is not None:
                    fl.append(f"hl={r.font.highlight_color}")
                if r.font.color is not None and r.font.color.rgb is not None:
                    fl.append(f"color={r.font.color.rgb}")
                runs.append((f"[{','.join(fl)}]" if fl else "") + r.text)
            pb = f" PAGEBREAKS={breaks}" if breaks else ""
            style = re.sub(r"\d+$", "", p.style.name)  # LibreOffice renames normal -> normal1 on save
            out.append(f"P({style}){pb}: " + "|".join(runs))
        elif tag == "tbl":
            t = Table(child, d)
            out.append(f"TABLE {len(t.rows)}x{len(t.columns)}")
            for row in t.rows:
                out.append("  ROW: " + " | ".join(c.text for c in row.cells))
    return out


def run_flags_pptx(r):
    rpr = r._r.find(f"{{{A}}}rPr")
    fl = []
    if rpr is not None:
        for k in ("b", "i", "u", "strike"):
            if rpr.get(k) not in (None, "noStrike", "none", "0"):
                fl.append(f"{k}={rpr.get(k)}")
        clr = rpr.find(f"{{{A}}}solidFill/{{{A}}}srgbClr")
        if clr is not None:
            fl.append(f"color={clr.get('val')}")
    return fl


def walk_pptx(shape, out, ind):
    out.append(f"{ind}SHAPE '{shape.name}' x={cm(shape.left)} y={cm(shape.top)} w={cm(shape.width)} h={cm(shape.height)}")
    if hasattr(shape, "shapes") and shape.shape_type is not None and "GROUP" in str(shape.shape_type):
        for s in shape.shapes:
            walk_pptx(s, out, ind + "  ")
        return
    if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
        for pi, para in enumerate(shape.text_frame.paragraphs):
            runs = [(f"[{','.join(run_flags_pptx(r))}]" if run_flags_pptx(r) else "") + r.text for r in para.runs]
            out.append(f"{ind}  p{pi} {para_props_pptx(para)}: " + "|".join(runs))


def para_props_pptx(para):
    """Bullet and indent settings of one paragraph (empty paragraphs are kept in the view)."""
    ppr = para._p.find(f"{{{A}}}pPr")
    if ppr is None:
        return "[bu=inherit]"
    fl = []
    for k in ("marL", "indent", "lvl"):
        if ppr.get(k) is not None:
            fl.append(f"{k}={ppr.get(k)}")
    if ppr.find(f"{{{A}}}buNone") is not None:
        fl.append("bu=none")
    elif ppr.find(f"{{{A}}}buChar") is not None:
        fl.append(f"bu=char{ppr.find(f'{{{A}}}buChar').get('char')!r}")
    elif ppr.find(f"{{{A}}}buAutoNum") is not None:
        fl.append("bu=autonum")
    return "[" + ",".join(fl) + "]"


def pptx_view(path):
    from pptx import Presentation
    prs = Presentation(path)
    out = []
    for si, slide in enumerate(prs.slides, 1):
        out.append(f"SLIDE {si}")
        for shape in slide.shapes:
            walk_pptx(shape, out, "  ")
        # LibreOffice saves transitions inside mc:AlternateContent, so search the whole slide, not only direct children
        for tr in slide._element.iter(f"{{{P}}}transition"):
            kinds = [etree.QName(c).localname for c in tr]
            out.append(f"  TRANSITION speed={tr.get('spd')} {kinds}")
        if any(etree.QName(e).localname == "AlternateContent" for e in slide._element.iter()):
            out.append("  ALTERNATE_CONTENT present")
    return out


def xlsx_view(path):
    import openpyxl
    wb = openpyxl.load_workbook(path)
    out = [f"SHEETS {wb.sheetnames}"]
    for ws in wb.worksheets:
        out.append(f"SHEET {ws.title} dims={ws.dimensions}")
        hidden = sorted(r for r, dim in ws.row_dimensions.items() if dim.hidden)
        if hidden:
            out.append(f"  HIDDEN ROWS {hidden}")
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None:
                    fmt = f" fmt={c.number_format}" if c.number_format != "General" else ""
                    out.append(f"  {c.coordinate} = {c.value!r}{fmt}")
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    out.append(f"CHARTS {len([n for n in names if 'charts/chart' in n])} PIVOT_PARTS {len([n for n in names if 'pivotTable' in n and n.endswith('.xml')])}")
    return out


def odt_view(path):
    root = etree.fromstring(zipfile.ZipFile(path).read("content.xml"))
    out = []
    for st in root.iter(f"{{{OD_STYLE}}}style"):
        props = st.find(f"{{{OD_STYLE}}}text-properties")
        if props is not None:
            attrs = {etree.QName(k).localname: v for k, v in props.attrib.items()}
            out.append(f"STYLE {st.get(f'{{{OD_STYLE}}}name')}: {attrs}")
    for el in root.iter(f"{{{OD_TEXT}}}p", f"{{{OD_TEXT}}}h"):
        parts = [el.text or ""]
        for ch in el:
            if etree.QName(ch).localname == "span":
                parts.append(f"<{ch.get(f'{{{OD_TEXT}}}style-name')}>{''.join(ch.itertext())}</>")
                parts.append(ch.tail or "")
            else:
                parts.append("".join(ch.itertext()) + (ch.tail or ""))
        out.append(f"{etree.QName(el).localname}[{el.get(f'{{{OD_TEXT}}}style-name')}]: {''.join(parts)}")
    return out


def profile_view(path):
    p = os.path.join(path, "user", "registrymodifications.xcu") if os.path.isdir(os.path.join(path, "user")) else \
        os.path.join(path, "registrymodifications.xcu")
    return open(p, encoding="utf-8", errors="replace").read().splitlines()


def view_lines(e, path):
    if e["kind"] == "profile":
        return profile_view(path)
    f = e["file"].lower()
    if f.endswith(".docx"):
        return docx_view(path)
    if f.endswith(".pptx"):
        return pptx_view(path)
    if f.endswith(".xlsx"):
        return xlsx_view(path)
    if f.endswith(".odt"):
        return odt_view(path)
    raise ValueError(f"no view for {e['file']}")


def main(codes):
    os.makedirs(VIEW, exist_ok=True)
    entries = {e["code"]: e for e in json.load(open(os.path.join(PRIV, "map.json")))}
    tasks = {t["id"][:8]: t["instruction"] for t in json.load(open(os.path.join(HERE, "..", "exp4b", "blind_tasks.json")))}
    for c in codes:
        e = entries[c]
        res = json.load(open(os.path.join(bjp.EXEC, c, "result.json")))
        if not res.get("end_state"):
            print(c, "no end state yet")
            continue
        pk = bjp.packet_for(e, res, tasks)
        b = view_lines(e, e["input_path"])
        a = view_lines(e, res["end_state"])
        diff = "\n".join(difflib.unified_diff(b, a, "before", "after", lineterm="", n=1))
        head = [f"REQUEST: {pk['request']}"]
        if pk.get("ui_state"):
            head.append("UI STATE:\n" + pk["ui_state"])
        head.append(f"RUN: status={res.get('status')} exit={res.get('exit_code')}; stderr tail: {res.get('stderr_tail', '')[-300:]!r}")
        head.append(f"FILE: {e['file']}")
        head.append("DIFF (uncapped, content level):")
        with open(os.path.join(VIEW, c + ".txt"), "w") as fh:
            fh.write("\n".join(head) + "\n" + (diff if diff else "NO CONTENT CHANGE") + "\n")
        print(c, "view", len(b), "->", len(a), "lines; diff", len(diff), "chars")


if __name__ == "__main__":
    main(sys.argv[1:])
