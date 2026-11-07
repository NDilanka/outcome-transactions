"""State readers and ODS editing for the outcome-transaction prototype."""
import zipfile, re, io, os, hashlib, subprocess, shutil, copy
import xml.etree.ElementTree as ET

NS = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
T = "{%s}" % NS["table"]; O = "{%s}" % NS["office"]; X = "{%s}" % NS["text"]
MAX_COLUMNS = 16384  # the widest sheet a spreadsheet application writes

def col_name(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s

def ref_to_rc(ref):
    m = re.fullmatch(r"([A-Z]+)(\d+)", ref)
    c = 0
    for ch in m.group(1):
        c = c * 26 + ord(ch) - 64
    return int(m.group(2)) - 1, c - 1

def _register_ns(xml_bytes):
    for _, (prefix, uri) in ET.iterparse(io.BytesIO(xml_bytes), events=["start-ns"]):
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            pass

def _rows(table):
    return [r for r in table.iter(T + "table-row")]

S = "{urn:oasis:names:tc:opendocument:xmlns:style:1.0}"

def _style_props(root):
    """Resolve automatic cell style names to their formatting properties, so renamed styles compare equal."""
    props = {}
    for st in root.iter(S + "style"):
        kv = []
        for child in st:
            if child.tag in (S + "text-properties", S + "table-cell-properties", S + "paragraph-properties"):
                kv += [(child.tag.split("}")[1] + ":" + k.split("}")[-1], v) for k, v in child.attrib.items()]
        props[st.get(S + "name")] = (st.get(S + "parent-style-name"), st.get(S + "data-style-name") is not None, tuple(sorted(kv)))
    return props

def _cached(cell):
    """The value a cell stores in an attribute (number, date, boolean or string), or None. A string cell may have no text."""
    for a in ("value", "date-value", "boolean-value", "string-value"):
        if cell.get(O + a):
            return cell.get(O + a)
    return None

DRAW = "{urn:oasis:names:tc:opendocument:xmlns:drawing:1.0}"
SKIP = (O + "annotation", O + "annotation-end")

def _collapse(s):
    """ODF collapses each run of whitespace in a text node to one space. Spaces that count are text:s elements."""
    return re.sub(r"[ \t\r\n]+", " ", s)

def _inline(el):
    """The text of one paragraph: text:s is a run of spaces, text:tab a tab, text:line-break a newline."""
    out = [_collapse(el.text or "")]
    for ch in el:
        if ch.tag == X + "s":
            out.append(" " * int(ch.get(X + "c", "1")))
        elif ch.tag == X + "tab":
            out.append("\t")
        elif ch.tag == X + "line-break":
            out.append("\n")
        elif ch.tag not in SKIP and not ch.tag.startswith(DRAW):
            out.append(_inline(ch))
        out.append(_collapse(ch.tail or ""))
    return "".join(out)

def _paragraphs(el):
    """The paragraphs of a cell's content. Annotations (comments) and drawn shapes are not cell text."""
    for ch in el:
        if ch.tag in SKIP or ch.tag.startswith(DRAW):
            continue
        if ch.tag in (X + "p", X + "h"):
            yield ch
        else:
            yield from _paragraphs(ch)

def _text(cell):
    """A cell's text, paragraphs joined by newlines, or "" if every paragraph is empty."""
    texts = [_inline(p) for p in _paragraphs(cell)]
    return "\n".join(texts) if any(texts) else ""

def _root(path):
    with zipfile.ZipFile(path) as z:
        return ET.fromstring(z.read("content.xml"))

def _table(root, sheet=None):
    """The named sheet, which must occur once in the workbook. With no name, the first sheet: a fixture default
    that the checks never use."""
    tables = list(root.iter(T + "table"))
    if sheet is None:
        return tables[0]
    named = [t for t in tables if t.get(T + "name") == sheet]
    if len(named) != 1:
        raise ValueError(f"sheet {sheet!r} occurs {len(named)} times")
    return named[0]

def ods_cells(path, sheet):
    """{ref: (value, formatting)} for the non-empty cells of one named sheet."""
    root = _root(path)
    return _sheet_cells(_table(root, sheet), _style_props(root))

def all_cells(path):
    """{'Sheet!REF': (value, formatting)} over every sheet. A cell's identity includes its sheet. Two sheets with
    one name would share keys, so the workbook is refused instead."""
    root = _root(path)
    sprops = _style_props(root)
    names = [t.get(T + "name") for t in root.iter(T + "table")]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup: raise ValueError(f"sheet name {dup[0]!r} is used more than once")
    return {f"{t.get(T + 'name')}!{ref}": v for t in root.iter(T + "table") for ref, v in _sheet_cells(t, sprops).items()}

def _sheet_cells(table, sprops):
    out = {}
    r = 0
    for row in table.iter(T + "table-row"):
        rrep = int(row.get(T + "number-rows-repeated", "1"))
        c = 0
        cells = []
        for cell in row:
            if cell.tag not in (T + "table-cell", T + "covered-table-cell"):
                continue
            crep = int(cell.get(T + "number-columns-repeated", "1"))
            val = _cached(cell)
            if val is None:
                val = _text(cell) or None
            sname = cell.get(T + "style-name") or row.get(T + "default-cell-style-name")
            style = sprops.get(sname, (sname, False, ()))[2] if sname else ()
            cells.append((c, crep, val, style))
            c += crep
        # Empty rows repeated to the end of the sheet are skipped. A repeated block that holds values is read in full,
        # so duplicate labels in it are seen (an anchor must match exactly one row).
        if rrep > 1000 and not any(val is not None for _, _, val, _ in cells):
            r += rrep
            continue
        for k in range(rrep):
            for c0, crep, val, style in cells:
                if val is None:
                    continue
                if crep > MAX_COLUMNS: raise ValueError(f"a repeated cell spans {crep} columns, more than {MAX_COLUMNS}")
                for j in range(crep):
                    out[f"{col_name(c0 + j)}{r + k + 1}"] = (val, style)
        r += rrep
    return out

def changed_cells(a_path, b_path):
    """Refs whose cell differs between two sheets, over both key sets; an absent cell is None."""
    ca, cb = all_cells(a_path), all_cells(b_path)
    return {k for k in set(ca) | set(cb) if ca.get(k) != cb.get(k)}

def ods_set_cell(path, ref, value, sheet=None):
    """Set a numeric cell in place, or clear it when value is None; everything else in the file is preserved."""
    rr, cc = ref_to_rc(ref)
    with zipfile.ZipFile(path) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    content = dict((i.filename, d) for i, d in items)["content.xml"]
    _register_ns(content)
    root = ET.fromstring(content)
    table = _table(root, sheet)
    r = 0
    target_row = None
    for row in list(table.iter(T + "table-row")):
        rrep = int(row.get(T + "number-rows-repeated", "1"))
        if r <= rr < r + rrep:
            target_row = row
            if rrep > 1:
                raise ValueError("repeated row split not supported in prototype")
            break
        r += rrep
    c = 0
    for idx, cell in enumerate(list(target_row)):
        crep = int(cell.get(T + "number-columns-repeated", "1"))
        if c <= cc < c + crep:
            if crep > 1:
                before, after = cc - c, c + crep - cc - 1
                parent = target_row
                pos = list(parent).index(cell)
                parent.remove(cell)
                parts = []
                import copy
                if before: b = copy.deepcopy(cell); b.set(T + "number-columns-repeated", str(before)); parts.append(b)
                mid = copy.deepcopy(cell); mid.attrib.pop(T + "number-columns-repeated", None); parts.append(mid)
                if after: a = copy.deepcopy(cell); a.set(T + "number-columns-repeated", str(after)); parts.append(a)
                for k, p in enumerate(parts):
                    parent.insert(pos + k, p)
                cell = mid
            for p in list(cell):
                if p.tag == X + "p":
                    cell.remove(p)
            if value is None:
                cell.attrib.pop(O + "value-type", None); cell.attrib.pop(O + "value", None)
            else:
                cell.set(O + "value-type", "float")
                cell.set(O + "value", str(value))
                p = ET.SubElement(cell, X + "p"); p.text = str(value)
            break
        c += crep
    _save_content(path, items, root)

def _save_content(path, items, root):
    """Write content.xml back in place; every other entry of the zip is copied unchanged."""
    new = ET.tostring(root, xml_declaration=True, encoding="UTF-8")
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w") as z:
        for info, data in items:
            if info.filename == "content.xml":
                data = new
            z.writestr(info, data)
    os.replace(tmp, path)

def ods_insert_row(path, idx):
    """Insert an empty row before row idx (0-based) of the first sheet; the rows below move down one."""
    with zipfile.ZipFile(path) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    content = dict((i.filename, d) for i, d in items)["content.xml"]
    _register_ns(content)
    root = ET.fromstring(content)
    table = next(root.iter(T + "table"))
    parent_of = {c: p for p in root.iter() for c in p}
    r = 0
    for row in list(table.iter(T + "table-row")):
        rrep = int(row.get(T + "number-rows-repeated", "1"))
        if r <= idx < r + rrep:
            if rrep > 1:
                raise ValueError("repeated row split not supported in prototype")
            new = ET.Element(T + "table-row")
            ET.SubElement(new, T + "table-cell", {T + "number-columns-repeated": "1024"})
            parent = parent_of[row]
            parent.insert(list(parent).index(row), new)
            break
        r += rrep
    else:
        raise ValueError(f"row {idx} is past the end of the sheet")
    _save_content(path, items, root)

def anchor_of(path, ref):
    """Name a cell by its sheet, its row label (column A of its row) and its column header (row 1 of its column).
    ref is 'Sheet!B2'."""
    sheet, cell = ref.rsplit("!", 1)
    cells = ods_cells(path, sheet)
    row, col = ref_to_rc(cell)
    return (sheet, cells.get(f"A{row + 1}", (None,))[0], cells.get(f"{col_name(col)}1", (None,))[0])

def find_anchor(path, anchor):
    """The address 'Sheet!B2' of the one cell this anchor names, or None. The sheet must occur once in the workbook
    under its name (a rename, a deletion or a duplicate refuses), and within it the label and the header must each
    occur once. No other sheet is ever used in its place."""
    sheet, label, header = anchor
    if sheet is None or label is None or header is None:
        return None
    root = _root(path)
    if sum(t.get(T + "name") == sheet for t in root.iter(T + "table")) != 1:
        return None
    cells = _sheet_cells(_table(root, sheet), _style_props(root))
    rows = [k[1:] for k, (v, _) in cells.items() if re.fullmatch(r"A\d+", k) and v == label]
    cols = [k[:-1] for k, (v, _) in cells.items() if re.fullmatch(r"[A-Z]+1", k) and v == header]
    if len(rows) != 1 or len(cols) != 1:
        return None
    return f"{sheet}!{cols[0]}{rows[0]}"

def ods_append_block(path, label, count):
    """Append count identical rows, each with label in column A, stored as one repeated row block (what pasting identical rows writes)."""
    with zipfile.ZipFile(path) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    content = dict((i.filename, d) for i, d in items)["content.xml"]
    _register_ns(content)
    root = ET.fromstring(content)
    table = next(root.iter(T + "table"))
    row = ET.SubElement(table, T + "table-row", {T + "number-rows-repeated": str(count)})
    cell = ET.SubElement(row, T + "table-cell", {O + "value-type": "string"})
    ET.SubElement(cell, X + "p").text = label
    _save_content(path, items, root)

def _fragment(xml):
    """Parse XML written with the ODS prefixes, so a test adds rows and cells as content.xml holds them."""
    wrap = f'<w xmlns:table="{NS["table"]}" xmlns:office="{NS["office"]}" xmlns:text="{NS["text"]}">{xml}</w>'
    return list(ET.fromstring(wrap))

def _load_content(path):
    with zipfile.ZipFile(path) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    content = dict((i.filename, d) for i, d in items)["content.xml"]
    _register_ns(content)
    return items, ET.fromstring(content)

def ods_append_rows(path, rows_xml):
    """Append table-row XML after the last row of the first sheet, as a paste of rows does."""
    items, root = _load_content(path)
    next(root.iter(T + "table")).extend(_fragment(rows_xml))
    _save_content(path, items, root)

def ods_replace_cell(path, ref, cell_xml):
    """Replace one cell of the first sheet with table-cell XML. Rows above it and the cell itself must not be repeated."""
    rr, cc = ref_to_rc(ref)
    items, root = _load_content(path)
    rows = list(next(root.iter(T + "table")).iter(T + "table-row"))
    assert all(r.get(T + "number-rows-repeated", "1") == "1" for r in rows[:rr + 1])
    row = rows[rr]
    old = [c for c in row if c.tag == T + "table-cell"][cc]
    assert old.get(T + "number-columns-repeated", "1") == "1"
    row.insert(list(row).index(old), _fragment(cell_xml)[0])
    row.remove(old)
    _save_content(path, items, root)

def ods_copy_sheet_first(path, name):
    """Insert a copy of the first sheet under a new name, ahead of it, as a user who duplicates and moves a sheet does."""
    items, root = _load_content(path)
    parent_of = {c: p for p in root.iter() for c in p}
    first = next(root.iter(T + "table"))
    dup = copy.deepcopy(first)
    dup.set(T + "name", name)
    parent = parent_of[first]
    parent.insert(list(parent).index(first), dup)
    _save_content(path, items, root)

def sheet_names(path):
    """The sheet names of a workbook, in order."""
    return [t.get(T + "name") for t in _root(path).iter(T + "table")]

def ods_rename_sheet(path, old, new):
    """Rename a sheet, as a user does."""
    items, root = _load_content(path)
    named = [t for t in root.iter(T + "table") if t.get(T + "name") == old]
    assert len(named) == 1
    named[0].set(T + "name", new)
    _save_content(path, items, root)

def pdf_text(path):
    return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True).stdout

def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def tree_hashes(root):
    out = {}
    for d, _, files in os.walk(root):
        for f in files:
            p = os.path.join(d, f)
            out[os.path.relpath(p, root)] = sha(p)
    return out
