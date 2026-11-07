import os
import shutil
import zipfile
from lxml import etree
import openpyxl
from openpyxl.chart import BarChart, LineChart, Reference

REL_PATH = os.path.join("home", "user", "SalesRep.xlsx")

TOTALS = {
    2: 4852,
    3: 4587,
    4: 3943,
    5: 3857,
    6: 4677,
    7: 4243,
}

GROWTHS = {
    3: (4587 - 4852) / 4852,
    4: (3943 - 4587) / 4587,
    5: (3857 - 3943) / 3943,
    6: (4677 - 3857) / 3857,
    7: (4243 - 4677) / 4677,
}


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


def _add_charts(ws, total_title="Total", growth_title="Growth", include_jan_in_growth=False):
    bar = BarChart()
    bar.title = total_title
    bar_data = Reference(ws, min_col=2, min_row=12, max_col=7, max_row=12)
    bar_cats = Reference(ws, min_col=2, min_row=1, max_col=7, max_row=1)
    bar.add_data(bar_data, from_rows=True)
    bar.set_categories(bar_cats)
    ws.add_chart(bar, "A15")

    line = LineChart()
    line.title = growth_title
    min_c = 2 if include_jan_in_growth else 3
    line_data = Reference(ws, min_col=min_c, min_row=13, max_col=7, max_row=13)
    line_cats = Reference(ws, min_col=min_c, min_row=1, max_col=7, max_row=1)
    line.add_data(line_data, from_rows=True)
    line.set_categories(line_cats)
    ws.add_chart(line, "I15")


def correct_formulas_with_charts(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    ws.cell(12, 1, "Total")
    ws.cell(13, 1, "Growth")
    cols = {2: "B", 3: "C", 4: "D", 5: "E", 6: "F", 7: "G"}
    cached = {}
    for c_idx, col_let in cols.items():
        ws.cell(12, c_idx, f"=SUM({col_let}2:{col_let}11)")
        cached[f"{col_let}12"] = TOTALS[c_idx]
        if c_idx >= 3:
            prev_let = cols[c_idx - 1]
            cell = ws.cell(13, c_idx, f"=({col_let}12-{prev_let}12)/{prev_let}12")
            cell.number_format = "0.00%"
            cached[f"{col_let}13"] = GROWTHS[c_idx]
    _add_charts(ws)
    wb.save(xlsx_path)
    _patch_cached_numbers(xlsx_path, "xl/worksheets/sheet1.xml", cached)


def correct_values_with_charts(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    ws.cell(12, 1, "Total")
    ws.cell(13, 1, "Growth")
    for c_idx, val in TOTALS.items():
        ws.cell(12, c_idx, val)
    for c_idx, val in GROWTHS.items():
        cell = ws.cell(13, c_idx, val)
        cell.number_format = "0.00%"
    _add_charts(ws)
    wb.save(xlsx_path)


def wrong_missing_charts(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    ws.cell(12, 1, "Total")
    ws.cell(13, 1, "Growth")
    for c_idx, val in TOTALS.items():
        ws.cell(12, c_idx, val)
    for c_idx, val in GROWTHS.items():
        cell = ws.cell(13, c_idx, val)
        cell.number_format = "0.00%"
    wb.save(xlsx_path)


def wrong_growth_divides_by_current_month(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    ws.cell(12, 1, "Total")
    ws.cell(13, 1, "Growth")
    cols = {2: "B", 3: "C", 4: "D", 5: "E", 6: "F", 7: "G"}
    cached = {}
    for c_idx, col_let in cols.items():
        ws.cell(12, c_idx, f"=SUM({col_let}2:{col_let}11)")
        cached[f"{col_let}12"] = TOTALS[c_idx]
        if c_idx >= 3:
            prev_let = cols[c_idx - 1]
            wrong_g = (TOTALS[c_idx] - TOTALS[c_idx - 1]) / TOTALS[c_idx]
            cell = ws.cell(13, c_idx, f"=({col_let}12-{prev_let}12)/{col_let}12")
            cell.number_format = "0.00%"
            cached[f"{col_let}13"] = wrong_g
    _add_charts(ws)
    wb.save(xlsx_path)
    _patch_cached_numbers(xlsx_path, "xl/worksheets/sheet1.xml", cached)


def wrong_jan_included_in_growth_and_chart(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    ws.cell(12, 1, "Total")
    ws.cell(13, 1, "Growth")
    for c_idx, val in TOTALS.items():
        ws.cell(12, c_idx, val)
    ws.cell(13, 2, 0.0).number_format = "0.00%"
    for c_idx, val in GROWTHS.items():
        cell = ws.cell(13, c_idx, val)
        cell.number_format = "0.00%"
    _add_charts(ws, include_jan_in_growth=True)
    wb.save(xlsx_path)


def wrong_swapped_chart_titles(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    ws.cell(12, 1, "Total")
    ws.cell(13, 1, "Growth")
    for c_idx, val in TOTALS.items():
        ws.cell(12, c_idx, val)
    for c_idx, val in GROWTHS.items():
        cell = ws.cell(13, c_idx, val)
        cell.number_format = "0.00%"
    _add_charts(ws, total_title="Growth", growth_title="Total")
    wb.save(xlsx_path)


def wrong_total_off_by_one_row(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    ws.cell(12, 1, "Total")
    ws.cell(13, 1, "Growth")
    cols = {2: "B", 3: "C", 4: "D", 5: "E", 6: "F", 7: "G"}
    last_row_vals = {c: ws.cell(11, c).value for c in range(2, 8)}
    short_totals = {c: TOTALS[c] - last_row_vals[c] for c in range(2, 8)}
    cached = {}
    for c_idx, col_let in cols.items():
        ws.cell(12, c_idx, f"=SUM({col_let}2:{col_let}10)")
        cached[f"{col_let}12"] = short_totals[c_idx]
        if c_idx >= 3:
            prev_let = cols[c_idx - 1]
            g = (short_totals[c_idx] - short_totals[c_idx - 1]) / short_totals[c_idx - 1]
            cell = ws.cell(13, c_idx, f"=({col_let}12-{prev_let}12)/{prev_let}12")
            cell.number_format = "0.00%"
            cached[f"{col_let}13"] = g
    _add_charts(ws)
    wb.save(xlsx_path)
    _patch_cached_numbers(xlsx_path, "xl/worksheets/sheet1.xml", cached)
