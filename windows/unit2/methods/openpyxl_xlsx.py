"""Fork method: the second Excel-capable edit, through openpyxl and no COM.

Sets Q3!B2 to 5000 in the fork's copy, saves it, then writes out/q3.csv from the openpyxl workbook's values.
It shares no code path with the COM method. The CSV writer is the only shared piece, and it takes plain cells.
"""
import os
import sys

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from xlsx_edit import write_csv  # noqa: E402


def main():
    fork = sys.argv[1]
    path = os.path.join(fork, "budget.xlsx")
    wb = openpyxl.load_workbook(path)
    ws = wb["Q3"]
    ws["B2"] = 5000
    wb.save(path)
    cells = {c.coordinate: c.value for row in ws.iter_rows() for c in row if c.value is not None}
    write_csv(cells, os.path.join(fork, "out", "q3.csv"))


if __name__ == "__main__":
    main()
