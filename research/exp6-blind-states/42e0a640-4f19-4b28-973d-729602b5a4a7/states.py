import os
import shutil
import zipfile
from lxml import etree
import openpyxl

REL_PATH = os.path.join("home", "user", "NetIncome.xlsx")

TOTAL_REV = 867786
TOTAL_EXP = 411686


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def _patch_cached_numbers(xlsx_path, sheet_xml_name, cell_values):
    with zipfile.ZipFile(xlsx_path, "r") as zin:
        entries = [(info, zin.read(info.filename)) for info in zin.infolist()]
    with zipfile.ZipFile(xlsx_path, "w") as zout:
        for info, data in entries:
            if info.filename == sheet_xml_name:
                root = etree.fromstring(data)
                ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for coord, val in cell_values.items():
                    for c in root.xpath(f"//s:c[@r='{coord}']", namespaces=ns):
                        if "t" in c.attrib:
                            del c.attrib["t"]
                        v_nodes = c.xpath("s:v", namespaces=ns)
                        v_el = v_nodes[0] if v_nodes else etree.SubElement(
                            c, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v"
                        )
                        v_el.text = str(val)
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
            zout.writestr(info, data)


def correct_sum_formulas_on_sheet2(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws2 = wb.create_sheet("Sheet2")
    ws2["A1"] = "Total Revenue"
    ws2["B1"] = "Total Expenses"
    ws2["A2"] = "=SUM(Sheet1!A2:A20)"
    ws2["B2"] = "=SUM(Sheet1!B2:B20)"
    wb.save(xlsx_path)
    _patch_cached_numbers(
        xlsx_path,
        "xl/worksheets/sheet2.xml",
        {"A2": TOTAL_REV, "B2": TOTAL_EXP},
    )


def correct_static_sums_on_sheet2(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws2 = wb.create_sheet("Sheet2")
    ws2["A1"] = "Total Revenue"
    ws2["B1"] = "Total Expenses"
    ws2["A2"] = TOTAL_REV
    ws2["B2"] = TOTAL_EXP
    ws2["A2"].number_format = "#,##0"
    ws2["B2"].number_format = "#,##0"
    wb.save(xlsx_path)


def wrong_sums_placed_on_sheet1(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws1 = wb["Sheet1"]
    ws1["A21"] = TOTAL_REV
    ws1["B21"] = TOTAL_EXP
    wb.save(xlsx_path)


def wrong_swapped_column_values(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws2 = wb.create_sheet("Sheet2")
    ws2["A1"] = "Total Revenue"
    ws2["B1"] = "Total Expenses"
    ws2["A2"] = TOTAL_EXP
    ws2["B2"] = TOTAL_REV
    wb.save(xlsx_path)


def wrong_wrong_column_header_revenue(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws2 = wb.create_sheet("Sheet2")
    ws2["A1"] = "Revenue"
    ws2["B1"] = "Expenses"
    ws2["A2"] = TOTAL_REV
    ws2["B2"] = TOTAL_EXP
    wb.save(xlsx_path)


def wrong_off_by_one_missed_last_row(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws2 = wb.create_sheet("Sheet2")
    ws2["A1"] = "Total Revenue"
    ws2["B1"] = "Total Expenses"
    ws2["A2"] = TOTAL_REV - 58782
    ws2["B2"] = TOTAL_EXP - 25706
    wb.save(xlsx_path)


def wrong_sheet1_deleted(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws2 = wb.create_sheet("Sheet2")
    ws2["A1"] = "Total Revenue"
    ws2["B1"] = "Total Expenses"
    ws2["A2"] = TOTAL_REV
    ws2["B2"] = TOTAL_EXP
    del wb["Sheet1"]
    wb.save(xlsx_path)
