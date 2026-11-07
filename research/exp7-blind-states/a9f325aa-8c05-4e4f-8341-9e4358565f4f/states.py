"""End states for task a9f325aa-8c05-4e4f-8341-9e4358565f4f (Movie_title_garbage_clean.xlsx)."""

import os
import re

import openpyxl
from openpyxl.styles import Alignment

from statekit import copy_snapshot, write_ods

SRC = ("home", "user", "Movie_title_garbage_clean.xlsx")
ROWS = range(2, 30)


def _open(out_dir, name="Movie_title_garbage_clean.xlsx", folder=None):
    return openpyxl.load_workbook(os.path.join(out_dir, *(folder or SRC[:-1]), name))


def _save(wb, out_dir, name="Movie_title_garbage_clean.xlsx", folder=None):
    target = os.path.join(out_dir, *(folder or SRC[:-1]))
    os.makedirs(target, exist_ok=True)
    wb.save(os.path.join(target, name))


def _clean(text):
    words = re.split(r"\s+", text.strip())
    return " ".join(word[:1].upper() + word[1:].lower() for word in words)


def _collapse(text):
    return re.sub(r"\s+", " ", text).strip()


def _titles(ws):
    return [ws["B%d" % row].value for row in ROWS]


def _word_case_only(text):
    return re.sub(r"\S+", lambda match: match.group(0)[:1].upper() + match.group(0)[1:].lower(), text)


def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        ws["C%d" % row] = _word_case_only(ws["B%d" % row].value)
    _save(wb, out_dir)


def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        ws["C%d" % row] = _clean(ws["B%d" % row].value)
    _save(wb, out_dir)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        words = _collapse(ws["B%d" % row].value).split(" ")
        ws["C%d" % row] = " ".join(word[:1].upper() + word[1:] for word in words)
    _save(wb, out_dir)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        ws["D%d" % row] = _clean(ws["B%d" % row].value)
    _save(wb, out_dir)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        ws["C%d" % row] = _clean(ws["B%d" % row].value)
    ws.column_dimensions["C"].width = 52
    _save(wb, out_dir)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        ws["B%d" % row] = _clean(ws["B%d" % row].value)
    _save(wb, out_dir)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        ws["C%d" % row] = _collapse(ws["B%d" % row].value)
    _save(wb, out_dir)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in range(2, 29):
        ws["C%d" % row] = _clean(ws["B%d" % row].value)
    _save(wb, out_dir)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        cell = ws["C%d" % row]
        cell.value = _clean(ws["B%d" % row].value)
        cell.alignment = Alignment(horizontal="left", vertical="bottom")
    _save(wb, out_dir)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        ws["C%d" % row] = _collapse(ws["B%d" % row].value).capitalize()
    _save(wb, out_dir)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        collapsed = re.sub(r"\s+", " ", ws["B%d" % row].value)
        ws["C%d" % row] = " ".join(word[:1].upper() + word[1:].lower() for word in collapsed.split(" "))
    _save(wb, out_dir)


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        words = _collapse(ws["B%d" % row].value).split(" ")
        ws["C%d" % row] = "".join(word[:1].upper() + word[1:].lower() for word in words)
    _save(wb, out_dir)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        ws["C%d" % row] = _clean(ws["B%d" % row].value)
    ws.sheet_view.zoomScale = 90
    _save(wb, out_dir)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        ws["C%d" % row] = _collapse(ws["B%d" % row].value).upper()
    _save(wb, out_dir)


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        ws["C%d" % row] = _clean(ws["B%d" % row].value) if row == 29 else _clean(ws["B%d" % (row + 1)].value)
    _save(wb, out_dir)


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        ws["C%d" % row] = _clean(ws["B%d" % row].value)
    for row in range(30, 34):
        ws["C%d" % row] = "N/A"
    ws["D1"] = "Clean Movie Titles"
    _save(wb, out_dir)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        ws["C%d" % row] = ws["B%d" % row].value
        ws["B%d" % row] = _clean(ws["B%d" % row].value)
    _save(wb, out_dir)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in ROWS:
        original = ws["B%d" % row].value
        ws["C%d" % row] = original
        ws["B%d" % row] = re.sub(r"\s+", " ", original.strip())
    _save(wb, out_dir)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    second = wb.create_sheet("Sheet2")
    second["A1"] = "Clean Movie Titles"
    for index, row in enumerate(ROWS, start=2):
        second["A%d" % index] = _clean(ws["B%d" % row].value)
    _save(wb, out_dir)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    rows = [["Garbage Movie titles", "Clean Movie Titles"]]
    for row in ROWS:
        rows.append([ws["B%d" % row].value, _clean(ws["B%d" % row].value)])
    write_ods(os.path.join(out_dir, "home", "user", "Movie_title_garbage_clean.ods"), "Sheet1", rows)


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for index, value in enumerate(sorted(_clean(ws["B%d" % row].value) for row in ROWS), start=2):
        ws["C%d" % index] = value
    _save(wb, out_dir)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    for row in range(2, 12):
        ws["C%d" % row] = _clean(ws["B%d" % row].value)
    _save(wb, out_dir)
