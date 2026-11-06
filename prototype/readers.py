"""State readers and ODS editing for the outcome-transaction prototype."""
import zipfile, re, io, os, hashlib, subprocess, shutil
import xml.etree.ElementTree as ET

NS = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
T = "{%s}" % NS["table"]; O = "{%s}" % NS["office"]; X = "{%s}" % NS["text"]

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

def ods_cells(path, sheet=None):
    """Return {ref: (value, formatting)} for non-empty cells of the first (or named) sheet."""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("content.xml"))
    sprops = _style_props(root)
    tables = list(root.iter(T + "table"))
    table = next((t for t in tables if t.get(T + "name") == sheet), tables[0])
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
            val = cell.get(O + "value")
            if val is None:
                txt = "".join("".join(p.itertext()) for p in cell.iter(X + "p"))
                val = txt if txt else None
            sname = cell.get(T + "style-name") or row.get(T + "default-cell-style-name")
            style = sprops.get(sname, (sname, False, ()))[2] if sname else ()
            cells.append((c, crep, val, style))
            c += crep
        if rrep > 1000:
            r += rrep
            continue
        for k in range(rrep):
            for c0, crep, val, style in cells:
                if val is None:
                    continue
                for j in range(min(crep, 1000)):
                    out[f"{col_name(c0 + j)}{r + k + 1}"] = (val, style)
        r += rrep
    return out

def ods_set_cell(path, ref, value):
    """Set a numeric cell in place, preserving everything else in the file."""
    rr, cc = ref_to_rc(ref)
    with zipfile.ZipFile(path) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    content = dict((i.filename, d) for i, d in items)["content.xml"]
    _register_ns(content)
    root = ET.fromstring(content)
    table = next(root.iter(T + "table"))
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
            cell.set(O + "value-type", "float")
            cell.set(O + "value", str(value))
            for p in list(cell):
                if p.tag == X + "p":
                    cell.remove(p)
            p = ET.SubElement(cell, X + "p"); p.text = str(value)
            break
        c += crep
    new = ET.tostring(root, xml_declaration=True, encoding="UTF-8")
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w") as z:
        for info, data in items:
            if info.filename == "content.xml":
                data = new
            ct = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            z.writestr(info.filename, data, compress_type=ct)
    os.replace(tmp, path)

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
