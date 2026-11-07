"""Fork method: a plausible wrong edit. Sets B3 to 5000 instead of B2, then writes out/q3.csv."""
import os
import sys

from otx_win import xlsx_cells
from xlsx_edit import set_number, write_csv


def main():
    fork = sys.argv[1]
    path = os.path.join(fork, "budget.xlsx")
    set_number(path, "B3", 5000)
    write_csv(xlsx_cells(path), os.path.join(fork, "out", "q3.csv"))


if __name__ == "__main__":
    main()
