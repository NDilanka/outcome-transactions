"""Cell values and properties read straight from the xlsx XML, for the second-method agreement check.

No COM and no openpyxl are used here, so a file from either writer is read by the same third reader.
Properties: value, formula text, number format (by code), bold, fill colour, merged, and column width.
"""
import xml.etree.ElementTree as ET
import zipfile

from xlsx_edit import col_index, col_name, split_ref

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
SS_NS = NS
BUILTIN_FORMATS = {0: "General", 1: "0", 2: "0.00", 3: "#,##0", 4: "#,##0.00", 9: "0%", 10: "0.00%"}
CELL_PROPS = ("value", "formula", "numfmt", "bold", "fill", "merged")
EMPTY = dict(value=None, formula=None, numfmt="General", bold=False, fill=None, merged=False)


def _children(root, parent, child):
    el = root.find(NS + parent)
    return el.findall(NS + child) if el is not None else []


def _flag(el):
    return el is not None and el.get("val", "1") not in ("0", "false")


def _fill_key(fill):
    pf = fill.find(NS + "patternFill")
    if pf is None or pf.get("patternType") in (None, "none"):
        return None
    fg = pf.find(NS + "fgColor")
    if fg is None:
        return pf.get("patternType")
    if fg.get("rgb"):
        return fg.get("rgb")[-6:].upper()
    return "theme" + str(fg.get("theme"))


def _styles(z):
    if "xl/styles.xml" not in z.namelist():
        return {}, [], [], []
    root = ET.fromstring(z.read("xl/styles.xml"))
    numfmts = {int(n.get("numFmtId")): n.get("formatCode") for n in root.iter(NS + "numFmt")}
    fonts = [_flag(f.find(NS + "b")) for f in _children(root, "fonts", "font")]
    fills = [_fill_key(f) for f in _children(root, "fills", "fill")]
    xfs = [(int(x.get("numFmtId", "0")), int(x.get("fontId", "0")), int(x.get("fillId", "0")))
           for x in _children(root, "cellXfs", "xf")]
    return numfmts, fonts, fills, xfs


def _shared_strings(z):
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.iter(SS_NS + "t")) for si in root.findall(SS_NS + "si")]


def _value(c, strings):
    t = c.get("t")
    if t == "inlineStr":
        return "".join(x.text or "" for x in c.iter(NS + "t"))
    v = c.find(NS + "v")
    if v is None or v.text is None:
        return None
    if t == "s":
        return strings[int(v.text)]
    return v.text if t in ("str", "e") else float(v.text)


def _range_refs(ref):
    a, _, b = ref.partition(":")
    c1, r1 = split_ref(a)
    c2, r2 = split_ref(b or a)
    return {f"{col_name(c)}{r}" for c in range(col_index(c1), col_index(c2) + 1)
            for r in range(r1, r2 + 1)}


def read_props(path):
    """{'cells': {ref: props}, 'col_width': {column: width}} for the first worksheet."""
    with zipfile.ZipFile(path) as z:
        strings = _shared_strings(z)
        numfmts, fonts, fills, xfs = _styles(z)
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    merged = set()
    for m in sheet.iter(NS + "mergeCell"):
        merged |= _range_refs(m.get("ref"))
    cells = {}
    for c in sheet.iter(NS + "c"):
        ref = c.get("r")
        nf, font, fill = xfs[int(c.get("s", "0"))] if int(c.get("s", "0")) < len(xfs) else (0, 0, 0)
        f = c.find(NS + "f")
        cells[ref] = dict(
            value=_value(c, strings),
            formula=(f.text or "") if f is not None else None,
            numfmt=numfmts.get(nf, BUILTIN_FORMATS.get(nf, f"builtin:{nf}")),
            bold=fonts[font] if font < len(fonts) else False,
            fill=fills[fill] if fill < len(fills) else None,
            merged=ref in merged,
        )
    for ref in merged - set(cells):
        cells[ref] = dict(EMPTY, merged=True)
    widths = {}
    for col in sheet.iter(NS + "col"):
        for i in range(int(col.get("min")), int(col.get("max")) + 1):
            widths[col_name(i)] = round(float(col.get("width")), 2)
    return dict(cells=cells, col_width=widths)


def _order(ref):
    col, row = split_ref(ref)
    return row, col_index(col)


def compare_props(a, b):
    """Differences between two read_props results, as {property: [(where, a, b)]}. Empty means agreement."""
    diffs = {p: [] for p in CELL_PROPS}
    for ref in sorted(set(a["cells"]) | set(b["cells"]), key=_order):
        ca, cb = a["cells"].get(ref, EMPTY), b["cells"].get(ref, EMPTY)
        for p in CELL_PROPS:
            if ca[p] != cb[p]:
                diffs[p].append((ref, ca[p], cb[p]))
    diffs["col_width"] = [(c, a["col_width"].get(c), b["col_width"].get(c))
                          for c in sorted(set(a["col_width"]) | set(b["col_width"]))
                          if a["col_width"].get(c) != b["col_width"].get(c)]
    return {p: rows for p, rows in diffs.items() if rows}
