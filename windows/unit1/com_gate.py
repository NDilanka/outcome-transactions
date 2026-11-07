"""Busy-safe, time-bounded in-app Excel writes.

An in-app commit writes into a workbook a user has open. It runs under three layers.

1. Prevent the prompt. The commit sets Application.DisplayAlerts to False for its duration, as a checked step, and
   restores it as a checked step at the end (guard). A prompt Excel would raise inside a write, such as a replace
   or save prompt, is then not raised. The commit never calls Close, Save, SaveAs or Quit on the user's workbook.
2. Time out. Every COM call runs on a worker thread with its own COM apartment and a fresh connection to the
   workbook (open_view runs on the worker). The caller waits at most CALL_BUDGET_S. A call that does not return is
   "not responding". The worker stays alive; COM cannot cancel a call that Excel has accepted.
3. Reconcile. A timed-out write is outcome unknown, not refused. While the call is pending, the target is polled on
   fresh connections for up to RECONCILE_BUDGET_S. When the call returns, the target decides: a value that landed
   late is rolled back through the checked steps and the report says so. A call still pending at the end is
   reported as unknown, with the cells to check.

Checked steps. Excel rejects a call it cannot take (RPC_E_CALL_REJECTED or RPC_E_SERVERCALL_RETRYLATER), and a
rejected call did not run. After every rejection the step reads its target back. If the target holds the wanted
value, the rejected call had landed and the step is done. If it still holds the value from before the step, the
step is retried. Any other value (a user edit, or a partial state) refuses the commit. A refused commit rolls back
the steps that landed, and each rollback step is checked the same way.

Statuses of run_steps:
  committed        every step is in place.
  refused          a step was refused. The steps that landed were rolled back. late_landing records a timed-out
                   write that landed after the timeout and was rolled back.
  unknown          a timed-out write had not returned when reconciliation ended. Cells are not rolled back, because
                   the write may still land. Application properties the commit set are restored on a background
                   thread when the call returns. The message names the cells to check.
  refused_partial  a rollback step was refused, so the target may hold part of the change.
"""
import collections
import re
import threading
import time

import pythoncom

BUSY_CODES = (-2147418111, -2147417846)  # RPC_E_CALL_REJECTED 0x80010001, RPC_E_SERVERCALL_RETRYLATER 0x8001010A
READY_BUDGET_S = 5.0
WRITE_BUDGET_S = 10.0
CALL_BUDGET_S = 5.0
RECONCILE_BUDGET_S = 20.0
POLL_S = 0.25

# label: name for the report. read(view) -> current value. write(view, v): one COM call that sets v. want: after.
Step = collections.namedtuple("Step", "label read write want")


class RemoteError(Exception):
    """A COM error from a worker call, without its traceback (the COM objects die with the worker).

    turned_away: pywin32 reports a member lookup that Excel refused as AttributeError "<object>.<member>", with no
    COM code. A failed lookup never invokes the member, so the call did not run. It is handled like a rejected call."""

    def __init__(self, kind, hresult, text, turned_away=False):
        super().__init__(text)
        self.kind = kind
        self.hresult = hresult
        self.turned_away = turned_away


_LOOKUP_FAILURE = re.compile(r"^\S+\.[A-Za-z_]\w*$")  # pywin32's "<object>.<member>"; Python's own messages have spaces


def _remote(e):
    if isinstance(e, AttributeError) and e.args and isinstance(e.args[0], str) and _LOOKUP_FAILURE.match(e.args[0]):
        return RemoteError("AttributeError", None, repr(e)[:200], turned_away=True)
    return RemoteError(type(e).__name__, getattr(e, "hresult", None), repr(e)[:200])


class NotResponding(Exception):
    """A COM call did not return within its budget. call is the pending Call, kept for reconciliation."""

    def __init__(self, text, call):
        super().__init__(text)
        self.call = call


class Call:
    """One COM call on a worker thread with its own COM apartment. The thread outlives a timeout."""

    def __init__(self, fn, label):
        self.label = label
        self._done = threading.Event()
        self._box = {}
        threading.Thread(target=self._work, args=(fn,), name=f"com-{label}", daemon=True).start()

    def _work(self, fn):
        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        try:
            self._box["value"] = fn()
        except Exception as e:
            self._box["error"] = _remote(e)
        finally:
            try:
                pythoncom.CoUninitialize()
            finally:
                self._done.set()

    def wait(self, budget_s=None):
        """Wait up to budget_s seconds, or without limit when budget_s is None. Returns True when the call returned."""
        return self._done.wait(None if budget_s is None else max(0.0, budget_s))

    def finished(self):
        return self._done.is_set()

    def result(self):
        if "error" in self._box:
            raise self._box["error"]
        return self._box.get("value")


def timed(fn, budget_s=CALL_BUDGET_S, label="COM call"):
    """Run fn() on a worker thread. Return its value, raise its COM error as RemoteError, or raise NotResponding."""
    call = Call(fn, label)
    if not call.wait(budget_s):
        raise NotResponding(f"{label} did not return within {budget_s:g} s", call)
    return call.result()


def is_busy(e):
    return getattr(e, "hresult", None) in BUSY_CODES or bool(getattr(e, "turned_away", False))


def describe(e):
    if getattr(e, "turned_away", False):
        return "AttributeError (member lookup turned away)"
    code = getattr(e, "hresult", None)
    tag = f" 0x{code & 0xFFFFFFFF:08X}" if code is not None else ""
    return f"{getattr(e, 'kind', type(e).__name__)}{tag}"


def ready_gate(open_view, probe, budget_s=READY_BUDGET_S, poll_s=POLL_S, clock=time.monotonic, sleep=time.sleep,
               call_budget_s=CALL_BUDGET_S):
    """Return dict(ok, reason, tries, seconds, last_error). probe(view) -> bool runs on a worker with a fresh view.
    The gate writes nothing."""
    start = clock()
    tries = 0
    last = None
    while True:
        tries += 1
        try:
            if timed(lambda: probe(open_view()), call_budget_s, "readiness probe"):
                return dict(ok=True, reason=None, tries=tries, seconds=round(clock() - start, 2), last_error=last)
            last = "Application.Ready is False"
        except NotResponding as e:
            return dict(ok=False, reason="Excel not responding", tries=tries, seconds=round(clock() - start, 2),
                        last_error=str(e))
        except RemoteError as e:
            if not is_busy(e):
                return dict(ok=False, reason=f"Excel error: {describe(e)}", tries=tries,
                            seconds=round(clock() - start, 2), last_error=describe(e))
            last = describe(e)
        if clock() - start >= budget_s:
            return dict(ok=False, reason="Excel busy", tries=tries, seconds=round(clock() - start, 2),
                        last_error=last)
        sleep(poll_s)


class _Ctx:
    """The view, budgets and clock for one phase of a step."""

    def __init__(self, open_view, budget_s, call_budget_s, clock, sleep, poll_s):
        self.open_view = open_view
        self.call_budget_s = call_budget_s
        self.clock = clock
        self.sleep = sleep
        self.poll_s = poll_s
        self.deadline = clock() + budget_s

    def call(self, fn, label):
        """fn(view) on a worker with a fresh view. Raises RemoteError, or NotResponding with the pending call."""
        return timed(lambda: fn(self.open_view()), self.call_budget_s, label)

    def settle_read(self, step):
        """Read the target until a read returns, fails without busy, or the phase deadline passes."""
        while True:
            try:
                return True, self.call(step.read, f"read {step.label}")
            except RemoteError as e:
                if not is_busy(e) or self.clock() >= self.deadline:
                    return False, describe(e)
                self.sleep(self.poll_s)


def _is_app_step(step):
    """Application properties (DisplayAlerts, ScreenUpdating) that guard sets. They are not workbook content."""
    return step.label.startswith("Application.")


def _cells(steps):
    """The cells the commit writes, from the step labels ("B2 value" -> "B2"), in order, without repeats."""
    return list(dict.fromkeys(s.label.split()[0] for s in steps if not _is_app_step(s)))


def _do_step(step, ctx):
    """One checked write. Returns dict(status, before, rejections, checks, reason, write_issued, pending).

    status: written | already | refused | not_responding. A not_responding step is reconciled by run_steps."""
    r = dict(status=None, before=None, rejections=0, checks=[], reason=None, write_issued=False, pending=None)
    try:
        ok, before = ctx.settle_read(step)
        if not ok:
            return dict(r, status="refused", reason=f"target unreadable before the write: {before}")
        r["before"] = before
        if before == step.want:
            return dict(r, status="already")
        while True:
            r["write_issued"] = True
            try:
                ctx.call(lambda view: step.write(view, step.want), f"write {step.label}")
                break
            except RemoteError as e:
                if not is_busy(e):
                    return dict(r, status="refused", reason=f"write error: {describe(e)}")
                r["rejections"] += 1
                ok, now = ctx.settle_read(step)
                r["checks"].append(repr(now) if ok else f"unreadable ({now})")
                if not ok:
                    return dict(r, status="refused",
                                reason=f"rejected ({describe(e)}) and the target could not be read back: {now}")
                if now == step.want:
                    break
                if now != before:
                    return dict(r, status="refused",
                                reason=f"rejected ({describe(e)}), and the target holds {now!r}, neither the "
                                       f"value before the write {before!r} nor the wanted {step.want!r}")
                if ctx.clock() >= ctx.deadline:
                    return dict(r, status="refused",
                                reason=f"busy: rejected {r['rejections']} times, target unchanged")
                ctx.sleep(ctx.poll_s)
        ok, after = ctx.settle_read(step)
        if not ok:
            return dict(r, status="refused", reason=f"written, but the target could not be read back: {after}")
        if after != step.want:
            return dict(r, status="refused", reason=f"written, but the target holds {after!r}, wanted {step.want!r}")
        return dict(r, status="written")
    except NotResponding as e:
        return dict(r, status="not_responding", reason=str(e), pending=e.call)


def _read_or_text(step, ctx):
    """settle_read that reports a read which does not return as text."""
    try:
        return ctx.settle_read(step)
    except NotResponding as e:
        return False, f"not responding ({e})"


def _read_once(step, ctx):
    """One read on a fresh connection, without retries: a reconcile poll records what it sees and moves on."""
    try:
        return True, ctx.call(step.read, f"poll {step.label}")
    except RemoteError as e:
        return False, describe(e)
    except NotResponding as e:
        return False, f"not responding ({e})"


def _reconcile(step, before, pending, make_ctx, budget_s, poll_s):
    """A write call timed out. Poll the target on fresh connections while the call is pending, then decide.

    Returns dict(state, detail, returned, call_error, polls). state is landed | unchanged | other | unknown.
    Only a returned call gives a settled state: while it is pending the state is unknown."""
    polls = []
    end = time.monotonic() + budget_s
    while not pending.finished() and time.monotonic() < end:
        ok, now = _read_once(step, make_ctx(CALL_BUDGET_S))
        polls.append(repr(now) if ok else f"unreadable ({now})")
        pending.wait(min(poll_s, max(0.0, end - time.monotonic())))
    if not pending.finished():
        last = polls[-1] if polls else "no read"
        return dict(state="unknown", detail=f"the call had not returned after {budget_s:g} s; last read {last}",
                    returned=False, call_error=None, polls=polls)
    call_error = None
    try:
        pending.result()
    except RemoteError as e:
        call_error = describe(e)
    ok, now = _read_or_text(step, make_ctx(WRITE_BUDGET_S, CALL_BUDGET_S))
    if not ok:
        return dict(state="unknown", detail=f"the call returned, but the target could not be read back: {now}",
                    returned=True, call_error=call_error, polls=polls)
    if now == step.want:
        state = "landed"
    elif now == before:
        state = "unchanged"
    else:
        state = "other"
    return dict(state=state, detail=repr(now), returned=True, call_error=call_error, polls=polls)


def prop_step(prop, want, label=None):
    """An Application property as a checked step: read it on the application, write it, read it back."""
    return Step(label or f"Application.{prop}", lambda view: getattr(view.Application, prop),
                lambda view, v: setattr(view.Application, prop, v), want)


def guard(core, befores, during):
    """Wrap the core steps with Application properties set to `during` first, and restored to `befores` last.
    Only properties whose value changes are touched. befores and during map property name to value."""
    names = [p for p in during if during[p] != befores[p]]
    on = [prop_step(p, during[p], f"Application.{p} set") for p in names]
    off = [prop_step(p, befores[p], f"Application.{p} restored") for p in reversed(names)]
    return on + list(core) + off


def _rollback(report, applied, make_ctx, budget_s, landed_late):
    """Undo the landed steps, newest first. A rollback step that is refused makes the report refused_partial."""
    for prev, before in reversed(applied):
        rb = _do_step(Step(prev.label, prev.read, prev.write, before), make_ctx(budget_s))
        report["rollback"].append(dict(step=prev.label, status=rb["status"], reason=rb["reason"]))
        report["rejections"] += rb["rejections"]
        if rb["status"] not in ("written", "already"):
            report["status"] = "refused_partial"
            report["reason"] += f"; rollback of {prev.label} {rb['status']}: {rb['reason']}"
            return
    if landed_late:
        report["late_landing"] = "landed after the timeout, rolled back"


def _restore_when_returned(app_steps, pending, make_ctx, budget_s, report):
    """Restore the application properties once the pending call returns. Workbook cells are not touched here."""
    def finish():
        pending.wait()
        out = []
        for prev, before in reversed(app_steps):
            rb = _do_step(Step(prev.label, prev.read, prev.write, before), make_ctx(budget_s))
            out.append(dict(step=prev.label, status=rb["status"], reason=rb["reason"]))
            if rb["status"] not in ("written", "already"):
                break
        report["app_restore"] = out

    threading.Thread(target=finish, name="com-restore-app", daemon=True).start()


def run_steps(steps, open_view, budget_s=WRITE_BUDGET_S, call_budget_s=CALL_BUDGET_S,
              reconcile_budget_s=RECONCILE_BUDGET_S, clock=time.monotonic, sleep=time.sleep, poll_s=POLL_S):
    """Run the steps in order, each call on a fresh connection. See the module docstring for the rules.

    Returns dict(status, done, refused_at, reason, message, rejections, checks, late_landing, reconcile, rollback,
    app_restore)."""
    report = dict(status="committed", done=[], refused_at=None, reason=None, message=None, rejections=0, checks=[],
                  late_landing=None, reconcile=None, rollback=[], app_restore=None, left=[])
    cells = _cells(steps)
    applied = []  # (step, value before the step) for steps that landed, in order

    def make_ctx(budget, call_budget=call_budget_s):
        return _Ctx(open_view, budget, call_budget, clock, sleep, poll_s)

    for step in steps:
        r = _do_step(step, make_ctx(budget_s))
        report["rejections"] += r["rejections"]
        report["checks"] += r["checks"]
        if r["status"] in ("written", "already"):
            report["done"].append(step.label + (" (already)" if r["status"] == "already" else ""))
            applied.append((step, r["before"]))
            continue
        report.update(refused_at=step.label, status="refused", reason=r["reason"])
        landed_late = False
        if r["status"] == "not_responding" and not r["write_issued"]:
            report["reason"] = f"Excel not responding before the {step.label} write ({r['reason']})"
        elif r["status"] == "not_responding":
            rc = _reconcile(step, r["before"], r["pending"], make_ctx, reconcile_budget_s, poll_s)
            report["reconcile"] = dict(step=step.label, **rc)
            if rc["state"] == "unknown":
                report.update(status="unknown",
                              reason=f"Excel did not return from the {step.label} write ({rc['detail']})")
                app_steps = [(s, b) for s, b in applied if _is_app_step(s)]
                if app_steps:
                    _restore_when_returned(app_steps, r["pending"], make_ctx, budget_s, report)
                _set_message(report, cells)
                return report
            if rc["state"] == "landed":
                applied.append((step, r["before"]))
                landed_late = True
                report["reason"] = f"the {step.label} write returned after the timeout, and its value landed"
            elif rc["state"] == "unchanged":
                report["reason"] = (f"Excel did not answer the {step.label} write within {call_budget_s:g} s, and the "
                                    f"call returned later with nothing landed")
            else:
                report["left"] = _cells([step])
                report["reason"] = (f"the {step.label} write returned after the timeout, and the target holds "
                                    f"{rc['detail']}")
        _rollback(report, applied, make_ctx, budget_s, landed_late)
        _set_message(report, cells)
        return report
    _set_message(report, cells)
    return report


def _set_message(report, cells):
    s, reason = report["status"], report["reason"]
    if s == "committed":
        report["message"] = "Committed."
    elif s == "refused":
        tail = "Finished steps were rolled back." if report["rollback"] else "Nothing was written."
        if report["left"]:
            tail += (f" Left as it is: {', '.join(report['left'])}, which holds a value the commit did not write.")
        report["message"] = f"Refused: {reason}. {tail}"
    elif s == "unknown":
        report["message"] = (f"Outcome unknown: {reason}. Check {' and '.join(cells)} before you save, because a write "
                             f"may still complete.")
    else:
        report["message"] = f"Refused, and not fully rolled back: {reason}. Check the workbook."
