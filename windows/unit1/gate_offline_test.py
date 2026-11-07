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

G.RESTORE_RETRY_S = 0.05  # the restore retries run fast in tests

BUSY = G.BUSY_CODES[0]  # RPC_E_CALL_REJECTED
RETRY = G.BUSY_CODES[1]  # RPC_E_SERVERCALL_RETRYLATER
E_FAIL = -2147467259  # E_FAIL 0x80004005
E_UNAVAILABLE = -2147221021  # OLE_E_NOTRUNNING-style "Operation unavailable": the workbook is no longer open

FAST = dict(budget_s=1.0, call_budget_s=0.3, reconcile_budget_s=1.0, poll_s=0.05)


class ComErr(Exception):
    def __init__(self, hresult, text="COM error"):
        super().__init__(text)
        self.hresult = hresult


class ComDispErr(Exception):
    """pywin32's form of an automation error: DISP_E_EXCEPTION, with Excel's own code in excepinfo[5] (scode)."""

    def __init__(self, scode, text="Exception occurred."):
        super().__init__(text)
        self.hresult = G.DISP_E_EXCEPTION
        self.args = (G.DISP_E_EXCEPTION, text, (0, None, None, None, 0, scode), None)


MODAL_BUSY = -2146777998  # 0x800AC472: "waiting for another application to complete an OLE action" (dialog open)


class BusyApp:
    """The Application object. While busy, Excel turns away every call on it. Once closed, calls fail with a
    non-busy error, as they do after the workbook is closed and Excel no longer answers through it."""

    def __init__(self):
        self.Ready = True
        self.busy = False
        self.closed = False
        self._alerts = True

    def _check(self):
        if self.closed:
            raise ComErr(E_UNAVAILABLE, "Operation unavailable")
        if self.busy:
            raise ComErr(BUSY, "rejected")

    @property
    def DisplayAlerts(self):
        self._check()
        return self._alerts

    @DisplayAlerts.setter
    def DisplayAlerts(self, v):
        self._check()
        self._alerts = v


class Book:
    """The view: cells, an Application, and scripts. write_script[ref] is consumed one entry per write call:
    "ok", "busy" (rejected, nothing applied), "land-busy" (applied, then rejected), "user-busy" (a user value is
    written, then rejected), "error" (a non-busy error), "app-busy" (Excel turns away this and every later call on the
    application, and the write itself is rejected), ("hang", ev) (waits for ev, then applies the value),
    ("hang-nothing", ev) (waits for ev, applies nothing), ("hang-other", ev, value) (waits, applies value),
    ("hang-busy", ev) (waits, then is rejected busy, applies nothing)."""

    def __init__(self, **cells):
        self.cells = dict(cells)
        self.app = BusyApp()
        self.Application = self.app  # the view exposes Application, as a worksheet does
        self.write_script = collections.defaultdict(list)
        self.read_script = collections.deque()  # "busy" or a threading.Event (the read waits for it)
        self.writes = []  # (ref, value, DisplayAlerts seen by the write)

    def read(self, ref):
        if self.read_script:
            f = self.read_script.popleft()
            if f == "busy":
                raise ComErr(BUSY, "read rejected")
            if f == "fail":
                raise ComErr(E_FAIL, "read failed")
            if f != "pass":
                f.wait()
        return self.cells[ref]

    def write(self, ref, value):
        self.writes.append((ref, value, self.app._alerts))
        beh = self.write_script[ref].pop(0) if self.write_script[ref] else "ok"
        if isinstance(beh, tuple):
            kind = beh[0]
            beh[1].wait()
            if kind == "hang":
                self.cells[ref] = value
            elif kind == "hang-other":
                self.cells[ref] = beh[2]
            elif kind == "hang-busy":  # the call returns busy after the wait, and nothing is applied
                raise ComErr(BUSY, "rejected after the wait")
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
        elif beh == "land-error":  # applied, then an error that is not busy
            self.cells[ref] = value
            raise ComErr(E_FAIL, "write failed after applying")
        elif beh == "app-busy":
            self.app.busy = True
            raise ComErr(BUSY, "rejected; the application is busy")
        elif beh == "modal-busy":  # Excel with a dialog up: the write is refused with 0x800AC472, nothing applied
            raise ComDispErr(MODAL_BUSY)
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
    assert g["reason"] == "Excel busy" and "turned the call away" in g["last_error"], g


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
    assert rep["message"].startswith("Refused, and not fully rolled back: ") and rep["message"].endswith(
        "Check B2 and E2."), rep["message"]


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


def test_timed_out_write_that_returns_busy_with_target_unchanged_is_refused_as_rejected():
    b = Book(B2=1000)
    ev = threading.Event()
    b.write_script["B2"] = [("hang-busy", ev)]
    release_after(ev, 0.5)
    rep = run([cell("B2", 5000)], b, call_budget_s=0.3)
    assert rep["status"] == "refused" and rep["reconcile"]["state"] == "rejected", rep
    assert rep["reason"].startswith("busy: rejected") and rep["rejections"] == 1 and rep["unconfirmed"] is None, rep
    assert rep["late_landing"] is None and b.cells["B2"] == 1000, rep
    assert rep["message"].startswith("Refused: busy: rejected"), rep["message"]


def test_timed_out_write_that_returns_busy_and_cannot_be_read_back_is_unconfirmed():
    b = Book(B2=1000)
    ev = threading.Event()
    b.write_script["B2"] = [("hang-busy", ev)]
    b.read_script.extend(["pass"] + ["busy"] * 500)  # the pre-write read passes; every read after it is turned away
    release_after(ev, 0.5)
    rep = run([cell("B2", 5000)], b, call_budget_s=0.3)
    assert rep["status"] == "refused" and rep["reconcile"]["state"] == "rejected", rep
    assert rep["reconcile"]["confirmed"] is False and rep["reason"].startswith("busy: rejected"), rep
    assert rep["unconfirmed"] == ["B2"] and rep["rejections"] == 1 and b.cells["B2"] == 1000, rep
    assert "Check B2 before you save" in rep["message"] and "did not return" not in rep["message"], rep["message"]


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
        assert [x["status"] for x in rep["app_restore"]] == ["restored"], rep["app_restore"]
        assert rep["app_restore_state"] == "restored" and b.app.DisplayAlerts is True, rep
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


# restore of application properties --------------------------------------------------------------------------------------

def wait_while(rep, state, seconds=5.0):
    """Wait while the restore state equals `state` (for example "pending"). Returns the state it left."""
    deadline = time.monotonic() + seconds
    while rep["app_restore_state"] == state and time.monotonic() < deadline:
        time.sleep(0.02)
    return rep["app_restore_state"]


def test_refused_commit_whose_alerts_restore_is_turned_away_is_restored_when_excel_answers():
    b = Book(B2=1000)
    b.write_script["B2"] = ["app-busy"] + ["busy"] * 500
    steps = G.guard([cell("B2", 5000)], {"DisplayAlerts": True}, {"DisplayAlerts": False})
    threading.Timer(0.8, lambda: setattr(b.app, "busy", False)).start()
    rep = run(steps, b, budget_s=0.4, call_budget_s=0.3)
    assert rep["status"] == "refused" and b.cells["B2"] == 1000, rep
    assert rep["app_restore_state"] == "pending" and b.app._alerts is False, rep  # Excel is busy: no property reads
    assert "Excel alerts are temporarily off" in rep["message"], rep["message"]
    assert wait_while(rep, "pending") == "restored", rep["restore_log"]
    assert b.app.DisplayAlerts is True
    actions = [x["action"] for x in rep["restore_log"]]
    assert actions[0] == "turned away" and actions[-1] == "restored", actions
    assert all(x["step"] == "Application.DisplayAlerts set" for x in rep["restore_log"]), rep["restore_log"]


def test_restore_stops_when_the_workbook_is_closed():
    b = Book(B2=1000)
    b.write_script["B2"] = ["app-busy"] + ["busy"] * 500
    steps = G.guard([cell("B2", 5000)], {"DisplayAlerts": True}, {"DisplayAlerts": False})
    rep = run(steps, b, budget_s=0.4, call_budget_s=0.3)
    assert rep["app_restore_state"] == "pending", rep
    b.app.closed = True
    state = wait_while(rep, "pending")
    assert state.startswith("stopped: "), (state, rep["restore_log"])
    count = len(rep["restore_log"])
    time.sleep(0.4)
    assert len(rep["restore_log"]) == count, "no attempt after the workbook closed"
    assert rep["restore_log"][-1]["action"] == "stopped", rep["restore_log"][-1]


def test_restore_stops_when_excel_has_exited():
    b = Book(B2=1000)
    b.write_script["B2"] = ["app-busy"] + ["busy"] * 500
    steps = G.guard([cell("B2", 5000)], {"DisplayAlerts": True}, {"DisplayAlerts": False})
    rep = run(steps, b, budget_s=0.4, call_budget_s=0.3, app_alive=lambda: False)
    assert rep["app_restore_state"] == "stopped: Excel exited", rep
    assert rep["restore_log"] and rep["restore_log"][-1]["detail"] == "Excel exited", rep["restore_log"]
    assert "Excel alerts may still be off: Excel exited." in rep["message"], rep["message"]


def test_restore_leaves_a_value_someone_else_set():
    b = Book(B2=1)
    b.app.Zoom = 100  # the value before the commit
    set_step = G.prop_step("Zoom", 200)  # the commit set 200
    b.app.Zoom = 300  # someone else changed it after that
    ctx = G._Ctx(lambda: b, 1.0, 0.3, time.monotonic, time.sleep, 0.05)
    action, detail = G._restore_once(set_step, 100, ctx)
    assert action == "left" and b.app.Zoom == 300, (action, detail, b.app.Zoom)
    assert "holds 300" in detail, detail


def test_restore_writes_back_only_the_value_the_commit_set():
    b = Book(B2=1)
    b.app.Zoom = 200  # the commit's value still in place
    set_step = G.prop_step("Zoom", 200)
    ctx = G._Ctx(lambda: b, 1.0, 0.3, time.monotonic, time.sleep, 0.05)
    action, _ = G._restore_once(set_step, 100, ctx)
    assert action == "restored" and b.app.Zoom == 100, (action, b.app.Zoom)


# time bounds and late outcomes ----------------------------------------------------------------------------------------

def test_gate_probe_cannot_outlast_the_gate_budget():
    ev = threading.Event()
    try:
        start = time.monotonic()
        g = G.ready_gate(lambda: None, lambda v: ev.wait(), budget_s=0.3, poll_s=0.05, call_budget_s=5.0)
        elapsed = time.monotonic() - start
    finally:
        ev.set()
    assert g["reason"] == "Excel not responding" and elapsed < 1.0, (g, elapsed)


def test_ready_gate_respects_an_absolute_deadline():
    start = time.monotonic()
    g = G.ready_gate(lambda: None, lambda v: False, budget_s=5.0, until=start + 0.3)
    assert g["reason"] == "Excel busy" and time.monotonic() - start < 1.0, g


def test_write_error_after_applying_is_read_back_and_rolled_back():
    b = Book(B2=1000)
    b.write_script["B2"] = ["land-error"]
    rep = run([cell("B2", 5000)], b)
    assert rep["status"] == "refused" and rep["reason"].startswith("write error") and "holds 5000" in rep["reason"], rep
    assert b.cells["B2"] == 1000 and rep["rollback"][0]["status"] == "written", rep
    assert rep["message"].endswith("Finished steps were rolled back."), rep["message"]


def test_write_whose_read_back_fails_is_rolled_back():
    b = Book(B2=1000)
    b.read_script.extend(["pass", "fail"])  # the pre-write read passes, the read-back after the write fails
    rep = run([cell("B2", 5000)], b)
    assert rep["status"] == "refused" and "could not be read back" in rep["reason"], rep
    assert b.cells["B2"] == 1000 and rep["rollback"][0]["status"] == "written", rep


def test_forward_deadline_stops_the_retry_of_a_rejected_write():
    b = Book(B2=1000)
    b.write_script["B2"] = ["busy"] * 1000
    start = time.monotonic()
    rep = run([cell("B2", 5000)], b, budget_s=10.0, forward_until=time.monotonic() + 0.5)
    elapsed = time.monotonic() - start
    assert rep["status"] == "refused" and rep["reason"].startswith("busy: rejected"), rep
    assert elapsed < 1.5 and len(b.writes) < 50, (elapsed, len(b.writes))


def test_write_is_not_started_when_its_full_call_budget_no_longer_fits():
    b = Book(B2=1000)
    rep = run([cell("B2", 5000)], b, call_budget_s=0.3, forward_until=time.monotonic() + 0.2)
    assert rep["status"] == "refused" and rep["reason"] == "out of time before the write began", rep
    assert b.writes == [] and rep["rejections"] == 0, rep


def test_forward_deadline_bounds_an_unknown_outcome():
    b = Book(B2=1000)
    ev = threading.Event()
    b.write_script["B2"] = [("hang", ev)]
    try:
        start = time.monotonic()
        rep = run([cell("B2", 5000)], b, call_budget_s=0.3, reconcile_budget_s=20.0,
                  forward_until=time.monotonic() + 0.6)
        elapsed = time.monotonic() - start
        assert rep["status"] == "unknown" and elapsed < 1.5, (rep["status"], elapsed)
    finally:
        ev.set()


def test_answer_deadline_bounds_the_rollback():
    b = Book(B2=1000, E2=2)
    ev = threading.Event()
    b.write_script["B2"] = ["ok", ("hang-nothing", ev)]  # the rollback write of B2 never returns
    b.write_script["E2"] = ["error"]
    try:
        start = time.monotonic()
        rep = run([cell("B2", 5000), cell("E2", 6)], b, call_budget_s=5.0,
                  answer_until=time.monotonic() + 0.8)
        elapsed = time.monotonic() - start
        assert rep["status"] == "refused_partial" and elapsed < 1.5, (rep["status"], elapsed, rep["rollback"])
    finally:
        ev.set()


def wait_late(rep, seconds=3.0):
    """Wait until the late outcome of an unknown write is recorded (state pending is replaced)."""
    deadline = time.monotonic() + seconds
    while rep.get("late_outcome", {}).get("state") in (None, "pending") and time.monotonic() < deadline:
        time.sleep(0.02)
    return rep.get("late_outcome")


def test_late_landing_after_unknown_is_recorded_and_left_in_place():
    b = Book(B2=1000)
    ev = threading.Event()
    b.write_script["B2"] = [("hang", ev)]
    try:
        rep = run([cell("B2", 5000)], b, call_budget_s=0.3, reconcile_budget_s=0.5)
        assert rep["status"] == "unknown", rep
        ev.set()
        late = wait_late(rep)
        assert late["state"] == "landed" and b.cells["B2"] == 5000, (late, b.cells)
        assert rep["rollback"] == [], "an unknown write is reported, not rolled back"
    finally:
        ev.set()


def test_late_nothing_after_unknown_is_recorded():
    b = Book(B2=1000)
    ev = threading.Event()
    b.write_script["B2"] = [("hang-nothing", ev)]
    try:
        rep = run([cell("B2", 5000)], b, call_budget_s=0.3, reconcile_budget_s=0.5)
        assert rep["status"] == "unknown", rep
        ev.set()
        late = wait_late(rep)
        assert late["state"] == "unchanged" and b.cells["B2"] == 1000, late
    finally:
        ev.set()


# the application's name in messages (Excel or Word) -------------------------------------------------------------------

def test_ready_gate_names_the_application_in_its_reason():
    def probe(v):
        raise ComErr(BUSY)
    g = G.ready_gate(lambda: None, probe, budget_s=0.2, poll_s=0.05, call_budget_s=0.3, app="Word")
    assert g["reason"] == "Word busy", g


def test_refused_message_names_word_and_says_its_alerts_are_temporarily_off():
    b = Book(B2=1000)
    b.write_script["B2"] = ["app-busy"] + ["busy"] * 500
    steps = G.guard([cell("B2", 5000)], {"DisplayAlerts": True}, {"DisplayAlerts": False})
    threading.Timer(0.8, lambda: setattr(b.app, "busy", False)).start()
    rep = run(steps, b, budget_s=0.4, call_budget_s=0.3, app="Word")
    assert rep["status"] == "refused" and "Word alerts are temporarily off" in rep["message"], rep["message"]
    assert "Excel" not in rep["message"], rep["message"]
    assert wait_while(rep, "pending") == "restored", rep["restore_log"]


def test_a_label_with_several_words_names_the_cell_in_the_unknown_message():
    b = Book(B2=1000)
    ev = threading.Event()
    b.write_script["B2"] = [("hang", ev)]
    total = G.Step("total line value", lambda v: v.read("B2"), lambda v, x: v.write("B2", x), 5000)
    try:
        rep = run([total], b, call_budget_s=0.2, reconcile_budget_s=0.5)
        assert rep["status"] == "unknown" and "Check total line before you save" in rep["message"], rep["message"]
    finally:
        ev.set()


# Excel busy in two more shapes: Ready = False with no error, and 0x800AC472 ------------------------------------------

class ReadyFalseApp:
    """The Application as Excel answers it with a dialog up: Ready is False, with no error. With ready_at set, Ready
    turns True on the ready_at-th read."""

    def __init__(self, ready_at=None):
        self.reads = 0
        self.ready_at = ready_at

    @property
    def Ready(self):
        self.reads += 1
        return self.ready_at is not None and self.reads >= self.ready_at

    @property
    def Name(self):
        return "Microsoft Excel"


class ReadyView:
    def __init__(self, app):
        self.Application = app
        self.cells = {"B2": 1000.0}

    def Range(self, ref):
        return types.SimpleNamespace(Value=self.cells[ref])


def test_gate_refuses_when_the_production_probe_sees_ready_false_without_an_error():
    import open_doc_experiment as X  # the probe the commit uses, unchanged
    view = ReadyView(ReadyFalseApp())
    g = G.ready_gate(lambda: view, X.excel_ready_probe, budget_s=0.3, poll_s=0.05, call_budget_s=0.3)
    assert not g["ok"] and g["reason"] == "Excel busy" and g["last_error"] == "Application.Ready is False", g
    assert g["tries"] > 1 and g["seconds"] < 1.5, g


def test_gate_passes_once_the_production_probe_sees_ready_again():
    import open_doc_experiment as X
    view = ReadyView(ReadyFalseApp(ready_at=3))
    g = G.ready_gate(lambda: view, X.excel_ready_probe, budget_s=2.0, poll_s=0.05, call_budget_s=0.3)
    assert g["ok"] and g["tries"] == 3, g


def test_0x800AC472_is_busy_and_another_scode_is_not():
    busy = G.remote_error(ComDispErr(MODAL_BUSY))
    assert busy.hresult == MODAL_BUSY and G.is_busy(busy), busy
    assert "0x800AC472" in G.describe(busy), G.describe(busy)
    declined = G.remote_error(ComDispErr(-2146827284))  # a SaveAs that the user declined: not busy
    assert not G.is_busy(declined), declined


def test_write_refused_with_0x800AC472_is_retried_and_commits():
    b = Book(B2=1000)
    b.write_script["B2"] = ["modal-busy"]  # one refusal, nothing applied, then the write goes through
    rep = run([cell("B2", 5000)], b)
    assert rep["status"] == "committed" and rep["rejections"] == 1 and b.cells["B2"] == 5000, rep


def test_write_refused_with_0x800AC472_past_the_budget_is_refused_busy_and_nothing_is_written():
    b = Book(B2=1000)
    b.write_script["B2"] = ["modal-busy"] * 500
    rep = run([cell("B2", 5000)], b, budget_s=0.4)
    assert rep["status"] == "refused" and rep["reason"].startswith("busy: rejected"), rep
    assert b.cells["B2"] == 1000 and "Nothing was written" in rep["message"], rep


def test_write_turned_away_with_no_read_back_is_unconfirmed_and_not_reported_as_unwritten():
    b = Book(B2=1000)
    b.read_script.extend(["pass"] + ["busy"] * 500)  # the pre-write read passes; every read after the rejection is busy
    b.write_script["B2"] = ["modal-busy"]
    rep = run([cell("B2", 5000)], b, budget_s=0.4)
    assert rep["status"] == "refused" and rep["unconfirmed"] == ["B2"], rep
    assert rep["reason"].startswith("busy: rejected (ComDispErr 0x800AC472)"), rep["reason"]
    assert "Check B2 before you save" in rep["message"] and "Nothing was written" not in rep["message"], rep["message"]


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
