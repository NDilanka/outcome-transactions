"""End states for task 51719eea-10bc-4246-a428-ac7c433dd4b3 (BoomerangSales.xlsx)."""

import os

import openpyxl
from openpyxl.styles import Font

from statekit import copy_snapshot, write_ods

SRC = ("home", "user", "BoomerangSales.xlsx")
SALES_ROWS = range(2, 37)
PRICE_ROWS = range(2, 24)


def _open(out_dir, name="BoomerangSales.xlsx", folder=None):
    return openpyxl.load_workbook(os.path.join(out_dir, *(folder or SRC[:-1]), name))


def _save(wb, out_dir, name="BoomerangSales.xlsx", folder=None):
    target = os.path.join(out_dir, *(folder or SRC[:-1]))
    os.makedirs(target, exist_ok=True)
    wb.save(os.path.join(target, name))


def _prices(wb):
    ws = wb["Retail Price"]
    return {ws["A%d" % row].value: ws["B%d" % row].value for row in PRICE_ROWS}


def _sales(wb):
    ws = wb["Sheet1"]
    return [(ws["C%d" % row].value, ws["E%d" % row].value, ws["F%d" % row].value) for row in SALES_ROWS]


def _revenue_values(wb):
    prices = _prices(wb)
    return [prices[product] * quantity * (1 - discount) for product, quantity, discount in _sales(wb)]


def _products(wb):
    seen = []
    for product, _quantity, _discount in _sales(wb):
        if product not in seen:
            seen.append(product)
    return seen


def _summary(ws, rows, header_two="Sum of Revenue", total_row=False):
    ws["A1"] = "Product"
    ws["B1"] = header_two
    ws["A1"].font = Font(bold=True)
    ws["B1"].font = Font(bold=True)
    for index, (product, value) in enumerate(rows, start=2):
        ws["A%d" % index] = product
        ws["B%d" % index] = value
    if total_row:
        last = len(rows) + 2
        ws["A%d" % last] = "Total"
        ws["B%d" % last] = "=SUM(B2:B%d)" % (last - 1)


def state_01(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    prices = _prices(wb)
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        product = ws["C%d" % row].value
        ws["G%d" % row] = prices[product] * ws["E%d" % row].value
    second = wb.create_sheet("Sheet2")
    rows = []
    for product in _products(wb):
        rows.append((product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (len(rows) + 2)))
    _summary(second, rows)
    _save(wb, out_dir)


def state_02(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        ws["G%d" % row] = "=VLOOKUP(C%d,'Retail Price'!$A$2:$B$23,2,0)*E%d*(1-F%d)" % (row, row, row)
    second = wb.create_sheet("Sheet2")
    products = sorted(_products(wb))
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (index + 2)) for index, product in enumerate(products)]
    _summary(second, rows)
    _save(wb, out_dir)


def state_03(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    values = _revenue_values(wb)
    ws["G1"] = "Revenue"
    for row, value in zip(SALES_ROWS, values):
        ws["G%d" % row] = round(value, 2)
    second = wb.create_sheet("Sheet2")
    totals = {}
    for (product, _quantity, _discount), value in zip(_sales(wb), values):
        totals[product] = totals.get(product, 0) + value
    ordered = sorted(totals.items(), key=lambda item: -item[1])
    _summary(second, [(product, round(value, 2)) for product, value in ordered])
    _save(wb, out_dir)


def state_04(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        ws["G%d" % row] = "=INDEX('Retail Price'!$B$2:$B$23,MATCH(C%d,'Retail Price'!$A$2:$A$23,0))*E%d*(1-F%d)" % (
            row, row, row)
    second = wb.create_sheet("Sheet2")
    companies = []
    for product in _products(wb):
        companies.append(product)
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (index + 2)) for index, product in enumerate(companies)]
    _summary(second, rows, total_row=True)
    _save(wb, out_dir)


def state_05(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        ws["G%d" % row] = "=VLOOKUP(C%d,'Retail Price'!$A$2:$B$23,2)*E%d*(1-F%d)" % (row, row, row)
    second = wb.create_sheet("Sheet2")
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (index + 2)) for index, product in enumerate(_products(wb))]
    _summary(second, rows)
    _save(wb, out_dir)


def state_06(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        ws["G%d" % row] = "=VLOOKUP(C%d,'Retail Price'!$A$2:$B$23,2,0)*E%d*(1-F%d)" % (row, row, row)
    second = wb.create_sheet("Sheet2")
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (index + 2)) for index, product in enumerate(_products(wb))]
    _summary(second, rows, total_row=True)
    _save(wb, out_dir)


def state_07(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    prices = _prices(wb)
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        product = ws["C%d" % row].value
        ws["G%d" % row] = prices[product] * ws["E%d" % row].value - ws["F%d" % row].value
    second = wb.create_sheet("Sheet2")
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (index + 2)) for index, product in enumerate(_products(wb))]
    _summary(second, rows)
    _save(wb, out_dir)


def state_08(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        ws["G%d" % row] = "=VLOOKUP(C%d,'Retail Price'!$A$2:$B$23,2,0)*E%d*(1-F%d)" % (row, row, row)
    third = wb.create_sheet("Pivot")
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (index + 2)) for index, product in enumerate(_products(wb))]
    _summary(third, rows)
    _save(wb, out_dir)


def state_09(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        ws["G%d" % row] = "=VLOOKUP(C%d,'Retail Price'!$A$2:$B$23,1,0)*E%d*(1-F%d)" % (row, row, row)
    second = wb.create_sheet("Sheet2")
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (index + 2)) for index, product in enumerate(_products(wb))]
    _summary(second, rows)
    _save(wb, out_dir)


def state_10(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        ws["G%d" % row] = "=VLOOKUP(C%d,'Retail Price'!$A$2:$B$23,2,0)*E%d*(1-F%d)" % (row, row, row)
    _save(wb, out_dir)


def state_11(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    values = _revenue_values(wb)
    ws["G1"] = "Revenue"
    for row, value in zip(SALES_ROWS, values):
        ws["G%d" % row] = str(round(value, 2))
    second = wb.create_sheet("Sheet2")
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (index + 2)) for index, product in enumerate(_products(wb))]
    _summary(second, rows)
    _save(wb, out_dir)


def state_12(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        ws["G%d" % row] = "=VLOOKUP(C%d,'Retail Price'!$A$2:$B$23,2,0)*E%d*(1-F%d)" % (row, row, row)
    second = wb.create_sheet("Sheet2")
    rows = [(product, "=COUNTA($C$2:$C$36)") for product in _products(wb)]
    _summary(second, rows, header_two="Count of Orders")
    _save(wb, out_dir)


def state_13(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    values = _revenue_values(wb)
    ws["G1"] = "Revenue"
    for row, value in zip(SALES_ROWS, values):
        ws["G%d" % row] = int(round(value))
    second = wb.create_sheet("Sheet2")
    totals = {}
    for (product, _quantity, _discount), value in zip(_sales(wb), values):
        totals[product] = totals.get(product, 0) + value
    _summary(second, [(product, int(round(value))) for product, value in totals.items()])
    _save(wb, out_dir)


def state_14(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        ws["G%d" % row] = "=VLOOKUP(C%d,'Retail Price'!$A$2:$B$23,2,0)*E%d*(1+F%d)" % (row, row, row)
    second = wb.create_sheet("Sheet2")
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (index + 2)) for index, product in enumerate(_products(wb))]
    _summary(second, rows)
    _save(wb, out_dir)


def state_15(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        ws["G%d" % row] = "=VLOOKUP(C%d,'Retail Price'!$A$2:$B$23,2,0)*E%d*(1-F%d)" % (row, row, row)
    second = wb.create_sheet("Sheet2")
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)") for product in _products(wb)]
    _summary(second, rows)
    _save(wb, out_dir)


def state_16(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Total"
    for row in SALES_ROWS:
        ws["G%d" % row] = "=VLOOKUP(C%d,'Retail Price'!$A$2:$B$23,2,0)*E%d*(1-F%d)" % (row, row, row)
    second = wb.create_sheet("Sheet2")
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (index + 2)) for index, product in enumerate(_products(wb))]
    _summary(second, rows)
    _save(wb, out_dir)


def state_17(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in range(3, 38):
        ws["G%d" % row] = "=VLOOKUP(C%d,'Retail Price'!$A$2:$B$23,2,0)*E%d*(1-F%d)" % (row, row, row)
    second = wb.create_sheet("Sheet2")
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (index + 2)) for index, product in enumerate(_products(wb))]
    _summary(second, rows)
    _save(wb, out_dir)


def state_18(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        ws["G%d" % row] = "='Retail Price'!$B$2*E%d*(1-F%d)" % (row, row)
    second = wb.create_sheet("Sheet2")
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (index + 2)) for index, product in enumerate(_products(wb))]
    _summary(second, rows)
    _save(wb, out_dir)


def state_19(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        ws["G%d" % row] = "=VLOOKUP(C%d,'Retail Price'!$A$2:$B$23,2,0)*E%d*(1-F%d)" % (row, row, row)
    second = wb.create_sheet("Sheet2")
    sites = []
    for row in SALES_ROWS:
        site = ws["B%d" % row].value
        if site not in sites:
            sites.append(site)
    rows = [(site, "=SUMIF($B$2:$B$36,A%d,$G$2:$G$36)" % (index + 2)) for index, site in enumerate(sites)]
    _summary(second, rows, header_two="Sum of Revenue")
    _save(wb, out_dir)


def state_20(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    prices = _prices(wb)
    rows = [["Date Time", "Web Site", "Product", "Type", "Quantity", "Discount", "Revenue"]]
    for row in SALES_ROWS:
        product = ws["C%d" % row].value
        rows.append([
            str(ws["A%d" % row].value),
            ws["B%d" % row].value,
            product,
            ws["D%d" % row].value,
            ws["E%d" % row].value,
            ws["F%d" % row].value,
            prices[product] * ws["E%d" % row].value * (1 - ws["F%d" % row].value),
        ])
    summary = [["Product", "Sum of Revenue"]]
    totals = {}
    for record in rows[1:]:
        totals[record[2]] = totals.get(record[2], 0) + record[6]
    summary.extend([[product, value] for product, value in totals.items()])
    write_ods(os.path.join(out_dir, "home", "user", "BoomerangSales.ods"), "Sheet1", rows)
    write_ods(os.path.join(out_dir, "home", "user", "BoomerangSales_summary.ods"), "Sheet2", summary)


def state_21(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in SALES_ROWS:
        ws["G%d" % row] = "=VLOOKUP(C%d,'Retail Price'!$A$2:$B$23,2,0)*E%d*(1-F%d)" % (row, row, row)
    second = wb.create_sheet("Sheet2")
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (index + 2)) for index, product in enumerate(_products(wb))]
    _summary(second, rows)
    del wb["Sheet1"]
    _save(wb, out_dir)


def state_22(snapshot_dir, out_dir):
    copy_snapshot(snapshot_dir, out_dir)
    wb = _open(out_dir)
    ws = wb["Sheet1"]
    ws["G1"] = "Revenue"
    for row in range(2, 36):
        ws["G%d" % row] = "=VLOOKUP(C%d,'Retail Price'!$A$2:$B$23,2,0)*E%d*(1-F%d)" % (row, row, row)
    second = wb.create_sheet("Sheet2")
    rows = [(product, "=SUMIF($C$2:$C$36,A%d,$G$2:$G$36)" % (index + 2)) for index, product in enumerate(_products(wb))]
    _summary(second, rows)
    _save(wb, out_dir)
