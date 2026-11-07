"""End states for task 0326d92d-d218-48a8-9ca1-981cd6d064c7 (SalesRep.xlsx)."""

import os

import openpyxl
from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import DataBarRule

from statekit import copy_snapshot

SHEET_FILE = ("home", "user", "SalesRep.xlsx")
MONTHS = ["B", "C", "D", "E", "F", "G"]
LAST_REP_ROW = 11


def _open(out_dir, folder=None, name="SalesRep.xlsx"):
    parts = folder or SHEET_FILE[:-1]
    return openpyxl.load_workbook(os.path.join(out_dir, *parts, name))


def _save(wb, out_dir, folder=None, name="SalesRep.xlsx"):
    parts = folder or SHEET_FILE[:-1]
    os.makedirs(os.path.join(out_dir, *parts), exist_ok=True)
    wb.save(os.path.join(out_dir, *parts, name))


def _totals(ws, first_row=2, last_row=LAST_REP_ROW):
    return [sum(ws["%s%d" % (col, row)].value for row in range(first_row, last_row + 1)) for col in MONTHS]


def _bar_chart(ws, columns, title, anchor="A15", horizontal=False, labels=False):
    chart = BarChart()
    chart.type = "bar" if horizontal else "col"
    if title is not None:
        chart.title = title
    data = Reference(ws, min_col=columns[0], max_col=columns[1], min_row=12, max_row=12)
    cats = Reference(ws, min_col=columns[0], max_col=columns[1], min_row=1, max_row=1)
    chart.add_data(data, from_rows=True, titles_from_data=False)
    chart.set_categories(cats)
    if labels:
        chart.dataLabels = DataLabelList()
        chart.dataLabels.showVal = True
        chart.legend = None
    ws.add_chart(chart, anchor)
    return chart


def _line_chart(ws, columns, title, anchor="J15", markers=True):
    chart = LineChart()
    if title is not None:
        chart.title = title
    data = Reference(ws, min_col=columns[0], max_col=columns[1], min_row=13, max_row=13)
    cats = Reference(ws, min_col=columns[0], max_col=columns[1], min_row=1, max_row=1)
    chart.add_data(data, from_rows=True, titles_from_data=False)
    chart.set_categories(cats)
    if markers:
        chart.series[0].marker.symbol = "circle"
    ws.add_chart(chart, anchor)
    return chart


def _growth_cells(ws, first_col_index, last_col_index, percent_format="0.00%"):
    for index in range(first_col_index, last_col_index + 1):
        col = MONTHS[index]
        prev = MONTHS[index - 1]
        cell = ws["%s13" % col]
        cell.value = "=(%s12-%s12)/%s12" % (col, prev, prev)
        cell.number_format = percent_format


def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    for index in range(1, 6):
        col = MONTHS[index]
        prev = MONTHS[index - 1]
        cell = ws["%s13" % MONTHS[index - 1]]
        cell.value = "=(%s12-%s12)/%s12" % (col, prev, prev)
        cell.number_format = "0.00%"
    _bar_chart(ws, (2, 7), "Total")
    _line_chart(ws, (2, 7), "Growth")
    _save(wb, out_dir)


def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Growth"
    for index in range(1, 6):
        col = MONTHS[index]
        prev = MONTHS[index - 1]
        cell = second["%s1" % col]
        cell.value = "=(Sheet1.%s12-Sheet1.%s12)/Sheet1.%s12" % (col, prev, prev)
        cell.number_format = "0.00%"
    _bar_chart(ws, (2, 7), "Total")
    _line_chart(ws, (2, 7), "Growth")
    _save(wb, out_dir)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    _growth_cells(ws, 1, 5)
    _bar_chart(ws, (2, 7), "Total", anchor="A15")
    _line_chart(ws, (3, 7), "Growth", anchor="A32")
    _save(wb, out_dir)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    _growth_cells(ws, 1, 5)
    chart = BarChart()
    chart.title = "Total"
    data = Reference(ws, min_col=2, max_col=7, min_row=2, max_row=11)
    chart.add_data(data, from_rows=True, titles_from_data=True)
    ws.add_chart(chart, "A15")
    _line_chart(ws, (3, 7), "Growth", anchor="A34")
    _save(wb, out_dir)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total Sales"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    _growth_cells(ws, 1, 5)
    _bar_chart(ws, (2, 7), "Total Sales")
    _line_chart(ws, (3, 7), "Growth")
    _save(wb, out_dir)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS[:5]:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    _growth_cells(ws, 1, 5)
    _bar_chart(ws, (2, 6), "Total")
    _line_chart(ws, (3, 7), "Growth")
    _save(wb, out_dir)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    for index in range(1, 6):
        col = MONTHS[index]
        prev = MONTHS[index - 1]
        cell = ws["%s13" % col]
        cell.value = "=%s12/%s12" % (col, prev)
        cell.number_format = "0.00%"
    _bar_chart(ws, (2, 7), "Total")
    _line_chart(ws, (3, 7), "Growth")
    _save(wb, out_dir)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    for index in range(1, 6):
        col = MONTHS[index]
        prev = MONTHS[index - 1]
        cell = ws["%s13" % col]
        cell.value = "=ROUND((%s12-%s12)/%s12,4)" % (col, prev, prev)
        cell.number_format = "0.00%"
    _bar_chart(ws, (2, 7), "Total", anchor="A15", horizontal=True)
    _line_chart(ws, (3, 7), "Growth", anchor="A33", markers=False)
    _save(wb, out_dir)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    _growth_cells(ws, 1, 5)
    ws.conditional_formatting.add(
        "B12:G12",
        DataBarRule(start_type="num", start_value=0, end_type="num", end_value=6000, color="638EC6"),
    )
    _line_chart(ws, (3, 7), "Growth")
    _save(wb, out_dir)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    totals = _totals(ws)
    ws["A13"] = "Growth"
    for index in range(1, 6):
        col = MONTHS[index]
        value = (totals[index] - totals[index - 1]) / totals[index - 1]
        ws["%s13" % col] = "%.1f%%" % (value * 100)
    _bar_chart(ws, (2, 7), "Total")
    _line_chart(ws, (3, 7), "Growth")
    _save(wb, out_dir)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s10)" % (col, col)
    ws["A13"] = "Growth"
    _growth_cells(ws, 1, 5)
    _bar_chart(ws, (2, 7), "Total")
    _line_chart(ws, (3, 7), "Growth")
    _save(wb, out_dir)


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    _growth_cells(ws, 1, 5)
    chart = PieChart()
    chart.title = "Total"
    data = Reference(ws, min_col=2, max_col=7, min_row=12, max_row=12)
    cats = Reference(ws, min_col=2, max_col=7, min_row=1, max_row=1)
    chart.add_data(data, from_rows=True, titles_from_data=False)
    chart.set_categories(cats)
    ws.add_chart(chart, "A15")
    _line_chart(ws, (3, 7), "Growth", anchor="A33")
    _save(wb, out_dir)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    _growth_cells(ws, 1, 5)
    _bar_chart(ws, (2, 7), "Total", anchor="A15", labels=True)
    _line_chart(ws, (3, 7), "Growth", anchor="A33")
    _save(wb, out_dir)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    for index in range(1, 6):
        col = MONTHS[index]
        prev = MONTHS[index - 1]
        ws["%s13" % col] = "=%s12-%s12" % (col, prev)
    _bar_chart(ws, (2, 7), "Total")
    _line_chart(ws, (3, 7), "Growth")
    _save(wb, out_dir)


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    _growth_cells(ws, 1, 5)
    _save(wb, out_dir)


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    ws["B13"] = "=(B12-B12)/B12"
    ws["B13"].number_format = "0.00%"
    _growth_cells(ws, 1, 5)
    _bar_chart(ws, (2, 7), "Total")
    _line_chart(ws, (2, 7), "Growth")
    _save(wb, out_dir)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s:%s)" % (col, col)
    ws["A13"] = "Growth"
    _growth_cells(ws, 1, 5)
    bar = _bar_chart(ws, (2, 7), "Total", anchor="A15")
    bar.width = 14
    bar.height = 7
    line = _line_chart(ws, (3, 7), "Growth", anchor="A30")
    line.width = 14
    line.height = 7
    _save(wb, out_dir)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    for index in range(1, 6):
        col = MONTHS[index]
        prev = MONTHS[index - 1]
        cell = ws["%s13" % col]
        cell.value = "=(%s12-%s12)/%s12" % (prev, col, col)
        cell.number_format = "0.00%"
    _bar_chart(ws, (2, 7), "Total")
    _line_chart(ws, (3, 7), "Growth")
    _save(wb, out_dir)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    _growth_cells(ws, 1, 5)
    _bar_chart(ws, (2, 7), "Total")
    _line_chart(ws, (3, 7), "Growth", anchor="J15")
    ws.delete_rows(2, 10)
    _save(wb, out_dir)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    _growth_cells(ws, 1, 5)
    _bar_chart(ws, (2, 7), "Total")
    _line_chart(ws, (3, 7), "Growth")
    _save(wb, out_dir, folder=("home", "user", "Documents"), name="SalesRep.xlsx")


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    _growth_cells(ws, 1, 5)
    _bar_chart(ws, (2, 7), None)
    _line_chart(ws, (3, 7), None)
    _save(wb, out_dir)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["A12"] = "Total"
    for col in MONTHS:
        ws["%s12" % col] = "=SUM(%s2:%s11)" % (col, col)
    ws["A13"] = "Growth"
    _growth_cells(ws, 2, 5)
    _bar_chart(ws, (2, 7), "Total")
    _line_chart(ws, (4, 7), "Growth")
    _save(wb, out_dir)
