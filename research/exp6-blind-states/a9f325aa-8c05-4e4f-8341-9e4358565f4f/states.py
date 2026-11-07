import os
import shutil
import zipfile
from lxml import etree
import openpyxl

REL_PATH = os.path.join("home", "user", "Movie_title_garbage_clean.xlsx")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def _patch_cached_values(xlsx_path, sheet_xml_name, cell_values):
    with zipfile.ZipFile(xlsx_path, "r") as zin:
        entries = [(info, zin.read(info.filename)) for info in zin.infolist()]
    with zipfile.ZipFile(xlsx_path, "w") as zout:
        for info, data in entries:
            if info.filename == sheet_xml_name:
                root = etree.fromstring(data)
                ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for coord, val in cell_values.items():
                    for c in root.xpath(f"//s:c[@r='{coord}']", namespaces=ns):
                        c.set("t", "str")
                        v_nodes = c.xpath("s:v", namespaces=ns)
                        v_el = v_nodes[0] if v_nodes else etree.SubElement(
                            c, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v"
                        )
                        v_el.text = str(val)
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
            zout.writestr(info, data)


def _clean_title(raw):
    return " ".join(str(raw).split()).title()


def _clean_word_cap(raw):
    return " ".join(w.capitalize() for w in str(raw).split())


def correct_static_clean_titles(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    for r in range(2, 30):
        raw = ws.cell(r, 2).value
        ws.cell(r, 3).value = _clean_title(raw)
    wb.save(xlsx_path)


def correct_formula_proper_trim(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    cached = {}
    for r in range(2, 30):
        raw = ws.cell(r, 2).value
        ws.cell(r, 3).value = f"=PROPER(TRIM(B{r}))"
        cached[f"C{r}"] = _clean_word_cap(raw)
    wb.save(xlsx_path)
    _patch_cached_values(xlsx_path, "xl/worksheets/sheet1.xml", cached)


def wrong_overwrite_source_column(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    for r in range(2, 30):
        raw = ws.cell(r, 2).value
        ws.cell(r, 2).value = _clean_title(raw)
    wb.save(xlsx_path)


def wrong_sentence_case_only(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    for r in range(2, 30):
        raw = ws.cell(r, 2).value
        ws.cell(r, 3).value = " ".join(str(raw).split()).capitalize()
    wb.save(xlsx_path)


def wrong_redundant_spaces_kept(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    for r in range(2, 30):
        raw = str(ws.cell(r, 2).value)
        ws.cell(r, 3).value = raw.title()
    wb.save(xlsx_path)


def wrong_partial_half_rows(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    for r in range(2, 16):
        raw = ws.cell(r, 2).value
        ws.cell(r, 3).value = _clean_title(raw)
    wb.save(xlsx_path)


def wrong_irrelevant_region_touched(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    ws.cell(1, 1).value = "Index"
    for r in range(2, 30):
        raw = ws.cell(r, 2).value
        ws.cell(r, 3).value = _clean_title(raw)
        ws.cell(r, 1).value = r - 1
    wb.save(xlsx_path)
