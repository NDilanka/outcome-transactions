import os
import shutil
import zipfile
from lxml import etree
import openpyxl

REL_PATH = os.path.join("home", "user", "Desktop", "my_bookkeeping.xlsx")
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

BASE_BALANCE_E8 = 3122.93
INITIAL_CACHED = {
    "E4": 879.5,
    "E5": 612.23,
    "E6": 712.23,
    "E7": 622.93,
    "E8": 3122.93,
}


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def _inject_cached_values(xlsx_path, cell_values):
    merged = dict(INITIAL_CACHED)
    merged.update(cell_values)
    tmp_path = xlsx_path + ".tmp"
    with zipfile.ZipFile(xlsx_path, "r") as zin, zipfile.ZipFile(tmp_path, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                root = etree.fromstring(data)
                for c_el in root.findall(f".//{{{MAIN_NS}}}c"):
                    ref = c_el.get("r")
                    if ref in merged:
                        v_el = c_el.find(f"{{{MAIN_NS}}}v")
                        if v_el is None:
                            v_el = etree.SubElement(c_el, f"{{{MAIN_NS}}}v")
                        v_el.text = str(merged[ref])
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
            zout.writestr(item, data)
    os.replace(tmp_path, xlsx_path)


def _append_transactions(xlsx_path, entries):
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active
    bal = BASE_BALANCE_E8
    cached = {}
    for idx, (cat, desc, amt) in enumerate(entries):
        row_num = 9 + idx
        prev_row = row_num - 1
        tx_id = 7 + idx
        ws[f"A{row_num}"] = tx_id
        ws[f"B{row_num}"] = cat
        ws[f"C{row_num}"] = desc
        ws[f"D{row_num}"] = amt
        ws[f"E{row_num}"] = f"=E{prev_row}+D{row_num}"
        bal = round(bal + amt, 2)
        cached[f"E{row_num}"] = bal
    wb.save(xlsx_path)
    _inject_cached_values(xlsx_path, cached)


def correct_all_five_receipts_with_cashout_income(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    entries = [
        ("Food", "Groceries", -186.93),
        ("Cash", "Cash Out to Bank of America", 3670),
        ("Hardware", "The Home Depot", -236.49),
        ("Subscription", "Dropbox Plus 2TB", -11.99),
        ("Fuel", "Chevron", -42.46),
    ]
    _append_transactions(xlsx_path, entries)


def correct_four_expense_receipts_only(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    entries = [
        ("Food", "Groceries", -186.93),
        ("Shopping", "The Home Depot", -236.49),
        ("Software", "Dropbox Plus", -11.99),
        ("Transport", "Chevron Gas", -42.46),
    ]
    _append_transactions(xlsx_path, entries)


def wrong_positive_signs_for_expenses(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    entries = [
        ("Food", "Groceries", 186.93),
        ("Cash", "Cash Out to Bank of America", 3670),
        ("Hardware", "The Home Depot", 236.49),
        ("Subscription", "Dropbox Plus 2TB", 11.99),
        ("Fuel", "Chevron", 42.46),
    ]
    _append_transactions(xlsx_path, entries)


def wrong_used_pre_tax_subtotals(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    entries = [
        ("Food", "Groceries", -185.08),
        ("Cash", "Cash Out to Bank of America", 3670),
        ("Hardware", "The Home Depot", -218.97),
        ("Subscription", "Dropbox Plus 2TB", -11.99),
        ("Fuel", "Chevron", -42.46),
    ]
    _append_transactions(xlsx_path, entries)


def wrong_partial_only_first_two_receipts(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    entries = [
        ("Food", "Groceries", -186.93),
        ("Cash", "Cash Out to Bank of America", 3670),
    ]
    _append_transactions(xlsx_path, entries)


def wrong_overwrote_existing_rows_3_to_7(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active
    entries = [
        ("Food", "Groceries", -186.93),
        ("Cash", "Cash Out to Bank of America", 3670),
        ("Hardware", "The Home Depot", -236.49),
        ("Subscription", "Dropbox Plus 2TB", -11.99),
        ("Fuel", "Chevron", -42.46),
    ]
    for idx, (cat, desc, amt) in enumerate(entries):
        r = 3 + idx
        ws[f"A{r}"] = idx + 1
        ws[f"B{r}"] = cat
        ws[f"C{r}"] = desc
        ws[f"D{r}"] = amt
    wb.save(xlsx_path)


def wrong_missing_balance_column_update(snapshot_dir, out_dir):
    xlsx_path = _prepare(snapshot_dir, out_dir)
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active
    entries = [
        ("Food", "Groceries", -186.93),
        ("Cash", "Cash Out to Bank of America", 3670),
        ("Hardware", "The Home Depot", -236.49),
        ("Subscription", "Dropbox Plus 2TB", -11.99),
        ("Fuel", "Chevron", -42.46),
    ]
    for idx, (cat, desc, amt) in enumerate(entries):
        row_num = 9 + idx
        ws[f"A{row_num}"] = 7 + idx
        ws[f"B{row_num}"] = cat
        ws[f"C{row_num}"] = desc
        ws[f"D{row_num}"] = amt
    wb.save(xlsx_path)
    _inject_cached_values(xlsx_path, {})
