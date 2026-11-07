"""End states for task 42e0a640-4f19-4b28-973d-729602b5a4a7 (NetIncome.xlsx sums)."""

import os

import openpyxl
from openpyxl.styles import Font

from statekit import copy_snapshot

SRC = ("home", "user", "NetIncome.xlsx")


def _open(out_dir, name="NetIncome.xlsx", folder=None):
    return openpyxl.load_workbook(os.path.join(out_dir, *(folder or SRC[:-1]), name))


def _save(wb, out_dir, name="NetIncome.xlsx", folder=None):
    target = os.path.join(out_dir, *(folder or SRC[:-1]))
    os.makedirs(target, exist_ok=True)
    wb.save(os.path.join(target, name))


def _column(ws, column):
    return [ws["%s%d" % (column, row)].value for row in range(2, 21)]


def _revenue_total(ws):
    return sum(_column(ws, "A"))


def _expense_total(ws):
    return sum(_column(ws, "B"))


def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    for row in range(2, 21):
        second["A%d" % row] = ws["A%d" % row].value
        second["B%d" % row] = ws["B%d" % row].value
    _save(wb, out_dir)


def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = "=SUM(Sheet1.A2:A20)"
    second["B2"] = "=SUM(Sheet1.B2:B20)"
    _save(wb, out_dir)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Totals")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = "=SUM(Sheet1.A2:A20)"
    second["B2"] = "=SUM(Sheet1.B2:B20)"
    _save(wb, out_dir)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = str(_revenue_total(ws))
    second["B2"] = str(_expense_total(ws))
    _save(wb, out_dir)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "=SUM(Sheet1.A2:A20)"
    second["A2"] = "Total Expenses"
    second["B2"] = "=SUM(Sheet1.B2:B20)"
    _save(wb, out_dir)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A3"] = "=SUM(Sheet1.A2:A20)"
    second["B3"] = "=SUM(Sheet1.B2:B20)"
    _save(wb, out_dir)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = "=SUM(Sheet1.A:A)"
    second["B2"] = "=SUM(Sheet1.B:B)"
    _save(wb, out_dir)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = "=SUM(Sheet1.A2:A20)"
    second["B2"] = "=SUM(Sheet1.B2:B20)"
    _save(wb, out_dir)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = round(_revenue_total(ws), -3)
    second["B2"] = round(_expense_total(ws), -3)
    _save(wb, out_dir)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    first = wb["Sheet1"]
    first["D1"] = "Total Revenue"
    first["E1"] = "Total Expenses"
    first["D2"] = "=SUM(A2:A20)"
    first["E2"] = "=SUM(B2:B20)"
    _save(wb, out_dir)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = "=SUM(Sheet1.A2:A20)"
    second["B2"] = "=SUM(Sheet1.B2:B20)"
    second["A2"].number_format = "#,##0"
    second["B2"].number_format = "#,##0"
    second["A1"].font = Font(bold=True)
    second["B1"].font = Font(bold=True)
    _save(wb, out_dir)


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = "=SUM(Sheet1.A2:A20)"
    _save(wb, out_dir)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = "=SUM(Sheet1.A2:A20)"
    second["B2"] = "=SUM(Sheet1.A2:A20)-SUM(Sheet1.B2:B20)"
    _save(wb, out_dir)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = "=SUM(Sheet1.A2:A19)"
    second["B2"] = "=SUM(Sheet1.B2:B19)"
    _save(wb, out_dir)


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    for row in range(2, 21):
        second["A%d" % row] = ws["A%d" % row].value
        second["B%d" % row] = ws["B%d" % row].value
    second["A21"] = "=SUM(A2:A20)"
    second["B21"] = "=SUM(B2:B20)"
    _save(wb, out_dir)


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = "=SUBTOTAL(9,Sheet1.$A$2:$A$20)"
    second["B2"] = "=SUBTOTAL(9,Sheet1.$B$2:$B$20)"
    _save(wb, out_dir)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = "=SUM(Sheet1.A2:A20)"
    second["B2"] = "=SUM(Sheet1.A2:A20)"
    _save(wb, out_dir)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    _save(wb, out_dir)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = "=SUM(Sheet1.A3:A20)"
    second["B2"] = "=SUM(Sheet1.B3:B20)"
    _save(wb, out_dir)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = "=SUM(Sheet1.A2:A20)"
    second["B2"] = "=SUM(Sheet1.B2:B20)"
    _save(wb, out_dir, name="NetIncome_copy.xlsx", folder=("home", "user", "Documents"))


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = "=SUM(Sheet1.A2:A20)"
    second["B2"] = "=SUM(Sheet1.B2:B20)"
    third = wb.create_sheet("Sheet3")
    third["A1"] = "Totals"
    third["A2"] = "=SUM(Sheet1.A2:A20)+SUM(Sheet1.B2:B20)"
    _save(wb, out_dir)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Total Revenue"
    second["B1"] = "Total Expenses"
    second["A2"] = "=SUM(Sheet1.A2:A20)"
    second["B2"] = "=SUM(Sheet1.B2:B20)"
    del wb["Sheet1"]
    _save(wb, out_dir)
