from copy import copy
import os
import shutil
import openpyxl

REL_PATH = os.path.join("home", "user", "NetIncome.xlsx")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def correct_copy_values_with_header(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws1 = wb["Sheet1"]
    ws2 = wb.create_sheet("Sheet2")
    for r in range(1, ws1.max_row + 1):
        ws2.cell(r, 1, ws1.cell(r, 1).value)
    wb.save(xlsx_path)


def correct_copy_values_and_styles(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws1 = wb["Sheet1"]
    ws2 = wb.create_sheet("Sheet2")
    for r in range(1, ws1.max_row + 1):
        src = ws1.cell(r, 1)
        dst = ws2.cell(r, 1, src.value)
        dst.number_format = src.number_format
        if src.has_style:
            dst.font = copy(src.font)
            dst.alignment = copy(src.alignment)
    wb.save(xlsx_path)


def wrong_missing_header_row(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws1 = wb["Sheet1"]
    ws2 = wb.create_sheet("Sheet2")
    for r in range(2, ws1.max_row + 1):
        ws2.cell(r - 1, 1, ws1.cell(r, 1).value)
    wb.save(xlsx_path)


def wrong_copied_expenses_instead_of_revenue(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws1 = wb["Sheet1"]
    ws2 = wb.create_sheet("Sheet2")
    for r in range(1, ws1.max_row + 1):
        ws2.cell(r, 1, ws1.cell(r, 2).value)
    wb.save(xlsx_path)


def wrong_cut_instead_of_copy(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws1 = wb["Sheet1"]
    ws2 = wb.create_sheet("Sheet2")
    for r in range(1, ws1.max_row + 1):
        ws2.cell(r, 1, ws1.cell(r, 1).value)
        ws1.cell(r, 1).value = None
    wb.save(xlsx_path)


def wrong_wrong_sheet_name(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws1 = wb["Sheet1"]
    ws2 = wb.create_sheet("Revenue")
    for r in range(1, ws1.max_row + 1):
        ws2.cell(r, 1, ws1.cell(r, 1).value)
    wb.save(xlsx_path)


def wrong_partial_rows_copied(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws1 = wb["Sheet1"]
    ws2 = wb.create_sheet("Sheet2")
    for r in range(1, 11):
        ws2.cell(r, 1, ws1.cell(r, 1).value)
    wb.save(xlsx_path)
