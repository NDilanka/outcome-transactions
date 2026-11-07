"""Offline tests for com_gate.py: no Excel. A fake view stands in for the workbook; each write or read can be
scripted to be rejected (RPC_E_CALL_REJECTED), to fail, or to hang until the test releases it.

  py -3 windows\\unit1\\gate_offline_test.py
"""
import collections
import os
import sys
import threading
import time
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import com_gate as G  # noqa: E402

BUSY = G.BUSY_CODES[0]  # RPC_E_CALL_REJECTED
RETRY = G.BUSY_CODES[1]  # RPC_E_SERVERCALL_RETRYLATER
E_FAIL = -2147467259  # E_FAIL 0x80004005

FAST = dict(budget_s=1.0, call_budget_s=0.3, reconcile_budget_s=1.0, poll_s=0.05)


class ComErr(Exception):
    def __init__(self, hresult, text="COM error"):
        super().__init__(text)
        self.hresult = hresult


class Book:
    """The view: cells, an Application, and scripts. write_script[ref] is consumed one entry per write call:
    "ok", "busy" (rejected, nothing applied), "land-busy" (applied, then rejected), "user-busy" (a user value is
    written, then rejected), "error" (a non-busy error), ("hang", ev) (waits for ev, then applies the value),
    ("hang-nothing", ev) (waits for ev, applies nothing), ("hang-other", ev, value) (waits, applies value)."""

    def __init__(self, **cells):
        self.cells = dict(cells)
        self.app = types.SimpleNamespace(DisplayAlerts=True, Ready=True)
        self.Application = self.app  # the view exposes Application, as a worksheet does
        self.write_script = collections.defaultdict(list)
        self.read_script = collections.deque()  # "busy" or a threading.Event (the read waits for it)
        self.writes = []  # (ref, value, DisplayAlerts seen by the write)

    def read(self, ref):
        if self.read_script:
            f = self.read_script.popleft()
            if f == "busy":
                raise ComErr(BUSY, "read rejected")
            f.wait()
        return self.cells[ref]

    def write(self, ref, value):
        self.writes.append((ref, value, self.app.DisplayAlerts))
        beh = self.write_script[ref].pop(0) if self.write_script[ref] else "ok"
        if isinstance(beh, tuple):
            kind = beh[0]
            beh[1].wait()
            if kind == "hang":
                self.cells[ref] = value
            elif kind == "hang-other":
                self.cells[ref] = beh[2]
            return
        if beh == "ok":
            self.cells[ref] = value
            return
        elif beh == "busy":
            raise ComErr(BUSY, "rejected")
        elif beh == "land-busy":
            self.cells[ref] = value
            raise ComErr(BUSY, "rejected after applying")
        elif beh == "user-busy":
            self.cells[ref] = "user edit"
            raise ComErr(BUSY, "rejected after a user edit")
        elif beh == "error":
            raise ComErr(E_FAIL, "write failed")
        elif beh == "turned-away":  # pywin32's form of a refused member lookup: the write was never invoked
            raise AttributeError(f"budget.xlsx.{ref}")
        elif beh == "python-bug":
            raise AttributeError("'NoneType' object has no attribute 'Range'")
        raise AssertionError(beh)


def cell(ref, want):
    return G.Step(f"{ref} value", lambda v: v.read(ref), lambda v, x: v.write(ref, x), want)


def run(steps, book, **kw):
    return G.run_steps(steps, lambda: book, **{**FAST, **kw})


def release_after(ev, seconds):
    threading.Timer(seconds, ev.set).start()


# ready gate ---------------------------------------------------------------------------------------------------------

def test_gate_passes_when_ready():
    g = G.ready_gate(lambda: None, lambda v: True)
    assert g["ok"] and g["tries"] == 1 and g["reason"] is None


def test_gate_recovers_after_busy_probes_within_budget():
    calls = collections.Counter()

    def probe(v):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise ComErr(BUSY)
        return True
    g = G.ready_gate(lambda: None, probe, budget_s=2.0, poll_s=0.05)
    assert g["ok"] and g["tries"] == 3, g


def test_gate_refuses_excel_busy_past_budget():
    def probe(v):
        raise ComErr(BUSY)
    g = G.ready_gate(lambda: None, probe, budget_s=0.4, poll_s=0.05, call_budget_s=0.3)
    assert not g["ok"] and g["reason"] == "Excel busy" and g["tries"] > 1, g
    assert g["seconds"] < 1.5, g


def test_gate_refuses_when_ready_stays_false():
    g = G.ready_gate(lambda: None, lambda v: False, budget_s=0.3, poll_s=0.05)
    assert g["reason"] == "Excel busy" and g["last_error"] == "Application.Ready is False", g


def test_gate_refuses_non_busy_error_at_once():
    def probe(v):
        raise ComErr(E_FAIL)
    g = G.ready_gate(lambda: None, probe)
    assert g["reason"].startswith("Excel error") and g["tries"] == 1, g


def test_gate_refuses_not_responding_when_probe_hangs():
    ev = threading.Event()
    try:
        g = G.ready_gate(lambda: None, lambda v: ev.wait(), call_budget_s=0.2)
        assert not g["ok"] and g["reason"] == "Excel not responding", g
    finally:
        ev.set()


# timed calls --------------------------------------------------------------------------------------------------------

def test_gate_refuses_turned_away_member_lookup_as_busy():
    def probe(v):
        raise AttributeError("budget.xlsx.Application")  # pywin32 hides RPC_E_CALL_REJECTED behind this form
    g = G.ready_gate(lambda: None, probe, budget_s=0.3, poll_s=0.05)
    assert g["reason"] == "Excel busy" and "turned away" in g["last_error"], g


def test_step_retries_a_turned_away_lookup_that_did_not_apply():
    b = Book(B2=1000)
    b.write_script["B2"] = ["turned-away", "ok"]
    rep = run([cell("B2", 5000)], b)
    assert rep["status"] == "committed" and rep["rejections"] == 1 and len(b.writes) == 2, rep


def test_python_attribute_error_is_not_mistaken_for_busy():
    b = Book(B2=1000)
    b.write_script["B2"] = ["python-bug"]
    rep = run([cell("B2", 5000)], b)
    assert rep["status"] == "refused" and rep["rejections"] == 0 and len(b.writes) == 1, rep


def test_timed_returns_value():
    assert G.timed(lambda: 5, 1.0) == 5


def test_timed_maps_com_error_to_remote_error():
    try:
        G.timed(lambda: (_ for _ in ()).throw(ComErr(BUSY)), 1.0)
    except G.RemoteError as e:
        assert G.is_busy(e) and e.hresult == BUSY, e
        return
    raise AssertionError("no RemoteError")


def test_timed_hang_raises_not_responding_and_the_call_finishes_later():
    ev = threading.Event()
    try:
        G.timed(lambda: (ev.wait(), "late")[1], 0.2)
    except G.NotResponding as e:
        assert not e.call.finished()
        ev.set()
        assert e.call.wait(2.0) and e.call.result() == "late"
        return
    finally:
        ev.set()
    raise AssertionError("no NotResponding")


# checked steps ------------------------------------------------------------------------------------------------------

def test_step_retries_rejected_write_that_did_not_apply():
    b = Book(B2=1000)
    b.write_script["B2"] = ["busy", "ok"]
    rep = run([cell("B2", 5000)], b)
    assert rep["status"] == "committed" and rep["rejections"] == 1, rep
    assert [w[:2] for w in b.writes] == [("B2", 5000), ("B2", 5000)], b.writes
    assert b.cells["B2"] == 5000


def test_step_rejected_write_that_landed_is_done_without_second_write():
    b = Book(B2=1000)
    b.write_script["B2"] = ["land-busy"]
    rep = run([cell("B2", 5000)], b)
    assert rep["status"] == "committed" and rep["rejections"] == 1, rep
    assert len(b.writes) == 1, b.writes
    assert rep["checks"] == ["5000"], rep["checks"]


def test_step_user_edit_during_rejection_refuses_without_retry():
    b = Book(B2=1000)
    b.write_script["B2"] = ["user-busy"]
    rep = run([cell("B2", 5000)], b)
    assert rep["status"] == "refused" and "neither the value before" in rep["reason"], rep
    assert len(b.writes) == 1 and b.cells["B2"] == "user edit", b.cells


def test_step_busy_past_budget_refuses_and_target_unchanged():
    b = Book(B2=1000)
    b.write_script["B2"] = ["busy"] * 100
    rep = run([cell("B2", 5000)], b, budget_s=0.4)
    assert rep["status"] == "refused" and rep["reason"].startswith("busy: rejected"), rep
    assert b.cells["B2"] == 1000


def test_step_non_busy_error_is_not_retried():
    b = Book(B2=1000)
    b.write_script["B2"] = ["error"]
    rep = run([cell("B2", 5000)], b)
    assert rep["status"] == "refused" and rep["reason"].startswith("write error"), rep
    assert len(b.writes) == 1


def test_step_unreadable_target_refuses_before_writing():
    b = Book(B2=1000)
    b.read_script.extend(["busy"] * 1000)
    rep = run([cell("B2", 5000)], b, budget_s=0.3)
    assert rep["status"] == "refused" and rep["reason"].startswith("target unreadable before the write"), rep
    assert b.writes == []


def test_step_already_at_wanted_value_skips_write():
    b = Book(B2=5000)
    rep = run([cell("B2", 5000)], b)
    assert rep["status"] == "committed" and rep["done"] == ["B2 value (already)"], rep
    assert b.writes == []


def test_not_responding_before_the_write_refuses_without_writing():
    b = Book(B2=1000)
    ev = threading.Event()
    b.read_script.append(ev)
    try:
        rep = run([cell("B2", 5000)], b, call_budget_s=0.2)
    finally:
        ev.set()
    assert rep["status"] == "refused" and rep["reason"].startswith("Excel not responding before the B2 value write"), rep
    assert b.writes == [], b.writes


# guard and run_steps ------------------------------------------------------------------------------------------------

def test_guard_sets_alerts_off_for_the_writes_and_restores_them():
    b = Book(B2=1000)
    steps = G.guard([cell("B2", 5000)], {"DisplayAlerts": True}, {"DisplayAlerts": False})
    rep = run(steps, b)
    assert rep["status"] == "committed", rep
    assert b.writes[0][2] is False, b.writes  # alerts off when the cell is written
    assert b.app.DisplayAlerts is True
    assert rep["done"] == ["Application.DisplayAlerts set", "B2 value", "Application.DisplayAlerts restored"], rep["done"]


def test_guard_skips_properties_already_at_their_value():
    steps = G.guard([cell("B2", 5000)], {"DisplayAlerts": False}, {"DisplayAlerts": False})
    assert [s.label for s in steps] == ["B2 value"]


def test_run_steps_all_done_commits():
    b = Book(B2=1000, E2=2)
    rep = run([cell("B2", 5000), cell("E2", 6)], b)
    assert rep["status"] == "committed" and rep["message"] == "Committed.", rep
    assert b.cells["B2"] == 5000 and b.cells["E2"] == 6


def test_run_steps_refused_step_rolls_back_finished_steps():
    b = Book(B2=1000, E2=2)
    b.write_script["E2"] = ["error"]
    rep = run([cell("B2", 5000), cell("E2", 6)], b)
    assert rep["status"] == "refused" and b.cells["B2"] == 1000, rep
    assert rep["rollback"] == [dict(step="B2 value", status="written", reason=None)], rep["rollback"]
    assert rep["message"].endswith("Finished steps were rolled back."), rep["message"]


def test_guard_is_restored_when_a_write_is_refused():
    b = Book(B2=1000, E2=2)
    b.write_script["B2"] = ["error"]
    steps = G.guard([cell("B2", 5000)], {"DisplayAlerts": True}, {"DisplayAlerts": False})
    rep = run(steps, b)
    assert rep["status"] == "refused" and b.app.DisplayAlerts is True, rep


def test_rollback_failure_is_reported_as_partial():
    b = Book(B2=1000, E2=2)
    b.write_script["B2"] = ["ok", "error"]  # the rollback write of B2 fails
    b.write_script["E2"] = ["error"]
    rep = run([cell("B2", 5000), cell("E2", 6)], b)
    assert rep["status"] == "refused_partial", rep
    assert "not fully rolled back" in rep["message"], rep["message"]


def test_nothing_landed_says_nothing_was_written():
    b = Book(B2=1000)
    b.write_script["B2"] = ["error"]
    rep = run([cell("B2", 5000)], b)
    assert rep["message"] == "Refused: write error: ComErr 0x80004005. Nothing was written.", rep["message"]


def test_cells_come_from_step_labels_without_application_steps():
    steps = G.guard([cell("B2", 5000), cell("E2", 6)], {"DisplayAlerts": True}, {"DisplayAlerts": False})
    assert G._cells(steps) == ["B2", "E2"]


# timed-out writes: reconcile ----------------------------------------------------------------------------------------

def test_timed_out_write_that_lands_late_is_rolled_back():
    b = Book(B2=1000)
    ev = threading.Event()
    b.write_script["B2"] = [("hang", ev)]
    release_after(ev, 0.5)
    rep = run([cell("B2", 5000)], b, call_budget_s=0.3)
    assert rep["status"] == "refused", rep
    assert rep["late_landing"] == "landed after the timeout, rolled back", rep
    assert rep["reconcile"]["state"] == "landed" and rep["reconcile"]["returned"] is True, rep["reconcile"]
    assert b.cells["B2"] == 1000 and rep["rollback"][0]["status"] == "written", rep
    assert rep["message"].startswith("Refused: the B2 value write returned after the timeout")


def test_timed_out_write_that_never_lands_is_refused_as_unchanged():
    b = Book(B2=1000)
    ev = threading.Event()
    b.write_script["B2"] = [("hang-nothing", ev)]
    release_after(ev, 0.5)
    rep = run([cell("B2", 5000)], b, call_budget_s=0.3)
    assert rep["status"] == "refused" and rep["reconcile"]["state"] == "unchanged", rep
    assert "did not answer" in rep["reason"] and rep["late_landing"] is None, rep
    assert b.cells["B2"] == 1000


def test_timed_out_write_that_lands_another_value_is_left_as_it_is():
    b = Book(B2=1000)
    ev = threading.Event()
    b.write_script["B2"] = [("hang-other", ev, 777)]
    release_after(ev, 0.5)
    rep = run([cell("B2", 5000)], b, call_budget_s=0.3)
    assert rep["status"] == "refused" and rep["reconcile"]["state"] == "other", rep
    assert "holds 777" in rep["reason"], rep["reason"]
    assert b.cells["B2"] == 777, "a value we did not write is not overwritten"
    assert "Left as it is: B2" in rep["message"], rep["message"]


def test_unknown_outcome_reports_cells_and_leaves_them_then_restores_app_when_call_returns():
    b = Book(B2=1000)
    ev = threading.Event()
    b.write_script["B2"] = [("hang", ev)]
    steps = G.guard([cell("B2", 5000)], {"DisplayAlerts": True}, {"DisplayAlerts": False})
    try:
        rep = run(steps, b, call_budget_s=0.3, reconcile_budget_s=0.8)
        assert rep["status"] == "unknown", rep
        assert rep["reconcile"]["state"] == "unknown" and rep["reconcile"]["returned"] is False, rep["reconcile"]
        assert "Check B2 before you save" in rep["message"], rep["message"]
        assert b.app.DisplayAlerts is False, "alerts stay off while the commit's write is pending"
        assert rep["rollback"] == [], "no rollback while the write may still land"
        ev.set()
        deadline = time.monotonic() + 3
        while rep["app_restore"] is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert [x["status"] for x in rep["app_restore"]] == ["written"], rep["app_restore"]
        assert b.app.DisplayAlerts is True
    finally:
        ev.set()


def test_unknown_outcome_without_application_steps_has_no_restore():
    b = Book(B2=1000)
    ev = threading.Event()
    b.write_script["B2"] = [("hang", ev)]
    try:
        rep = run([cell("B2", 5000)], b, call_budget_s=0.3, reconcile_budget_s=0.5)
        assert rep["status"] == "unknown" and rep["app_restore"] is None, rep
    finally:
        ev.set()


def test_reconcile_polls_the_target_while_the_call_is_pending():
    b = Book(B2=1000)
    ev = threading.Event()
    b.write_script["B2"] = [("hang", ev)]
    release_after(ev, 0.7)
    rep = run([cell("B2", 5000)], b, call_budget_s=0.2, reconcile_budget_s=2.0)
    assert len(rep["reconcile"]["polls"]) >= 3, rep["reconcile"]["polls"]


def test_message_names_both_cells_when_unknown():
    b = Book(B2=1000, E2=2)
    ev = threading.Event()
    b.write_script["E2"] = [("hang", ev)]
    try:
        rep = run([cell("B2", 5000), cell("E2", 6)], b, call_budget_s=0.2, reconcile_budget_s=0.5)
        assert rep["status"] == "unknown" and "Check B2 and E2 before you save" in rep["message"], rep["message"]
        assert rep["done"] == ["B2 value"], rep["done"]
    finally:
        ev.set()


def test_refused_message_wording_when_a_timed_out_write_landed_and_rolled_back():
    b = Book(B2=1000)
    ev = threading.Event()
    b.write_script["B2"] = [("hang", ev)]
    release_after(ev, 0.5)
    rep = run([cell("B2", 5000)], b, call_budget_s=0.3)
    assert rep["message"].endswith("Finished steps were rolled back."), rep["message"]


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]


def main():
    failed = []
    for fn in TESTS:
        t0 = time.monotonic()
        try:
            fn()
            print(f"PASS {fn.__name__} ({time.monotonic() - t0:.1f} s)")
        except Exception as e:  # report every failure, then exit non-zero
            failed.append(fn.__name__)
            print(f"FAIL {fn.__name__}: {type(e).__name__}: {e}")
    print(f"{len(TESTS) - len(failed)}/{len(TESTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
