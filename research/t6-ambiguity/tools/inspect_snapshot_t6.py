"""Read-only inspector: turns a task's starting snapshot into a text report a spec writer can read.
Generic by file type; nothing in here knows about any particular task."""
import os, sys, io, json, zipfile, tarfile, struct, collections
from PIL import Image
import numpy as np

CAP_FILE, CAP_TASK, CAP_TEXT = 14000, 40000, 12000
TEXT_EXT = {".py", ".json", ".md", ".txt", ".html", ".htm", ".sh", ".csv", ".code-workspace", ".js", ".ini", ".xml", ".yaml", ".yml", ".cfg", ".dat"}

def clip(s, n):
    return s if len(s) <= n else s[:n] + f"\n... [truncated, {len(s) - n} more chars]"

def sheet_xlsx(path):
    import openpyxl
    out = []
    wb = openpyxl.load_workbook(path, data_only=False)
    wbv = openpyxl.load_workbook(path, data_only=True)
    for ws in wb.worksheets:
        wv = wbv[ws.title]
        out.append(f"## sheet '{ws.title}' dims={ws.dimensions} state={ws.sheet_state}")
        hid_r = [r for r, d in ws.row_dimensions.items() if d.hidden]
        hid_c = [c for c, d in ws.column_dimensions.items() if d.hidden]
        if hid_r or hid_c: out.append(f"hidden rows={hid_r} hidden cols={hid_c}")
        if ws.merged_cells.ranges: out.append(f"merged={[str(m) for m in ws.merged_cells.ranges]}")
        if getattr(ws, "_charts", None): out.append(f"charts={len(ws._charts)}: " + "; ".join(type(c).__name__ for c in ws._charts))
        if ws.auto_filter and ws.auto_filter.ref: out.append(f"autofilter={ws.auto_filter.ref}")
        if ws.conditional_formatting: out.append(f"conditional_formatting={[str(c.sqref) for c in ws.conditional_formatting]}")
        n = 0
        for row in ws.iter_rows():
            for c in row:
                if c.value is None: continue
                n += 1
                if n > 500: break
                extra = []
                if isinstance(c.value, str) and c.value.startswith("="): extra.append(f"cached={wv[c.coordinate].value!r}")
                if c.number_format != "General": extra.append(f"fmt={c.number_format}")
                if c.font and c.font.b: extra.append("bold")
                if c.font and c.font.i: extra.append("italic")
                if c.fill and c.fill.fgColor and c.fill.fill_type: extra.append(f"fill={c.fill.fgColor.rgb}")
                out.append(f"{c.coordinate}={c.value!r} " + " ".join(extra))
        out.append(f"(non-empty cells: {n})")
    return "\n".join(out)

def sheet_xls(path):
    import xlrd
    wb = xlrd.open_workbook(path); out = []
    for sh in wb.sheets():
        out.append(f"## sheet '{sh.name}' rows={sh.nrows} cols={sh.ncols}")
        for r in range(sh.nrows):
            for c in range(sh.ncols):
                v = sh.cell_value(r, c)
                if v not in ("", None): out.append(f"{xlrd.formula.cellname(r, c)}={v!r}")
    return "\n".join(out)

def docx_report(path):
    import docx
    d = docx.Document(path); out = []
    body = d.element.body
    out.append(f"sections={len(d.sections)} paragraphs={len(d.paragraphs)} tables={len(d.tables)} "
               f"page_breaks={len(body.xpath('.//w:br[@w:type=\"page\"]'))} inline_images={len(d.inline_shapes)}")
    for i, p in enumerate(d.paragraphs):
        fm = set()
        for r in p.runs:
            if r.bold: fm.add("bold")
            if r.italic: fm.add("italic")
            if r.underline: fm.add("underline")
            if r.font.highlight_color: fm.add(f"highlight={r.font.highlight_color}")
            if r.font.color is not None and r.font.color.rgb: fm.add(f"color={r.font.color.rgb}")
            if r.font.size: fm.add(f"size={r.font.size.pt}")
            if r.font.name: fm.add(f"font={r.font.name}")
        out.append(f"p{i} [{p.style.name}{' align=' + str(p.alignment) if p.alignment is not None else ''}] {p.text!r} {sorted(fm) if fm else ''}")
    for ti, t in enumerate(d.tables):
        out.append(f"table{ti} {len(t.rows)}x{len(t.columns)}: " + json.dumps([[c.text for c in r.cells] for r in t.rows]))
    return "\n".join(out)

def odt_report(path):
    from odf.opendocument import load
    from odf import text as T, teletype
    doc = load(path); out = []
    for i, p in enumerate(doc.getElementsByType(T.P) + doc.getElementsByType(T.H)):
        out.append(f"p{i} style={p.getAttribute('stylename')} {teletype.extractText(p)!r}")
    spans = doc.getElementsByType(T.Span)
    styles = collections.Counter(s.getAttribute("stylename") for s in spans)
    out.append(f"spans by style: {dict(styles)}")
    for st in doc.automaticstyles.childNodes:
        if st.getAttribute("name") in styles:
            props = [ (k[1], v) for ch in st.childNodes for k, v in ch.attributes.items()]
            out.append(f"style {st.getAttribute('name')}: {props}")
    return "\n".join(out)

def pptx_report(path):
    from pptx import Presentation
    from pptx.util import Emu
    pr = Presentation(path); out = [f"slides={len(pr.slides)} size={Emu(pr.slide_width).cm:.1f}x{Emu(pr.slide_height).cm:.1f}cm"]
    for si, s in enumerate(pr.slides, 1):
        xml = s._element.xml
        tr = "transition" if "<p:transition" in xml else ""
        out.append(f"## slide {si} layout='{s.slide_layout.name}' {tr}")
        if tr:
            import re
            m = re.search(r"<p:transition.*?</p:transition>|<p:transition[^>]*/>", xml, re.S); out.append("  " + m.group(0))
        for sh in s.shapes:
            pos = f"x={Emu(sh.left or 0).cm:.1f} y={Emu(sh.top or 0).cm:.1f} w={Emu(sh.width or 0).cm:.1f} h={Emu(sh.height or 0).cm:.1f}cm"
            # Google Slides exports photos as freeform shapes with an image fill, not as PICTURE.
            img = " image_fill" if "blipFill" in sh._element.xml else ""
            out.append(f"  shape '{sh.name}' type={sh.shape_type}{img} {pos}")
            if sh.has_text_frame:
                for pi, p in enumerate(sh.text_frame.paragraphs):
                    pxml = p._p.xml
                    bu = "buNone" if "buNone" in pxml else ("buChar" if "buChar" in pxml else ("buAutoNum" if "buAutoNum" in pxml else ""))
                    runs = []
                    for r in p.runs:
                        f = r.font; a = []
                        if f.bold: a.append("b")
                        if f.strikethrough if hasattr(f, "strikethrough") else False: a.append("strike")
                        if "strike=" in r._r.xml: a.append("strike:" + r._r.xml.split('strike="')[1].split('"')[0])
                        try:
                            if f.color and f.color.type is not None and f.color.rgb: a.append(f"color={f.color.rgb}")
                        except Exception: pass
                        runs.append(a)
                    out.append(f"    p{pi} lvl={p.level} {bu} {p.text!r} {runs if any(runs) else ''}")
    return "\n".join(out)

def image_report(path):
    im = Image.open(path); out = [f"image {im.size[0]}x{im.size[1]} mode={im.mode} format={im.format}"]
    a = np.asarray(im.convert("RGB")).astype(float); h, w, _ = a.shape
    out.append(f"mean RGB={a.reshape(-1,3).mean(0).round(1).tolist()}")
    g = [[a[r*h//3:(r+1)*h//3, c*w//3:(c+1)*w//3].reshape(-1,3).mean(0).round(0).astype(int).tolist() for c in range(3)] for r in range(3)]
    out.append(f"3x3 grid mean RGB (rows top->bottom): {g}")
    out.append(f"column thirds mean RGB: {[a[:, c*w//3:(c+1)*w//3].reshape(-1,3).mean(0).round(0).astype(int).tolist() for c in range(3)]}")
    out.append(f"row thirds mean RGB: {[a[r*h//3:(r+1)*h//3].reshape(-1,3).mean(0).round(0).astype(int).tolist() for r in range(3)]}")
    q = (a // 32).astype(int); key = q[..., 0] * 64 + q[..., 1] * 8 + q[..., 2]
    vals, cnt = np.unique(key, return_counts=True)
    for v in vals[np.argsort(-cnt)]:
        ys, xs = np.nonzero(key == v); share = len(xs) / key.size
        rgb = a[key == v].mean(0).round(0).astype(int).tolist()
        out.append(f"color ~{rgb}: {share:.1%} of pixels, bbox x={xs.min()}..{xs.max()} y={ys.min()}..{ys.max()}, centroid=({xs.mean():.0f},{ys.mean():.0f})")
    return "\n".join(out)

def xcf_report(path):
    b = open(path, "rb").read(64)
    if not b.startswith(b"gimp xcf"): return "not an XCF file"
    off = b.index(b"\0") + 1
    w, h, t = struct.unpack(">III", b[off:off+12])
    return f"GIMP XCF {b[:off-1].decode()} canvas {w}x{h} base_type={['RGB','GRAY','INDEXED'][t] if t < 3 else t} (layer details not parsed)"

def pdf_report(path):
    from pypdf import PdfReader
    r = PdfReader(path); t = "\n".join((p.extract_text() or "") for p in r.pages[:5])
    return f"pdf pages={len(r.pages)}\n" + clip(t, 4000)

def archive_report(path, names_and_reader):
    out = []
    entries = list(names_and_reader)
    out.append(f"{len(entries)} entries: " + ", ".join(n for n, _, _ in entries) + "")
    # Config files carry hidden couplings, so they go first; telemetry and crash dumps are skipped.
    prio = lambda n: (0 if os.path.basename(n) in ("prefs.js", "user.js", "msgFilterRules.dat") else 1)
    for n, size, read in sorted(entries, key=lambda e: prio(e[0])):
        if "datareporting" in n or "Crash Reports" in n or "session" in os.path.basename(n): continue
        ext = os.path.splitext(n)[1].lower()
        if (ext in TEXT_EXT or os.path.basename(n) in ("prefs.js", "user.js", "msgFilterRules.dat")) and 0 < size <= 60000:
            try: out.append(f"--- {n} ---\n" + clip(read().decode("utf-8", "replace"), 6000))
            except Exception as e: out.append(f"--- {n}: unreadable {e}")
    return "\n".join(out)

def inspect_file(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".xlsx": return sheet_xlsx(path)
        if ext == ".xls": return sheet_xls(path)
        if ext == ".docx": return docx_report(path)
        if ext == ".odt": return odt_report(path)
        if ext == ".pptx": return pptx_report(path)
        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif"): return image_report(path)
        if ext == ".xcf": return xcf_report(path)
        if ext == ".pdf": return pdf_report(path)
        if ext == ".zip" or path.endswith((".tar.gz", ".tgz", ".tar")):
            global CAP_FILE
            CAP_FILE = 24000
        if ext == ".zip":
            z = zipfile.ZipFile(path)
            return archive_report(path, [(i.filename, i.file_size, (lambda i=i: z.read(i))) for i in z.infolist() if not i.is_dir()])
        if path.endswith((".tar.gz", ".tgz", ".tar")):
            t = tarfile.open(path)
            return archive_report(path, [(m.name, m.size, (lambda m=m: t.extractfile(m).read())) for m in t.getmembers() if m.isfile()])
        if ext in TEXT_EXT or os.path.getsize(path) < 4000:
            return clip(open(path, encoding="utf-8", errors="replace").read(), CAP_TEXT)
        return f"binary {ext} file, {os.path.getsize(path)} bytes (not inspected)"
    except Exception as e:
        return f"inspection failed: {type(e).__name__}: {e}"

def main(snap_root, out_root):
    os.makedirs(out_root, exist_ok=True)
    for tid in sorted(os.listdir(snap_root)):
        root = os.path.join(snap_root, tid); parts = [f"# Starting-state inspection for task {tid}\n(read-only copy of the files the task setup places on the machine)\n"]
        for dp, _, fs in os.walk(root):
            for f in sorted(fs):
                p = os.path.join(dp, f); vp = "/" + os.path.relpath(p, root).replace(os.sep, "/")
                parts.append(f"\n## FILE {vp} ({os.path.getsize(p)} bytes)\n" + clip(inspect_file(p), CAP_FILE))
        open(os.path.join(out_root, tid + ".md"), "w").write(clip("\n".join(parts), CAP_TASK))
        print(tid, sum(len(x) for x in parts))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
