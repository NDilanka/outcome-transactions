import os
import shutil
import openpyxl

REL_PATH = os.path.join("home", "user", "Date_Budget_Variance_HideNA.xlsx")

NA_ROWS = [3, 6, 8, 9, 12, 14, 18, 19, 20, 24, 27, 32, 33]


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def correct_hide_na_rows(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    for r in NA_ROWS:
        ws.row_dimensions[r].hidden = True
    wb.save(xlsx_path)


def correct_hide_na_rows_zero_height(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    for r in NA_ROWS:
        ws.row_dimensions[r].hidden = True
        ws.row_dimensions[r].height = 0
    wb.save(xlsx_path)


def wrong_deleted_na_cell_contents(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    for r in NA_ROWS:
        ws.cell(r, 4).value = None
        ws.cell(r, 5).value = None
    wb.save(xlsx_path)


def wrong_deleted_entire_na_rows(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    for r in sorted(NA_ROWS, reverse=True):
        ws.delete_rows(r, 1)
    wb.save(xlsx_path)


def wrong_autofilter_applied(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    ws.auto_filter.ref = "B1:E36"
    for r in NA_ROWS:
        ws.row_dimensions[r].hidden = True
    wb.save(xlsx_path)


def wrong_partial_na_rows_hidden(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    for r in NA_ROWS[:7]:
        ws.row_dimensions[r].hidden = True
    wb.save(xlsx_path)


def wrong_hid_entire_columns_d_and_e(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Sheet1"]
    ws.column_dimensions["D"].hidden = True
    ws.column_dimensions["E"].hidden = True
    wb.save(xlsx_path)
