"""Fork method: the programmatic edit. Applies the unit 1 agent edit (B2 1000 -> 5000), then writes out/q3.csv."""
import os
import sys

from open_doc_experiment import agent_bytes, commit_file
from otx_win import xlsx_cells
from xlsx_edit import write_csv


def main():
    fork = sys.argv[1]
    path = os.path.join(fork, "budget.xlsx")
    rec = commit_file("replace", path, agent_bytes("xlsx", path))
    if not rec["write_ok"]:
        raise SystemExit(rec["error"])
    write_csv(xlsx_cells(path), os.path.join(fork, "out", "q3.csv"))


if __name__ == "__main__":
    main()
