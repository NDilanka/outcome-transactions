"""Fork null control through Excel COM: opens and closes the copy with no edit. Whatever Excel leaves
behind is app noise. Not run by the offline tests."""
import os
import sys

from excel_com import ExcelSession


def main():
    fork = sys.argv[1]
    with ExcelSession() as xl:
        xl.open(os.path.join(fork, "budget.xlsx")).Close(False)


if __name__ == "__main__":
    main()
