"""Fork method through Excel COM: sets B2 to 5000 in the fork's copy, saves, and writes out/q3.csv from the
values Excel reports. Not run by the offline tests."""
import os
import sys

from excel_com import ExcelSession, com_cells
from xlsx_edit import write_csv


def main():
    fork = sys.argv[1]
    path = os.path.join(fork, "budget.xlsx")
    with ExcelSession() as xl:
        wb = xl.open(path)
        ws = wb.Worksheets("Q3")
        ws.Range("B2").Value = 5000
        wb.Save()
        cells = com_cells(ws)
        wb.Close(False)
    write_csv(cells, os.path.join(fork, "out", "q3.csv"))


if __name__ == "__main__":
    main()
