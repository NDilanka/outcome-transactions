"""End states for task 6054afcb-5bab-4702-90a0-b259b5d3217c (Date_Budget_Variance_HideNA.xlsx)."""

import os

import openpyxl
from openpyxl.styles import Font

from statekit import copy_snapshot

SRC = ("home", "user", "Date_Budget_Variance_HideNA.xlsx")
LAST_ROW = 36


def _open(out_dir):
    return openpyxl.load_workbook(os.path.join(out_dir, *SRC))


def _save(wb, out_dir):
    wb.save(os.path.join(out_dir, *SRC))


def _na_rows(ws):
    return [row for row in range(2, LAST_ROW + 1) if ws["D%d" % row].value == "=NA()"]


def _hide(ws, rows):
    for row in rows:
        ws.row_dimensions[row].hidden = True


def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    _hide(ws, _na_rows(ws))
    _save(wb, out_dir)


def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws.auto_filter.ref = "B1:E36"
    _hide(ws, _na_rows(ws))
    _save(wb, out_dir)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in reversed(_na_rows(ws)):
        ws.delete_rows(row, 1)
    _save(wb, out_dir)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    _hide(ws, _na_rows(ws))
    ws.sheet_view.zoomScale = 85
    _save(wb, out_dir)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    white = Font(name="Calibri", color="FFFFFFFF")
    for row in _na_rows(ws):
        for column in ("D", "E"):
            ws["%s%d" % (column, row)].font = white
    _save(wb, out_dir)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in _na_rows(ws):
        ws["D%d" % row] = None
    _save(wb, out_dir)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in _na_rows(ws):
        ws["D%d" % row] = 0
        ws["E%d" % row] = "=D%d-C%d" % (row, row)
    _save(wb, out_dir)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    _hide(ws, _na_rows(ws))
    ws.sheet_view.selection[0].activeCell = "B2"
    ws.sheet_view.selection[0].sqref = "B2"
    _save(wb, out_dir)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in _na_rows(ws):
        ws.row_dimensions[row].height = 0
    _save(wb, out_dir)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    _hide(ws, _na_rows(ws)[:-4])
    _save(wb, out_dir)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws.column_dimensions["D"].hidden = True
    _save(wb, out_dir)


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    _hide(ws, _na_rows(ws))
    ws.sheet_properties.tabColor = "808080"
    _save(wb, out_dir)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    _hide(ws, [row for row in range(2, LAST_ROW + 1) if isinstance(ws["C%d" % row].value, (int, float))
               and isinstance(ws["D%d" % row].value, (int, float))
               and ws["D%d" % row].value - ws["C%d" % row].value < 0])
    _save(wb, out_dir)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    rows = _na_rows(ws)
    keep = [row for row in range(2, LAST_ROW + 1) if row not in rows]
    data = [[ws["%s%d" % (col, row)].value for col in ("B", "C", "D", "E")] for row in keep + rows]
    for index, values in enumerate(data, start=2):
        for col, value in zip(("B", "C", "D", "E"), values):
            ws["%s%d" % (col, index)] = value
    _hide(ws, range(LAST_ROW - len(rows) + 1, LAST_ROW + 1))
    _save(wb, out_dir)


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    _hide(ws, _na_rows(ws))
    ws.delete_cols(5, 1)
    _save(wb, out_dir)


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    _hide(ws, _na_rows(ws))
    for column in ("B", "C", "D", "E"):
        ws["%s1" % column].font = Font(bold=False)
    _save(wb, out_dir)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    _hide(ws, range(3, 13))
    _save(wb, out_dir)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    _hide(ws, list(_na_rows(ws)) + [1])
    _save(wb, out_dir)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    rows = _na_rows(ws)
    _hide(ws, rows)
    for row in rows:
        ws["E%d" % row] = None
    _save(wb, out_dir)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    rows = _na_rows(ws)
    shifted = [row + 1 for row in rows]
    ws.insert_rows(2, 1)
    _hide(ws, shifted)
    _save(wb, out_dir)


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    rows = _na_rows(ws)
    for row in rows:
        ws["D%d" % row] = "N/A"
    _hide(ws, rows)
    _save(wb, out_dir)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    _hide(ws, _na_rows(ws))
    ws.column_dimensions["E"].hidden = True
    _save(wb, out_dir)
