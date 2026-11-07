"""Offline checks for the Unit 2 backend. Office COM is refused in this process and in offline forks.

  py -3 windows/unit2/tests_offline.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "unit1"))
sys.path.insert(0, HERE)

import backend as B  # noqa: E402
import make_workspace as MW  # noqa: E402
import otx_win  # noqa: E402
import spec_win as SW  # noqa: E402
import xlsx_edit as XE  # noqa: E402
from scenarios import MUTANTS, SPEC, make_mutant  # noqa: E402

UNIT1_BASE = os.path.join(os.path.dirname(HERE), "unit1", "base", "budget.xlsx")
OFFICE = ("EXCEL.EXE", "WINWORD.EXE")
TMP = tempfile.mkdtemp(prefix="unit2-tests-")
PROBE = """
import socket, sys
sys.path.insert(0, {here!r})
import fork_runner
fork_runner.install_guard()
for call in (lambda: socket.create_connection(("127.0.0.1", 9), timeout=1),
             lambda: socket.socket().connect(("127.0.0.1", 9))):
    try:
        call()
        print("connected")
    except OSError as e:
        print(e)
"""


def _dir(*parts):
    d = os.path.join(TMP, *parts)
    os.makedirs(d, exist_ok=True)
    return d


def _workspace(name):
    real = os.path.join(_dir(name), "real")
    MW.build(real)
    snap = os.path.join(_dir(name), "snap")
    B.snapshot(real, snap)
    return real, snap


def _xlsx_copy(src_file, name, edits):
    d = _dir("overlap", name)
    dst = os.path.join(d, "budget.xlsx")
    shutil.copy2(src_file, dst)
    for ref, val in edits:
        XE.set_number(dst, ref, val)
    return dst


def test_workspace_layout():
    real, _ = _workspace("layout")
    xlsx = os.path.join(real, "budget.xlsx")
    cells = otx_win.xlsx_cells(xlsx)
    assert cells["A1"] == "Item" and cells["B1"] == "Q1" and cells["D1"] == "Q3", cells.get("A1")
    assert cells["B2"] == 1000.0 and cells["A41"] == "item39" and cells["D41"] > 0
    assert "E1" not in cells and "A42" not in cells
    with zipfile.ZipFile(xlsx) as z:
        assert b'name="Q3"' in z.read("xl/workbook.xml")
        assert b'<c r="A1" s="1" t="s">' in z.read("xl/worksheets/sheet1.xml")
    with open(os.path.join(real, "notes.txt"), encoding="utf-8", newline="") as f:
        assert f.read() == "meeting notes\n"
    assert os.path.exists(os.path.join(real, "out", ".keep"))


def test_spec_accepts_only_the_correct_outcome():
    _, snap = _workspace("spec")
    for name, edits, csv, notes, expect in MUTANTS:
        d = os.path.join(TMP, "spec", "mut", name)
        shutil.copytree(snap, d)
        make_mutant(d, edits, csv, notes)
        ok, reasons, _ = SW.evaluate(SPEC, snap, d)
        assert ok == expect, (name, reasons)
        assert expect or reasons, name


def test_direct_and_wrong_on_unit1_base():
    snap = _dir("base_snap")
    shutil.copy2(UNIT1_BASE, os.path.join(snap, "budget.xlsx"))
    os.makedirs(os.path.join(snap, "out"))
    before = B.tree_hashes(os.path.dirname(UNIT1_BASE))
    direct = B.run_fork("direct_xlsx", snap, os.path.join(TMP, "base_direct"))
    assert direct["rc"] == 0, direct["stderr_tail"]
    cells = otx_win.xlsx_cells(os.path.join(TMP, "base_direct", "budget.xlsx"))
    assert cells["B2"] == 5000.0 and cells["B3"] == 250.0
    assert "5000" in open(os.path.join(TMP, "base_direct", "out", "q3.csv"), encoding="utf-8").read()
    wrong = B.run_fork("wrong_xlsx", snap, os.path.join(TMP, "base_wrong"))
    assert wrong["rc"] == 0, wrong["stderr_tail"]
    cells = otx_win.xlsx_cells(os.path.join(TMP, "base_wrong", "budget.xlsx"))
    assert cells["B2"] == 1000.0 and cells["B3"] == 5000.0
    assert B.tree_hashes(os.path.dirname(UNIT1_BASE)) == before, "unit1 base was modified"


def test_office_com_refused_in_process():
    import win32com.client

    try:
        win32com.client.DispatchEx("Excel.Application")
    except RuntimeError as e:
        assert "disabled" in str(e), e
    else:
        raise AssertionError("DispatchEx was not refused")


def test_offline_fork_refuses_office_com():
    snap = _dir("com_snap")
    shutil.copy2(UNIT1_BASE, os.path.join(snap, "budget.xlsx"))
    os.makedirs(os.path.join(snap, "out"))
    r = B.run_fork("com_null", snap, os.path.join(TMP, "com_refused"), refuse_office=True)
    assert r["rc"] != 0 and "Office COM is disabled" in r["stderr_tail"], r["stderr_tail"]
    assert r["network"].get("office_com") == "refused", r["network"]


def test_socket_guard_blocks_connect():
    out = subprocess.run([sys.executable, "-c", PROBE.format(here=HERE)], capture_output=True, text=True,
                         cwd=TMP).stdout
    assert out.splitlines() == ["network disabled in fork", "network disabled in fork"], out


def test_overlap_same_cell_is_true_conflict():
    base_ws, _ = _workspace("overlap_base")
    base = os.path.join(base_ws, "budget.xlsx")
    user = _xlsx_copy(base, "user_same", [("B2", 77)])
    win = _xlsx_copy(base, "win_same", [("B2", 5000)])
    m = SW.merge_test(base, user, win)
    assert m["outcome"] == "true_conflict" and m["overlap"] == ["B2"], m


def test_overlap_disjoint_is_no_conflict():
    base_ws, _ = _workspace("overlap_disjoint")
    base = os.path.join(base_ws, "budget.xlsx")
    user = _xlsx_copy(base, "user_disjoint", [("C3", 77)])
    win = _xlsx_copy(base, "win_disjoint", [("B2", 5000)])
    m = SW.merge_test(base, user, win)
    assert m == dict(outcome="no_conflict", overlap=[], user_cells=["C3"], winner_cells=["B2"]), m


def test_snapshot_hashes_match_copy():
    real = os.path.join(_dir("snapcheck"), "real")
    MW.build(real)
    snap = os.path.join(_dir("snapcheck"), "snap")
    hashes = B.snapshot(real, snap)
    assert hashes == B.tree_hashes(real) == B.tree_hashes(snap)
    os.makedirs(os.path.join(snap, B.SCRATCH))
    with open(os.path.join(snap, B.SCRATCH, "x.tmp"), "w", encoding="utf-8") as f:
        f.write("scratch")
    assert not any(k.startswith(B.SCRATCH) for k in B.tree_hashes(snap))


def test_rm_holders_and_lock_clear_for_unopened_workspace():
    real, _ = _workspace("preflight")
    assert otx_win.rm_holders(os.path.join(real, "budget.xlsx")) == []
    assert otx_win.lock_info(os.path.join(real, "budget.xlsx")) is None


def test_csv_from_cells_orders_rows_and_columns():
    assert XE.csv_from_cells({"B2": 2.5, "A1": "x", "B1": 1000.0, "A2": "y"}) == "x,1000\ny,2.5\n"
    assert XE.csv_from_cells({"A1": "x", "C1": 3.0}) == "x,,3\n"


def test_set_number_refuses_text_cell():
    real, _ = _workspace("text_cell")
    xlsx = os.path.join(real, "budget.xlsx")
    before = B.tree_hashes(real)
    try:
        XE.set_number(xlsx, "A1", 5)
    except ValueError:
        pass
    else:
        raise AssertionError("set_number wrote into a text cell")
    assert B.tree_hashes(real) == before


TESTS = [
    test_workspace_layout,
    test_spec_accepts_only_the_correct_outcome,
    test_direct_and_wrong_on_unit1_base,
    test_office_com_refused_in_process,
    test_offline_fork_refuses_office_com,
    test_socket_guard_blocks_connect,
    test_overlap_same_cell_is_true_conflict,
    test_overlap_disjoint_is_no_conflict,
    test_snapshot_hashes_match_copy,
    test_rm_holders_and_lock_clear_for_unopened_workspace,
    test_csv_from_cells_orders_rows_and_columns,
    test_set_number_refuses_text_cell,
]


def main():
    B.refuse_office_com()
    office_before = {img: otx_win.image_pids(img) for img in OFFICE}
    passed = 0
    for t in TESTS:
        try:
            t()
            passed += 1
            print("PASS", t.__name__)
        except Exception as e:
            print("FAIL", t.__name__, repr(e)[:400])
    started = {img: sorted(otx_win.image_pids(img) - office_before[img]) for img in OFFICE}
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"{passed}/{len(TESTS)} passed; new Office pids during run: {started} "
          f"(Office COM is refused in-process and in offline forks, so any pid here is another session)")
    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    sys.exit(main())
