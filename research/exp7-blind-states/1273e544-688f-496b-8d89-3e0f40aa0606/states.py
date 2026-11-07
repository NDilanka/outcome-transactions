"""End states for task 1273e544-688f-496b-8d89-3e0f40aa0606 (NetIncome.xlsx)."""

import os

import openpyxl
from copy import copy

from statekit import copy_snapshot, write_ods

SRC = ("home", "user", "NetIncome.xlsx")
DATA_ROWS = range(2, 21)


def _open(out_dir, name="NetIncome.xlsx", folder=None):
    return openpyxl.load_workbook(os.path.join(out_dir, *(folder or SRC[:-1]), name))


def _save(wb, out_dir, name="NetIncome.xlsx", folder=None):
    target = os.path.join(out_dir, *(folder or SRC[:-1]))
    os.makedirs(target, exist_ok=True)
    wb.save(os.path.join(target, name))


def _revenue(ws):
    return [ws["A%d" % row].value for row in DATA_ROWS]


def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenue"
    for index, value in enumerate(sorted(_revenue(ws)), start=2):
        second["A%d" % index] = value
    _save(wb, out_dir)


def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenue"
    for index, value in enumerate(_revenue(ws), start=2):
        second["A%d" % index] = value
    _save(wb, out_dir)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet 2")
    second["A1"] = "Revenue"
    for index, value in enumerate(_revenue(ws), start=2):
        second["A%d" % index] = value
    _save(wb, out_dir)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    for index, value in enumerate(_revenue(ws), start=1):
        second["A%d" % index] = value
    _save(wb, out_dir)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenue"
    for index in range(2, 21):
        second["A%d" % index] = "=Sheet1.A%d" % (index + 1)
    _save(wb, out_dir)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenue"
    for index, value in enumerate(_revenue(ws), start=2):
        second["A%d" % index] = value
    wb.active = wb.index(second)
    _save(wb, out_dir)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenue"
    second["B1"] = "Total Expenses"
    for index, row in enumerate(DATA_ROWS, start=2):
        second["A%d" % index] = ws["A%d" % row].value
        second["B%d" % index] = ws["B%d" % row].value
    _save(wb, out_dir)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A2"] = "Revenue"
    for index, value in enumerate(_revenue(ws), start=3):
        second["A%d" % index] = value
    _save(wb, out_dir)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    values = ["Revenue"] + _revenue(ws)
    for index, value in enumerate(values, start=1):
        second.cell(row=1, column=index, value=value)
    _save(wb, out_dir)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenue"
    second["A1"].number_format = ws["A1"].number_format
    for index, row in enumerate(DATA_ROWS, start=2):
        cell = second["A%d" % index]
        cell.value = ws["A%d" % row].value
        cell.number_format = ws["A%d" % row].number_format
    _save(wb, out_dir)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Revenue")
    second["A1"] = "Revenue"
    for index, value in enumerate(_revenue(ws), start=2):
        second["A%d" % index] = value
    _save(wb, out_dir)


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["B1"] = "Revenue"
    for index, value in enumerate(_revenue(ws), start=2):
        second["B%d" % index] = value
    _save(wb, out_dir)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    values = _revenue(ws)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenue"
    for index, value in enumerate(values, start=2):
        second["A%d" % index] = value
    ws.delete_cols(1, 1)
    _save(wb, out_dir)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenue"
    for index, value in enumerate(_revenue(ws)[:-1], start=2):
        second["A%d" % index] = value
    _save(wb, out_dir)


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenue"
    for index, value in enumerate(_revenue(ws), start=2):
        second["A%d" % index] = value
    _save(wb, out_dir, name="NetIncome_copy.xlsx", folder=("home", "user", "Documents"))


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenue"
    second["A1"].font = copy(ws["A1"].font)
    for index, value in enumerate(_revenue(ws), start=2):
        second["A%d" % index] = value
    second.column_dimensions["A"].width = 14
    _save(wb, out_dir)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenue"
    for index, value in enumerate(_revenue(ws), start=2):
        second["A%d" % index] = str(value)
    _save(wb, out_dir)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    rows = [["Revenue"]] + [[value] for value in _revenue(ws)]
    write_ods(os.path.join(out_dir, "home", "user", "NetIncome.ods"), "Sheet2", rows)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenues"
    for index, value in enumerate(_revenue(ws), start=2):
        second["A%d" % index] = value
    _save(wb, out_dir)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    source = wb["Sheet1"]
    second = wb.copy_worksheet(source)
    second.title = "Sheet2"
    _save(wb, out_dir)


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenue"
    _save(wb, out_dir)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenue"
    for index, value in enumerate(_revenue(ws)[:10], start=2):
        second["A%d" % index] = value
    _save(wb, out_dir)
