"""Checks that the commit preflight refuses to write while Excel holds the real workbook.

Opens the workspace's budget.xlsx in Excel, then calls the scenario commit path. Expected: the outcome is
routed_to_owner and the file's bytes do not change. Launches one Excel instance and closes it.

  py -3 windows\\unit2\\preflight_owner_check.py
"""
import hashlib
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import make_workspace as MW  # noqa: E402
import scenarios as S  # noqa: E402
from excel_com import ExcelSession  # noqa: E402


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    os.makedirs(S.WORK, exist_ok=True)
    root = tempfile.mkdtemp(prefix="preflight-", dir=S.WORK)
    real = os.path.join(root, "real")
    fork = os.path.join(root, "fork")
    MW.build(real)
    shutil.copytree(real, fork)
    xlsx = os.path.join(real, "budget.xlsx")
    before = sha(xlsx)
    scenario = S.Scenario("normal", "excel")
    scenario.real = real
    with ExcelSession() as xl:
        xl.open(xlsx)
        outcome = scenario._commit(fork, ["budget.xlsx"], before=None)
        preflight = scenario.res.get("commit_preflight")
    after = sha(xlsx)
    assert outcome == "routed_to_owner", outcome
    assert preflight["holders"] and preflight["lock_file"] is not None, preflight
    assert before == after, "file changed while Excel held it"
    print(f"routed_to_owner with Excel open: holders={preflight['holders']}, file unchanged={before == after}")


if __name__ == "__main__":
    main()
