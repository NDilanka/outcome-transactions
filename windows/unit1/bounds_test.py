"""Worst-case time to answer for the in-app Excel commit, with the production budgets.

Each scenario runs the commit's own path from com_gate.py (readiness gate, befores, guard, checked writes, reconcile,
rollback, restore) with the real constants, against a fake workbook scripted to be busy, slow or to hang. The clock
starts when the commit starts, as in Excel.live_agent. The state of the report is read when the commit answers, and
again after the scenario releases its hung calls. Real Excel timings are in results/busy (busy_test.py).

  py -3 windows\\unit1\\bounds_test.py      about 2 min; writes results/bounds/bounds-worst-case.json
"""
import collections
import copy
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import com_gate as G  # noqa: E402  production constants: nothing is overridden here

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results", "bounds")
BUSY = G.BUSY_CODES[0]
BUSY_WRITES = 38  # rejections before a write goes through: about 9.5 s at the 0.25 s retry interval


class ComErr(Exception):
    def __init__(self, hresult, text="COM error"):
        super().__init__(text)
        self.hresult = hresult


class App:
    def __init__(self):
        self.busy = False
        self._alerts = True

    @property
    def Ready(self):
        if self.busy:
            raise ComErr(BUSY, "rejected")
        return True

    @property
    def DisplayAlerts(self):
        if self.busy:
            raise ComErr(BUSY, "rejected")
        return self._alerts

    @DisplayAlerts.setter
    def DisplayAlerts(self, v):
        if self.busy:
            raise ComErr(BUSY, "rejected")
        self._alerts = v


class Sheet:
    """Writes follow a script per cell, one entry per call:
    "ok": applied. "busy": rejected, nothing applied. ("slow", s): applied after s seconds.
    ("hang", ev): applied when ev is set. ("hang-busy", ev): Excel turns every call away, and the write returns only when
    ev is set, with nothing applied.
    Reads follow rscript per cell: None reads normally, ("hang", ev) returns when ev is set."""

    def __init__(self, **cells):
        self.cells = dict(cells)
        self.Application = App()
        self.script = collections.defaultdict(list)
        self.rscript = collections.defaultdict(list)

    def read(self, ref):
        beh = self.rscript[ref].pop(0) if self.rscript[ref] else None
        if beh:
            beh[1].wait()
        if self.Application.busy:
            raise ComErr(BUSY, "read rejected")
        return self.cells[ref]

    def write(self, ref, value):
        beh = self.script[ref].pop(0) if self.script[ref] else "ok"
        if beh == "ok":
            self.cells[ref] = value
            return
        if beh == "busy":
            raise ComErr(BUSY, "rejected")
        kind, arg = beh
        if kind == "slow":
            time.sleep(arg)
            self.cells[ref] = value
            return
        if kind == "hang-busy":
            self.Application.busy = True
        arg.wait()
        if kind == "hang":
            self.cells[ref] = value


def cell_step(ref, want):
    return G.Step(f"{ref} value", lambda v: v.read(ref), lambda v, x: v.write(ref, x), want)


def commit(sheet, probe, cells, t0):
    """Excel.live_agent's sequence, with the same deadlines, on the fake sheet. Returns (the report as it stood when
    the commit answered, the seconds to the answer, the live report that later threads keep updating)."""
    forward_until, answer_until = t0 + G.FORWARD_BUDGET_S, t0 + G.ANSWER_BUDGET_S
    gate = G.ready_gate(lambda: sheet, probe, until=forward_until)
    if not gate["ok"]:
        out = dict(status="refused", reason=gate["reason"], message=f"Refused: {gate['reason']}. Nothing written.",
                   gate=gate)
        return out, time.monotonic() - t0, out
    befores = G.timed(lambda: {"DisplayAlerts": sheet.Application.DisplayAlerts},
                      max(0.0, min(G.CALL_BUDGET_S, forward_until - time.monotonic())))
    steps = G.guard([cell_step(ref, want) for ref, want in cells], befores, {"DisplayAlerts": False})
    live = G.run_steps(steps, lambda: sheet, app_alive=lambda: True, forward_until=forward_until,
                       answer_until=answer_until)
    seconds = time.monotonic() - t0
    return copy.deepcopy(live), seconds, live


def wait_for(live, key, state_test, seconds=3.0):
    deadline = time.monotonic() + seconds
    while not state_test(live.get(key)) and time.monotonic() < deadline:
        time.sleep(0.05)


def scenario_gate_busy():
    sheet = Sheet(B2=1000)
    sheet.Application.busy = True
    t0 = time.monotonic()
    rep, seconds, _ = commit(sheet, lambda v: bool(v.Application.Ready), [("B2", 5000)], t0)
    return dict(scenario="gate-busy", seconds=round(seconds, 2), at_answer=rep, after_release=None,
                note="Excel turned away every readiness probe")


def scenario_gate_hang():
    sheet = Sheet(B2=1000)
    ev = threading.Event()
    t0 = time.monotonic()
    try:
        rep, seconds, _ = commit(sheet, lambda v: ev.wait(), [("B2", 5000)], t0)
    finally:
        ev.set()
    return dict(scenario="gate-hang", seconds=round(seconds, 2), at_answer=rep, after_release=None,
                note="the readiness probe does not return")


def scenario_unknown_at_forward_deadline():
    """B2 lands at once. E2 is rejected for about 9.5 s, then its write call hangs. The call budget (5 s) ends first,
    and the reconcile window runs to the forward deadline (30 s)."""
    sheet = Sheet(B2=1000, E2=2)
    ev = threading.Event()
    sheet.script["E2"] = ["busy"] * BUSY_WRITES + [("hang", ev)]
    t0 = time.monotonic()
    try:
        rep, seconds, live = commit(sheet, lambda v: bool(v.Application.Ready), [("B2", 5000), ("E2", 6)], t0)
        ev.set()
        wait_for(live, "late_outcome", lambda x: x and x.get("state") not in (None, "pending"))
        after = dict(late_outcome=live.get("late_outcome"), app_restore_state=live.get("app_restore_state"),
                     cells=dict(sheet.cells))
    finally:
        ev.set()
    return dict(scenario="unknown-at-forward-deadline", seconds=round(seconds, 2), at_answer=rep, after_release=after,
                note="E2 write hangs after about 9.5 s of rejections, then lands when released")


def scenario_refused_write_start_limit():
    """B2 and E2 each take about 9.5 s of rejections and land. E3 is rejected until the last moment a write can
    start with its full call budget before the forward deadline (25 s). The rollback write of E2 hangs with Excel
    turned away, and the first restore attempt is turned away until the answer deadline."""
    sheet = Sheet(B2=1000, E2=2, E3=3)
    ev = threading.Event()
    sheet.script["B2"] = ["busy"] * BUSY_WRITES
    sheet.script["E2"] = ["busy"] * BUSY_WRITES + ["ok", ("hang-busy", ev)]
    sheet.script["E3"] = ["busy"] * 100000
    t0 = time.monotonic()
    try:
        rep, seconds, live = commit(sheet, lambda v: bool(v.Application.Ready),
                                    [("B2", 5000), ("E2", 6), ("E3", 7)], t0)
        sheet.Application.busy = False
        ev.set()
        wait_for(live, "app_restore_state", lambda x: x in (None, "restored", "left") or
                 (x or "").startswith("stopped"))
        after = dict(app_restore_state=live.get("app_restore_state"), cells=dict(sheet.cells))
    finally:
        ev.set()
        sheet.Application.busy = False
    return dict(scenario="refused-write-start-limit", seconds=round(seconds, 2), at_answer=rep, after_release=after,
                note="rejection stops at the write start limit (25 s); rollback write hangs with Excel turned away; "
                     "restore turned away to the answer deadline")


def scenario_refused_read_hang_at_forward_end():
    """B2 is slow (4.9 s, lands). E2 and F2 each take about 9.5 s of rejections and land. The pre-write read of G2
    hangs from about 24 s, so the call ends at the forward deadline. The rollback write of F2 hangs with Excel turned
    away, and the first restore attempt is turned away until the answer deadline."""
    sheet = Sheet(B2=1000, E2=2, F2=3, G2=4)
    ev_read, ev_write = threading.Event(), threading.Event()
    sheet.script["B2"] = [("slow", 4.9)]
    sheet.script["E2"] = ["busy"] * BUSY_WRITES
    sheet.script["F2"] = ["busy"] * BUSY_WRITES + ["ok", ("hang-busy", ev_write)]
    sheet.rscript["G2"] = [("hang", ev_read)]  # the first read of G2 is its pre-write read
    t0 = time.monotonic()
    try:
        rep, seconds, live = commit(sheet, lambda v: bool(v.Application.Ready),
                                    [("B2", 5000), ("E2", 6), ("F2", 7), ("G2", 8)], t0)
        sheet.Application.busy = False
        ev_read.set()
        ev_write.set()
        wait_for(live, "app_restore_state", lambda x: x in (None, "restored", "left") or
                 (x or "").startswith("stopped"))
        after = dict(app_restore_state=live.get("app_restore_state"), cells=dict(sheet.cells))
    finally:
        ev_read.set()
        ev_write.set()
        sheet.Application.busy = False
    return dict(scenario="refused-read-hang-at-forward-end", seconds=round(seconds, 2), at_answer=rep,
                after_release=after, note="pre-write read of G2 hangs to the forward deadline; rollback and restore "
                                          "as in the previous scenario")


def row_of(s):
    rep = s["at_answer"]
    out = dict(scenario=s["scenario"], seconds_to_answer=s["seconds"], status=rep.get("status"),
               reason=rep.get("reason"), message=rep.get("message"), restore_state_at_answer=rep.get("app_restore_state"),
               late_outcome_at_answer=rep.get("late_outcome"), rollback=rep.get("rollback"), note=s["note"])
    if s.get("after_release") is not None:
        out["after_release"] = s["after_release"]
    return out


def main():
    os.makedirs(RESULTS, exist_ok=True)
    scenarios = (scenario_gate_busy, scenario_gate_hang, scenario_unknown_at_forward_deadline,
                 scenario_refused_write_start_limit, scenario_refused_read_hang_at_forward_end)
    rows = []
    for fn in scenarios:
        row = row_of(fn())
        rows.append(row)
        print(f"{row['scenario']}: {row['status']} at {row['seconds_to_answer']} s; restore at answer "
              f"{row['restore_state_at_answer']}", flush=True)
    budgets = dict(forward_s=G.FORWARD_BUDGET_S, answer_s=G.ANSWER_BUDGET_S, ready_s=G.READY_BUDGET_S,
                   write_s=G.WRITE_BUDGET_S, call_s=G.CALL_BUDGET_S, reconcile_s=G.RECONCILE_BUDGET_S)
    with open(os.path.join(RESULTS, "bounds-worst-case.json"), "w") as f:
        json.dump(dict(budgets=budgets, rows=rows), f, indent=1, default=str)
    worst = max(r["seconds_to_answer"] for r in rows)
    print(f"worst measured time to answer: {worst} s (bound {G.ANSWER_BUDGET_S:g} s)")


if __name__ == "__main__":
    main()
