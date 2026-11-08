#!/usr/bin/env python3
"""Reader checks for the cases a second validator round found. Each FAIL is a silent wrong commit or a missed
change. Workbooks for label cases are made by LibreOffice (as the prototype's own files are); the rest are
hand-built content.xml packages. Run: python3 check_readers.py (needs soffice on PATH)."""
import os, sys, shutil, subprocess, tempfile, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import readers as R
import spec as SP

NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
      'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
      'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
      'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
      'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
      'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"')
WORK = tempfile.mkdtemp(prefix="check_readers_")
PROFILE = "file://" + os.path.join(WORK, "lo_profile")

def sv(t): return f'<table:table-cell office:value-type="string"><text:p>{t}</text:p></table:table-cell>'
def fv(v): return f'<table:table-cell office:value-type="float" office:value="{v}"><text:p>{v}</text:p></table:table-cell>'
def row(*cells): return '<table:table-row>' + ''.join(cells) + '</table:table-row>'
def table(name, rows): return f'<table:table table:name="{name}">' + ''.join(rows) + '</table:table>'
HDR = row(sv("Item"), sv("Q1"), sv("Q2"), sv("Q3"))

def zip_ods(name, content, styles=""):
    """A content.xml package, read by the parser only (no LibreOffice needed)."""
    path = os.path.join(WORK, name)
    doc = (f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {NS} office:version="1.3">'
           f'{styles}<office:body><office:spreadsheet>{content}</office:spreadsheet></office:body></office:document-content>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.spreadsheet", compress_type=zipfile.ZIP_STORED)
        z.writestr("content.xml", doc)
    return path

def lo_ods(name, sheets_xml):
    """A workbook saved by LibreOffice from a flat ODS, the same way the prototype's own files are made."""
    fods = os.path.join(WORK, name + ".fods")
    open(fods, "w").write(f'<?xml version="1.0" encoding="UTF-8"?><office:document {NS} office:version="1.3" '
                          f'office:mimetype="application/vnd.oasis.opendocument.spreadsheet">'
                          f'<office:body><office:spreadsheet>{sheets_xml}</office:spreadsheet></office:body></office:document>')
    r = subprocess.run(["soffice", f"-env:UserInstallation={PROFILE}", "--headless", "--convert-to", "ods", "--outdir", WORK, fods],
                       capture_output=True, text=True, timeout=180)
    out = os.path.join(WORK, name + ".ods")
    if r.returncode or not os.path.exists(out): raise RuntimeError(f"soffice could not build {name}: {r.stderr[-200:]}")
    return out

RESULTS = []
def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f" | {detail}"), flush=True)

# A. The parser must see every cell, and changes it cannot see are a missed change.
ten_wide = zip_ods("ten_wide.ods", table("Q3", [HDR, row(
    '<table:table-cell table:number-columns-repeated="1001" office:value-type="float" office:value="7"><text:p>7</text:p></table:table-cell>')]))
check("A1 a populated repeat of 1001 cells keeps its last cell",
      f"Q3!{R.col_name(1000)}2" in R.all_cells(ten_wide), "the 1001st column is cut at 1000")

dup_a = zip_ods("dup_sheet_a.ods", table("Q3", [HDR]) + table("Other", [row(fv(7))]) + table("Other", [row(fv(9))]))
dup_b = zip_ods("dup_sheet_b.ods", table("Q3", [HDR]) + table("Other", [row(fv(8))]) + table("Other", [row(fv(9))]))
try:
    seen = bool(R.changed_cells(dup_a, dup_b))
except ValueError:
    seen = True  # refusing a workbook with duplicate sheet names is also acceptable
check("A2 a change on the first of two sheets named Other is seen or refused", seen, "all_cells keeps only the last sheet")

# B. The fingerprint covers what a method can change without changing the displayed value.
def cell_row(*cells): return row(*cells)
def with_formula(f): return f'<table:table-cell table:formula="{f}" office:value-type="float" office:value="3"><text:p>3</text:p></table:table-cell>'
f1 = zip_ods("formula_a.ods", table("Q3", [HDR, cell_row(sv("item1"), fv(3), fv(4), fv(5), with_formula("of:=1+2"))]))
f2 = zip_ods("formula_b.ods", table("Q3", [HDR, cell_row(sv("item1"), fv(3), fv(4), fv(5), with_formula("of:=3"))]))
check("B1 a formula change with the same value is a change", R.changed_cells(f1, f2), "table:formula is not in the fingerprint")

t1 = zip_ods("time_a.ods", table("Q3", [HDR, cell_row(sv("item1"), fv(3), '<table:table-cell office:value-type="time" office:time-value="PT1H"/>')]))
t2 = zip_ods("time_b.ods", table("Q3", [HDR, cell_row(sv("item1"), fv(3), '<table:table-cell office:value-type="time" office:time-value="PT2H"/>')]))
check("B2 a time value without displayed text is a change", R.changed_cells(t1, t2), "office:time-value is not read")

c1 = zip_ods("cur_a.ods", table("Q3", [HDR, cell_row(sv("item1"), fv(3), '<table:table-cell office:value-type="currency" office:value="5" office:currency="EUR"/>')]))
c2 = zip_ods("cur_b.ods", table("Q3", [HDR, cell_row(sv("item1"), fv(3), '<table:table-cell office:value-type="currency" office:value="5" office:currency="USD"/>')]))
check("B3 a currency change with the same amount is a change", R.changed_cells(c1, c2), "office:currency is not in the fingerprint")

same = zip_ods("same_a.ods", table("Q3", [HDR, cell_row(sv("item1"), fv(3))]))
check("B0 an identical copy has no change (control)", not R.changed_cells(same, same))

# C and D. Anchor labels: what the user sees must decide the target, and a label the parser cannot read is a refusal.
book = lo_ods("labels", (
    table("List", [HDR, row(sv("1."), fv(3)), row(sv("placeholder"), fv(4))]) +
    table("Space", [HDR, row(sv(" R "), fv(3)), row(sv("R"), fv(4))]) +
    table("Span", [row(sv("Item"), '<table:table-cell table:number-columns-spanned="2" office:value-type="string"><text:p>Q1</text:p></table:table-cell>'
                       '<table:covered-table-cell/>', sv("Q3")), row(sv("item1"), fv(3), fv(4), fv(5))]) +
    table("Pos", [HDR, row(sv("item1"), fv(3)), row(sv("item2"), fv(4))])))
# LibreOffice drops a list paragraph when it loads a cell, so the list is written into the saved file (the first sheet).
R.ods_replace_cell(book, "A3", '<table:table-cell office:value-type="string"><text:list text:style-name="L"><text:list-item><text:p/></text:list-item></text:list></table:table-cell>')
def target_of(sheet): return R.find_anchor(book, R.anchor_of(book, f"{sheet}!B2"))
check("C1 a label that differs only in spaces is a duplicate", target_of("Space") is None, f"resolved to {target_of('Space')}")
check("C2 a label whose number is a list marker is refused", target_of("List") is None, f"resolved to {target_of('List')}")
check("D1 a header merged over two columns is refused", target_of("Span") is None, f"resolved to {target_of('Span')}")
check("D0 unique labels resolve to their cell (control)", target_of("Pos") == "Pos!B2", f"resolved to {target_of('Pos')}")
merged_label = lo_ods("merged_label", table("MergeL", [HDR, row(sv("item1"), fv(3)), row(sv("item2"), fv(4))]))
R.ods_replace_cell(merged_label, "A2", '<table:table-cell table:number-rows-spanned="2" office:value-type="string"><text:p>item1</text:p></table:table-cell>')
R.ods_replace_cell(merged_label, "A3", '<table:covered-table-cell/>')
check("D2 a label merged over two rows is refused", R.find_anchor(merged_label, R.anchor_of(merged_label, "MergeL!B2")) is None,
      f"resolved to {R.find_anchor(merged_label, R.anchor_of(merged_label, 'MergeL!B2'))}")
merged_away = lo_ods("merged_away", table("MergeA", [HDR, row(sv("item1"), fv(3)), row(sv("item2"), fv(4), fv(5), fv(6))]))
R.ods_replace_cell(merged_away, "C3", '<table:table-cell table:number-columns-spanned="2" office:value-type="float" office:value="5"><text:p>5</text:p></table:table-cell>')
R.ods_replace_cell(merged_away, "D3", '<table:covered-table-cell/>')
check("D3 a merge in another row and column leaves the anchor (control)", R.find_anchor(merged_away, R.anchor_of(merged_away, "MergeA!B2")) == "MergeA!B2",
      f"resolved to {R.find_anchor(merged_away, R.anchor_of(merged_away, 'MergeA!B2'))}")
# Labels that LibreOffice shows alike but the file stores differently: the displayed text decides.
shown_value = lo_ods("shown_value", table("Shown", [HDR, row(sv("p"), fv(3)), row(sv("q"), fv(4))]))
R.ods_replace_cell(shown_value, "A2", '<table:table-cell office:value-type="float" office:value="1.0"><text:p>1</text:p></table:table-cell>')
R.ods_replace_cell(shown_value, "A3", '<table:table-cell office:value-type="float" office:value="1"><text:p>1</text:p></table:table-cell>')
check("C3 a stored 1.0 and a stored 1 that both show as 1 are a duplicate", R.find_anchor(shown_value, R.anchor_of(shown_value, "Shown!B2")) is None,
      f"resolved to {R.find_anchor(shown_value, R.anchor_of(shown_value, 'Shown!B2'))}")
footnote = lo_ods("footnote", table("Note", [HDR, row(sv("p"), fv(3)), row(sv("q"), fv(4))]))
R.ods_replace_cell(footnote, "A2", '<table:table-cell office:value-type="string"><text:p>R<text:note text:id="ftn1" text:note-class="footnote"><text:note-citation>1</text:note-citation><text:note-body><text:p>one</text:p></text:note-body></text:note></text:p></table:table-cell>')
R.ods_replace_cell(footnote, "A3", '<table:table-cell office:value-type="string"><text:p>R<text:note text:id="ftn2" text:note-class="footnote"><text:note-citation>2</text:note-citation><text:note-body><text:p>two</text:p></text:note-body></text:note></text:p></table:table-cell>')
check("C4 labels that differ only in a footnote body are a duplicate as shown", R.find_anchor(footnote, R.anchor_of(footnote, "Note!B2")) is None,
      f"resolved to {R.find_anchor(footnote, R.anchor_of(footnote, 'Note!B2'))}")

# E. An external-reference cache table in the file is not a sheet to LibreOffice, so it must not shift which sheet is read.
def ods_prepend_table(path, table_xml):
    """Put a table ahead of the first sheet in content.xml, where a file with external references keeps its cache tables."""
    items, root = R._load_content(path)
    first = next(root.iter(R.T + "table"))
    parent = {c: p for p in root.iter() for c in p}[first]
    parent.insert(list(parent).index(first), R._fragment(table_xml)[0])
    R._save_content(path, items, root)
CACHE = "'file:///tmp/e.ods'#S"
ext_dup = lo_ods("ext_dup", table("Q3", [HDR, row(sv("x"), fv(3)), row(sv("y"), fv(4))]) + table("Other", [HDR, row(sv("1.0"), fv(3)), row(sv("1"), fv(4))]))
R.ods_replace_cell(ext_dup, "A2", '<table:table-cell office:value-type="float" office:value="1.0"><text:p>1</text:p></table:table-cell>')
R.ods_replace_cell(ext_dup, "A3", '<table:table-cell office:value-type="float" office:value="1"><text:p>1</text:p></table:table-cell>')
ods_prepend_table(ext_dup, table(CACHE, [row(sv("cached"))]))
check("E1 a label shown twice on the named sheet is a duplicate, whatever another sheet holds",
      R.anchor_of(ext_dup, "Q3!B2") == ("Q3", "1", "Q1") and R.find_anchor(ext_dup, R.anchor_of(ext_dup, "Q3!B2")) is None,
      f"anchor {R.anchor_of(ext_dup, 'Q3!B2')}, resolved to {R.find_anchor(ext_dup, R.anchor_of(ext_dup, 'Q3!B2'))}")
ext_ok = lo_ods("ext_ok", table("Q3", [HDR, row(sv("p"), fv(3)), row(sv("q"), fv(4))]) + table("Other", [HDR, row(sv("x"), fv(3)), row(sv("y"), fv(4))]))
ods_prepend_table(ext_ok, table(CACHE, [row(sv("cached"))]))
check("E2 a unique label on the named sheet resolves there, past an external cache table",
      R.find_anchor(ext_ok, R.anchor_of(ext_ok, "Q3!B2")) == "Q3!B2",
      f"anchor {R.anchor_of(ext_ok, 'Q3!B2')}, resolved to {R.find_anchor(ext_ok, R.anchor_of(ext_ok, 'Q3!B2'))}")

# F. A workbook the reader cannot parse (a truncated save) is a refusal from the spec wrapper, whatever the exception type.
f_before, f_after = os.path.join(WORK, "f_before"), os.path.join(WORK, "f_after")
os.makedirs(f_before); os.makedirs(f_after)
shutil.copy(lo_ods("f_base", table("Q3", [HDR, row(sv("item1"), fv(3))])), os.path.join(f_before, "budget.ods"))
open(os.path.join(f_after, "budget.ods"), "wb").write(b"not a zip file")
F_SPEC = {"must": [("ods_cell", "budget.ods", "Q3!B2", "==", 3)], "footprint": ["budget.ods"], "preserve": []}
try:
    ok, reasons, _ = SP.evaluate(F_SPEC, f_before, f_after)
    check("F1 an unreadable workbook is refused by the spec wrapper", not ok and any(r.startswith("refused") for r in reasons),
          f"ok {ok}, reasons {reasons[:2]}")
except Exception as ex:
    check("F1 an unreadable workbook is refused by the spec wrapper", False, f"raised {type(ex).__name__}: {ex}")
try:
    d = SP.semantic_diff(f_before, f_after, F_SPEC)
    check("F2 the outcome summary of an unreadable workbook says so", "unreadable" in d, f"got {d}")
except Exception as ex:
    check("F2 the outcome summary of an unreadable workbook says so", False, f"raised {type(ex).__name__}: {ex}")

shutil.rmtree(WORK, ignore_errors=True)
failed = [n for n, ok in RESULTS if not ok]
print(f"{len(RESULTS) - len(failed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
