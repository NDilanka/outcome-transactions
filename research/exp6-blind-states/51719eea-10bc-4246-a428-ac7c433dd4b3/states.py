from collections import defaultdict
import os
import shutil
import zipfile
from lxml import etree
import openpyxl

REL_PATH = os.path.join("home", "user", "BoomerangSales.xlsx")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def _get_prices(wb):
    ws_p = wb["Retail Price"]
    return {
        ws_p.cell(r, 1).value: float(ws_p.cell(r, 2).value)
        for r in range(2, ws_p.max_row + 1)
    }


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


def correct_vlookup_and_pivot_sheet(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    prices = _get_prices(wb)
    ws = wb["Sheet1"]
    ws.cell(1, 7, "Revenue")
    sums = defaultdict(float)
    cached_s1 = {}
    for r in range(2, ws.max_row + 1):
        prod = ws.cell(r, 3).value
        qty = float(ws.cell(r, 5).value)
        disc = float(ws.cell(r, 6).value)
        rev = round(prices[prod] * qty * (1.0 - disc), 6)
        ws.cell(r, 7, f"=VLOOKUP(C{r},'Retail Price'!$A$2:$B$23,2,0)*E{r}*(1-F{r})")
        cached_s1[f"G{r}"] = rev
        sums[prod] += rev

    ws2 = wb.create_sheet("Sheet2")
    ws2.cell(1, 1, "Product")
    ws2.cell(1, 2, "Sum - Revenue")
    for idx, prod in enumerate(sorted(sums), start=2):
        ws2.cell(idx, 1, prod)
        ws2.cell(idx, 2, round(sums[prod], 4))
    total_row = len(sums) + 2
    ws2.cell(total_row, 1, "Total Result")
    ws2.cell(total_row, 2, round(sum(sums.values()), 4))
    wb.save(xlsx_path)
    _patch_cached_numbers(xlsx_path, "xl/worksheets/sheet1.xml", cached_s1)


def correct_static_revenue_and_summary(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    prices = _get_prices(wb)
    ws = wb["Sheet1"]
    ws.cell(1, 7, "Revenue")
    sums = defaultdict(float)
    for r in range(2, ws.max_row + 1):
        prod = ws.cell(r, 3).value
        qty = float(ws.cell(r, 5).value)
        disc = float(ws.cell(r, 6).value)
        rev = round(prices[prod] * qty * (1.0 - disc), 4)
        ws.cell(r, 7, rev)
        sums[prod] += rev

    ws2 = wb.create_sheet("Sheet2")
    ws2.cell(1, 1, "Product")
    ws2.cell(1, 2, "Revenue")
    for idx, prod in enumerate(sorted(sums), start=2):
        ws2.cell(idx, 1, prod)
        ws2.cell(idx, 2, round(sums[prod], 4))
    wb.save(xlsx_path)


def wrong_discount_ignored(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    prices = _get_prices(wb)
    ws = wb["Sheet1"]
    ws.cell(1, 7, "Revenue")
    sums = defaultdict(float)
    for r in range(2, ws.max_row + 1):
        prod = ws.cell(r, 3).value
        qty = float(ws.cell(r, 5).value)
        rev = round(prices[prod] * qty, 4)
        ws.cell(r, 7, rev)
        sums[prod] += rev

    ws2 = wb.create_sheet("Sheet2")
    ws2.cell(1, 1, "Product")
    ws2.cell(1, 2, "Revenue")
    for idx, prod in enumerate(sorted(sums), start=2):
        ws2.cell(idx, 1, prod)
        ws2.cell(idx, 2, round(sums[prod], 4))
    wb.save(xlsx_path)


def wrong_multiplied_by_discount_rate(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    prices = _get_prices(wb)
    ws = wb["Sheet1"]
    ws.cell(1, 7, "Revenue")
    sums = defaultdict(float)
    for r in range(2, ws.max_row + 1):
        prod = ws.cell(r, 3).value
        qty = float(ws.cell(r, 5).value)
        disc = float(ws.cell(r, 6).value)
        rev = round(prices[prod] * qty * disc, 4)
        ws.cell(r, 7, rev)
        sums[prod] += rev

    ws2 = wb.create_sheet("Sheet2")
    ws2.cell(1, 1, "Product")
    ws2.cell(1, 2, "Revenue")
    for idx, prod in enumerate(sorted(sums), start=2):
        ws2.cell(idx, 1, prod)
        ws2.cell(idx, 2, round(sums[prod], 4))
    wb.save(xlsx_path)


def wrong_missing_sheet2_summary(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    prices = _get_prices(wb)
    ws = wb["Sheet1"]
    ws.cell(1, 7, "Revenue")
    for r in range(2, ws.max_row + 1):
        prod = ws.cell(r, 3).value
        qty = float(ws.cell(r, 5).value)
        disc = float(ws.cell(r, 6).value)
        ws.cell(r, 7, round(prices[prod] * qty * (1.0 - disc), 4))
    wb.save(xlsx_path)


def wrong_summarized_by_website(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    prices = _get_prices(wb)
    ws = wb["Sheet1"]
    ws.cell(1, 7, "Revenue")
    sums = defaultdict(float)
    for r in range(2, ws.max_row + 1):
        site = ws.cell(r, 2).value
        prod = ws.cell(r, 3).value
        qty = float(ws.cell(r, 5).value)
        disc = float(ws.cell(r, 6).value)
        rev = round(prices[prod] * qty * (1.0 - disc), 4)
        ws.cell(r, 7, rev)
        sums[site] += rev

    ws2 = wb.create_sheet("Sheet2")
    ws2.cell(1, 1, "Web Site")
    ws2.cell(1, 2, "Revenue")
    for idx, site in enumerate(sorted(sums), start=2):
        ws2.cell(idx, 1, site)
        ws2.cell(idx, 2, round(sums[site], 4))
    wb.save(xlsx_path)


def wrong_sheet_named_summary_instead_of_sheet2(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    prices = _get_prices(wb)
    ws = wb["Sheet1"]
    ws.cell(1, 7, "Revenue")
    sums = defaultdict(float)
    for r in range(2, ws.max_row + 1):
        prod = ws.cell(r, 3).value
        qty = float(ws.cell(r, 5).value)
        disc = float(ws.cell(r, 6).value)
        rev = round(prices[prod] * qty * (1.0 - disc), 4)
        ws.cell(r, 7, rev)
        sums[prod] += rev

    ws2 = wb.create_sheet("Summary")
    ws2.cell(1, 1, "Product")
    ws2.cell(1, 2, "Revenue")
    for idx, prod in enumerate(sorted(sums), start=2):
        ws2.cell(idx, 1, prod)
        ws2.cell(idx, 2, round(sums[prod], 4))
    wb.save(xlsx_path)
