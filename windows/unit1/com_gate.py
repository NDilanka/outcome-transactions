"""Busy-safe, time-bounded in-app writes to Excel and Word (app names the application in messages).

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
the steps that landed. Before each rollback, the cell must still hold the value the commit wrote. A value someone
else put there is left as it is, and the report names the cell.

Statuses of run_steps:
  committed        every step is in place.
  refused          a step was refused. The steps that landed were rolled back. late_landing records a timed-out
                   write that landed after the timeout and was rolled back.
  unknown          a timed-out write had not returned when reconciliation ended. Cells are not rolled back, because
                   the write may still land. When the call returns, late_outcome records what it left (landed,
                   unchanged, other), and the cells are not rolled back: the message already told the user to check
                   them. Application properties the commit set are restored on a background thread at that point.
                   The message names the cells to check.
  refused_partial  a rollback step was refused, so the target may hold part of the change.

Application properties (DisplayAlerts, ScreenUpdating) are not workbook content. They are restored by _restore_app,
which writes a property back only while it holds the value the commit set. app_restore_state says what became of
them: restored, left (someone else changed the value), pending (Excel turned the restore away; retried in the
background), or stopped (the workbook closed, or Excel exited). restore_log records every attempt.

Time. FORWARD_BUDGET_S bounds the forward path, counted from the commit's start: the readiness gate, the reads, the
writes and the reconcile window. No call starts or waits past it, and no write begins after it. ANSWER_BUDGET_S
bounds the answer: the rollback of landed cells and the first restore attempt end by then. Restore retries after
the answer run in the background and do not delay it. So an answer comes by ANSWER_BUDGET_S, and an unknown outcome
comes by FORWARD_BUDGET_S.
"""
import collections
import functools
import itertools
import math
import re
import threading
import time

import pythoncom

DISP_E_EXCEPTION = -2147352567  # 0x80020009: the call raised, and Excel's own code is in excepinfo[5] (scode)
BUSY_CODES = (
    -2147418111,  # RPC_E_CALL_REJECTED 0x80010001
    -2147417846,  # RPC_E_SERVERCALL_RETRYLATER 0x8001010A
    -2146777998,  # 0x800AC472 "waiting for another application to complete an OLE action": a modal dialog is open
)
ASPECTS = ("value", "formula", "numfmt", "bold", "fill", "comment")  # the last word of a cell step's label
READY_BUDGET_S = 5.0
WRITE_BUDGET_S = 10.0
CALL_BUDGET_S = 5.0
RECONCILE_BUDGET_S = 20.0
POLL_S = 0.25
RESTORE_RETRY_S = 0.5
FORWARD_BUDGET_S = 30.0
ANSWER_BUDGET_S = 40.0

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


def _com_code(e):
    """The HRESULT. For DISP_E_EXCEPTION, the code is the scode in excepinfo, where Excel puts its own error."""
    code = getattr(e, "hresult", None)
    info = e.args[2] if len(e.args) > 2 else None
    if code == DISP_E_EXCEPTION and info and len(info) > 5 and info[5]:
        return info[5]
    return code


def remote_error(e):
    if isinstance(e, AttributeError) and e.args and isinstance(e.args[0], str) and _LOOKUP_FAILURE.match(e.args[0]):
        return RemoteError("AttributeError", None, repr(e)[:200], turned_away=True)
    return RemoteError(type(e).__name__, _com_code(e), repr(e)[:200])


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
            self._box["error"] = remote_error(e)
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
        return "the application turned the call away"
    code = getattr(e, "hresult", None)
    tag = f" 0x{code & 0xFFFFFFFF:08X}" if code is not None else ""
    return f"{getattr(e, 'kind', type(e).__name__)}{tag}"


def ready_gate(open_view, probe, budget_s=READY_BUDGET_S, poll_s=POLL_S, clock=time.monotonic, sleep=time.sleep,
               call_budget_s=CALL_BUDGET_S, until=math.inf, app="Excel"):
    """Return dict(ok, reason, tries, seconds, last_error). probe(view) -> bool runs on a worker with a fresh view.
    The gate writes nothing. No probe starts after budget_s, or after until (an absolute time on clock), and no probe
    waits past that deadline: a probe still pending at the deadline is "not responding". app names the application in
    the reason ("Excel busy", "Word busy")."""
    start = clock()
    deadline = min(start + budget_s, until)
    tries = 0
    last = None
    while clock() < deadline:
        tries += 1
        try:
            budget = max(0.0, min(call_budget_s, deadline - clock()))
            if timed(lambda: probe(open_view()), budget, "readiness probe"):
                return dict(ok=True, reason=None, tries=tries, seconds=round(clock() - start, 2), last_error=last)
            last = "Application.Ready is False"
        except NotResponding as e:
            return dict(ok=False, reason=f"{app} not responding", tries=tries, seconds=round(clock() - start, 2),
                        last_error=str(e))
        except RemoteError as e:
            if not is_busy(e):
                return dict(ok=False, reason=f"{app} error: {describe(e)}", tries=tries,
                            seconds=round(clock() - start, 2), last_error=describe(e))
            last = describe(e)
        sleep(min(poll_s, max(0.0, deadline - clock())))
    return dict(ok=False, reason=f"{app} busy", tries=tries, seconds=round(clock() - start, 2), last_error=last)


class _Ctx:
    """The view, budgets and clock for one phase of a step. until is an absolute time on clock: no call starts or
    waits past it, and no retry starts past it."""

    def __init__(self, open_view, budget_s, call_budget_s, clock, sleep, poll_s, until=math.inf):
        self.open_view = open_view
        self.call_budget_s = call_budget_s
        self.clock = clock
        self.sleep = sleep
        self.poll_s = poll_s
        self.until = until
        self.deadline = min(clock() + budget_s, until)

    def call(self, fn, label):
        """fn(view) on a worker with a fresh view. Raises RemoteError, or NotResponding with the pending call."""
        budget = max(0.0, min(self.call_budget_s, self.until - self.clock()))
        return timed(lambda: fn(self.open_view()), budget, label)

    def settle_read(self, step):
        """Read the target until a read returns, fails without busy, or the phase deadline passes."""
        while True:
            try:
                return True, self.call(step.read, f"read {step.label}")
            except RemoteError as e:
                if not is_busy(e) or self.clock() >= self.deadline:
                    return False, describe(e)
                self.sleep(min(self.poll_s, max(0.0, self.deadline - self.clock())))


def _is_app_step(step):
    """Application properties (DisplayAlerts, ScreenUpdating) that guard sets. They are not workbook content."""
    return step.label.startswith("Application.")


def _cell_name(label):
    """"B2 value" -> "B2", "total line value" -> "total line": the label without its aspect word."""
    words = label.split()
    return " ".join(words[:-1]) if len(words) > 1 and words[-1] in ASPECTS else label


def _cells(steps):
    """The cells the commit writes, from the step labels, in order, without repeats."""
    return list(dict.fromkeys(_cell_name(s.label) for s in steps if not _is_app_step(s)))


def _can_start(ctx, at):
    """A write may begin at time `at` only if its whole call budget fits before the step's deadline and the forward
    deadline. A call cut short by a deadline is the one that comes back unknown, so none is started that short."""
    return at < ctx.deadline and ctx.until - at >= ctx.call_budget_s


def _after_write_error(r, e, step, before, ctx):
    """A write that failed with an error other than busy may still have applied part of its effect, so the target is
    read back. Unchanged: refused, nothing written. Anything else: unverified, and run_steps rolls it back."""
    try:
        ok, now = ctx.settle_read(step)
    except NotResponding as x:
        ok, now = False, f"not responding ({x})"
    if ok and now == before:
        return dict(r, status="refused", reason=f"write error: {describe(e)}")
    if not ok:
        return dict(r, status="unverified",
                    reason=f"write error: {describe(e)}, and the target could not be read back: {now}")
    return dict(r, status="unverified", reason=f"write error: {describe(e)}, and the target holds {now!r}")


def _do_step(step, ctx):
    """One checked write. Returns dict(status, before, rejections, checks, reason, write_issued, pending).

    status: written | already | refused | unverified | not_responding. unverified: the write call returned with an
    error, or it returned but the target could not be read back, so the write may have landed (run_steps rolls it
    back). not_responding: a call did not return, and run_steps reconciles it."""
    r = dict(status=None, before=None, rejections=0, checks=[], reason=None, write_issued=False, pending=None)
    if not _can_start(ctx, ctx.clock()):
        return dict(r, status="refused", reason="out of time before the write began")
    try:
        ok, before = ctx.settle_read(step)
        if not ok:
            return dict(r, status="refused", reason=f"target unreadable before the write: {before}")
        r["before"] = before
        if before == step.want:
            return dict(r, status="already")
        if not _can_start(ctx, ctx.clock()):
            return dict(r, status="refused", reason="out of time before the write began")
        while True:
            r["write_issued"] = True
            try:
                ctx.call(lambda view: step.write(view, step.want), f"write {step.label}")
                break
            except RemoteError as e:
                if not is_busy(e):
                    return _after_write_error(r, e, step, before, ctx)
                r["rejections"] += 1
                ok, now = ctx.settle_read(step)
                r["checks"].append(repr(now) if ok else f"unreadable ({now})")
                if not ok:  # the value is unconfirmed: the call was turned away, and no read of the target came back
                    return dict(r, status="refused", confirmed=False,
                                reason=f"busy: rejected ({describe(e)}), and no read-back of the target was possible "
                                       f"within the write budget ({now}); the value is unconfirmed")
                if now == step.want:
                    break
                if now != before:
                    return dict(r, status="refused",
                                reason=f"rejected ({describe(e)}), and the target holds {now!r}, neither the "
                                       f"value before the write {before!r} nor the wanted {step.want!r}")
                if not _can_start(ctx, ctx.clock() + ctx.poll_s):
                    return dict(r, status="refused",
                                reason=f"busy: rejected {r['rejections']} times, target unchanged")
                ctx.sleep(ctx.poll_s)
        try:
            ok, after = ctx.settle_read(step)
        except NotResponding as e:
            return dict(r, status="unverified",
                        reason=f"written, but the target could not be read back: not responding ({e})")
        if not ok:
            return dict(r, status="unverified", reason=f"written, but the target could not be read back: {after}")
        if after != step.want:
            return dict(r, status="unverified",
                        reason=f"written, but the target holds {after!r}, wanted {step.want!r}")
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


def _reconcile(step, before, pending, make_ctx, budget_s, poll_s, until, answer_until):
    """A write call timed out. Poll the target on fresh connections while the call is pending, then decide.

    The window is budget_s, and it never runs past until (the forward deadline). The final read, after the call
    returns, may run to answer_until. Returns dict(state, detail, returned, call_error, polls).
    state is landed | unchanged | other | rejected | unknown. Only a returned call gives a settled state. A call that
    returned busy was refused before Excel ran it, so it is rejected, not unknown, whatever the read-back shows."""
    polls = []
    end = min(time.monotonic() + budget_s, until)
    while not pending.finished() and time.monotonic() < end:
        ok, now = _read_once(step, make_ctx(CALL_BUDGET_S, until=until))
        polls.append(repr(now) if ok else f"unreadable ({now})")
        pending.wait(min(poll_s, max(0.0, end - time.monotonic())))
    if not pending.finished():
        last = polls[-1] if polls else "no read"
        return dict(state="unknown", detail=f"the call had not returned by the end of the reconcile window; last read "
                                            f"{last}", returned=False, call_error=None, polls=polls)
    call_error = None
    rejected = False
    try:
        pending.result()
    except RemoteError as e:
        call_error = describe(e)
        rejected = is_busy(e)  # Excel refused the call before it ran, so nothing was applied
    ok, now = _read_or_text(step, make_ctx(WRITE_BUDGET_S, CALL_BUDGET_S, until=answer_until))
    if not ok:
        if rejected:
            return dict(state="rejected", confirmed=False, returned=True, call_error=call_error, polls=polls,
                        detail=f"busy: rejected ({call_error}), and no read-back of the target was possible: {now}")
        return dict(state="unknown", detail=f"the target could not be read back: {now}", returned=True,
                    call_error=call_error, polls=polls)
    if now == step.want:
        state, detail = "landed", repr(now)
    elif rejected and now == before:
        state, detail = "rejected", f"busy: rejected ({call_error}), target unchanged"
    elif now == before:
        state, detail = "unchanged", repr(now)
    else:
        state, detail = "other", repr(now)
    return dict(state=state, detail=detail, returned=True, call_error=call_error, polls=polls)


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
    """Undo the landed workbook steps, newest first. Before each undo the cell must still hold the value the commit
    wrote. A value someone else put there is left as it is, and reported. A rollback step that is refused makes the
    report refused_partial. Application properties are restored by _restore_app."""
    for prev, before in reversed([(s, b) for s, b in applied if not _is_app_step(s)]):
        ok, now = _read_or_text(prev, make_ctx(budget_s))
        if not ok:
            report["rollback"].append(dict(step=prev.label, status="refused", reason=f"unreadable: {now}"))
            report.update(status="refused_partial",
                          reason=f"{report['reason']}; rollback of {prev.label} refused: target unreadable: {now}")
            return
        if now == before:
            report["rollback"].append(dict(step=prev.label, status="already", reason=None))
            continue
        if now != prev.want:
            report["rollback"].append(dict(step=prev.label, status="left", reason=f"holds {now!r}"))
            report["left"].append(_cells([prev])[0])
            continue
        rb = _do_step(Step(prev.label, prev.read, prev.write, before), make_ctx(budget_s))
        report["rollback"].append(dict(step=prev.label, status=rb["status"], reason=rb["reason"]))
        report["rejections"] += rb["rejections"]
        if rb["status"] not in ("written", "already"):
            report["status"] = "refused_partial"
            report["reason"] += f"; rollback of {prev.label} {rb['status']}: {rb['reason']}"
            return
    if landed_late:
        report["late_landing"] = "landed after the timeout, rolled back"


def _restore_read(step, ctx):
    """The step's current value, or (None, error). A turned-away or unanswered read is retried until the phase
    deadline, and the error is returned as it stands."""
    while True:
        try:
            return ctx.call(step.read, f"read {step.label}"), None
        except RemoteError as e:
            if not is_busy(e) or ctx.clock() >= ctx.deadline:
                return None, e
            ctx.sleep(min(ctx.poll_s, max(0.0, ctx.deadline - ctx.clock())))
        except NotResponding as e:
            return None, e


def _restore_error(err):
    """A call Excel did not answer, or turned away, is tried again. Any other failure stops the retries."""
    if isinstance(err, NotResponding):
        return "turned away", f"not responding ({err})"
    if is_busy(err):
        return "turned away", describe(err)
    return "stopped", describe(err)


def _restore_once(prev, before, ctx):
    """One restore of one application property. Returns (action, detail).

    prev is the step that set the property (its want is the value the commit set), before is the value it replaced.
    action: restored (at the original value already, or written back now), left (the value is neither the one the
    commit set nor the original, so someone else changed it, and it is not written), turned away (Excel did not
    answer or refused the call, so try again), or stopped (a read or write failed for another reason: the workbook is
    closed or Excel is unreachable)."""
    now, err = _restore_read(prev, ctx)
    if err is not None:
        return _restore_error(err)
    if now == before:
        return "restored", "already at the original value"
    if now != prev.want:
        return "left", f"holds {now!r}, neither the value the commit set ({prev.want!r}) nor the original ({before!r})"
    try:
        ctx.call(lambda view: prev.write(view, before), f"restore {prev.label}")
    except RemoteError as e:
        if not is_busy(e):
            return "stopped", describe(e)
    except NotResponding as e:
        return "turned away", f"not responding ({e})"
    now, err = _restore_read(prev, ctx)
    if err is not None:
        return _restore_error(err)
    if now == before:
        return "restored", "written back"
    return "turned away", f"holds {now!r} after the write"


def _log(report, attempt, step, action, detail):
    report["restore_log"].append(dict(attempt=attempt, at=round(time.time(), 2), step=step, action=action,
                                      detail=detail))


def _restore_app(app_steps, make_ctx, budget_s, report, app_alive=None, first_ctx=None, app="Excel"):
    """Restore the application properties the commit set, newest first. Workbook cells are not touched here.

    The first attempt runs now, with first_ctx when given (bounded by the answer deadline), and make_ctx otherwise. A
    restore that Excel does not answer or turns away is retried every RESTORE_RETRY_S on a background thread. The
    retries stop when every property is restored or left as someone else set it, when a read fails for another reason
    (the workbook was closed, or Excel is unreachable), or when app_alive() is False.

    report gets app_restore (the last attempt's action per property), app_restore_state (restored, left, pending, or
    stopped: reason) and restore_log (every attempt, in order, with the time and the action)."""
    counter = itertools.count(1)

    def attempt(make):
        n = next(counter)
        out, state = [], "restored"
        for prev, before in reversed(app_steps):
            if app_alive is not None and not app_alive():
                action, detail = "stopped", f"{app} exited"
            else:
                action, detail = _restore_once(prev, before, make(budget_s))
            _log(report, n, prev.label, action, detail)
            out.append(dict(step=prev.label, status=action, reason=detail))
            if action == "stopped":
                return out, f"stopped: {detail}"
            if action == "turned away":
                state = "pending"
            elif action == "left" and state == "restored":
                state = "left"
        return out, state

    def keep_trying():
        while True:
            time.sleep(RESTORE_RETRY_S)
            out, state = attempt(make_ctx)
            report.update(app_restore=out, app_restore_state=state)
            if state != "pending":
                return

    out, state = attempt(first_ctx or make_ctx)
    report.update(app_restore=out, app_restore_state=state)
    if state == "pending":
        threading.Thread(target=keep_trying, name="com-restore-app", daemon=True).start()


def _watch_late(step, before, pending, make_ctx, report, app_steps, app_alive, call_budget_s, app="Excel"):
    """A timed-out write whose outcome run_steps reported unknown. When its call returns, report["late_outcome"]
    records what the write left: landed, unchanged, other, or unreadable. The cell is not rolled back, because the
    report already told the user to check it. Then the application properties are restored (_restore_app).

    A call that never returns leaves late_outcome pending. Excel exiting first is recorded as its state."""
    report["late_outcome"] = dict(state="pending", detail="the write had not returned when the outcome was reported")

    def watch():
        while not pending.wait(RESTORE_RETRY_S):
            if app_alive is not None and not app_alive():
                report["late_outcome"] = dict(state="excel exited", detail=f"{app} exited before the write returned")
                if app_steps:
                    _log(report, None, app_steps[-1][0].label, "stopped", f"{app} exited while the write was pending")
                    report["app_restore_state"] = f"stopped: {app} exited while the write was pending"
                return
        call_error = None
        try:
            pending.result()
        except RemoteError as e:
            call_error = describe(e)
        ok, now = _read_once(step, make_ctx(call_budget_s))
        if not ok:
            late = dict(state="unreadable", detail=now)
        elif now == step.want:
            late = dict(state="landed", detail=repr(now))
        elif now == before:
            late = dict(state="unchanged", detail=repr(now))
        else:
            late = dict(state="other", detail=repr(now))
        report["late_outcome"] = dict(late, call_error=call_error)
        if app_steps:
            _restore_app(app_steps, make_ctx, call_budget_s, report, app_alive=app_alive, app=app)

    threading.Thread(target=watch, name="com-late-outcome", daemon=True).start()


def run_steps(steps, open_view, budget_s=WRITE_BUDGET_S, call_budget_s=CALL_BUDGET_S,
              reconcile_budget_s=RECONCILE_BUDGET_S, clock=time.monotonic, sleep=time.sleep, poll_s=POLL_S,
              app_alive=None, forward_until=math.inf, answer_until=math.inf, app="Excel"):
    """Run the steps in order, each call on a fresh connection. See the module docstring for the rules.

    forward_until and answer_until are absolute times on time.monotonic (the forward and answer deadlines). The
    default is no deadline. app_alive() -> bool is False once Excel has exited; it stops the restore retries.

    Returns dict(status, done, refused_at, reason, message, rejections, checks, late_landing, late_outcome,
    reconcile, rollback, app_restore, app_restore_state, restore_log, left, unconfirmed). unconfirmed names the cells
    of a write that was turned away while no read of the target could come back: the message asks the user to check
    them, and does not say they were left unwritten."""
    report = dict(status="committed", done=[], refused_at=None, reason=None, message=None, rejections=0, checks=[],
                  late_landing=None, late_outcome=None, reconcile=None, rollback=[], app_restore=None,
                  app_restore_state=None, restore_log=[], left=[], unconfirmed=None)
    cells = _cells(steps)
    applied = []  # (step, value before the step) for steps that landed, in order

    def make_ctx(budget, call_budget=call_budget_s, until=math.inf):
        return _Ctx(open_view, budget, call_budget, clock, sleep, poll_s, until)

    forward = functools.partial(make_ctx, until=forward_until)
    answer = functools.partial(make_ctx, until=answer_until)

    for step in steps:
        r = _do_step(step, forward(budget_s))
        report["rejections"] += r["rejections"]
        report["checks"] += r["checks"]
        if r["status"] in ("written", "already"):
            report["done"].append(step.label + (" (already)" if r["status"] == "already" else ""))
            applied.append((step, r["before"]))
            continue
        report.update(refused_at=step.label, status="refused", reason=r["reason"])
        if r.get("confirmed") is False:
            report["unconfirmed"] = _cells([step])
        if r["status"] == "unverified":
            applied.append((step, r["before"]))  # the write returned, so it is rolled back like a landed step
        landed_late = False
        if r["status"] == "not_responding" and not r["write_issued"]:
            report["reason"] = f"{app} not responding before the {step.label} write ({r['reason']})"
        elif r["status"] == "not_responding":
            rc = _reconcile(step, r["before"], r["pending"], make_ctx, reconcile_budget_s, poll_s, forward_until,
                            answer_until)
            report["reconcile"] = dict(step=step.label, **rc)
            if rc["state"] == "unknown":
                if rc["returned"]:
                    with_error = f" with {rc['call_error']}" if rc["call_error"] else ""
                    reason = f"{app} returned from the {step.label} write{with_error}, but {rc['detail']}"
                else:
                    reason = f"{app} did not return from the {step.label} write ({rc['detail']})"
                report.update(status="unknown", reason=reason)
                app_steps = [(s, b) for s, b in applied if _is_app_step(s)]
                report["app_restore_state"] = "pending" if app_steps else None
                _watch_late(step, r["before"], r["pending"], make_ctx, report, app_steps, app_alive, call_budget_s,
                            app)
                _set_message(report, cells, app)
                return report
            if rc["state"] == "rejected":
                report["rejections"] += 1
                report["reason"] = rc["detail"]
                if rc.get("confirmed") is False:
                    report["unconfirmed"] = _cells([step])
            elif rc["state"] == "landed":
                applied.append((step, r["before"]))
                landed_late = True
                report["reason"] = f"the {step.label} write returned after the timeout, and its value landed"
            elif rc["state"] == "unchanged":
                report["reason"] = (f"{app} did not answer the {step.label} write within {call_budget_s:g} s, and "
                                    f"the call returned later with nothing landed")
            else:
                report["left"] = _cells([step])
                report["reason"] = (f"the {step.label} write returned after the timeout, and the target holds "
                                    f"{rc['detail']}")
        _rollback(report, applied, answer, budget_s, landed_late)
        app_steps = [(s, b) for s, b in applied if _is_app_step(s)]
        if app_steps:
            _restore_app(app_steps, make_ctx, call_budget_s, report, app_alive=app_alive, first_ctx=answer, app=app)
        _set_message(report, cells, app)
        return report
    _set_message(report, cells, app)
    return report


def _alerts_note(state, app="Excel"):
    """What the message says about the application's alert setting while the restore is not done."""
    if state == "pending":
        return f" {app} alerts are temporarily off. The commit turns them back on when {app} answers."
    if state and state.startswith("stopped"):
        return f" {app} alerts may still be off: {state.split(': ', 1)[-1]}."
    return ""


def _set_message(report, cells, app="Excel"):
    s, reason = report["status"], report["reason"]
    alerts = _alerts_note(report.get("app_restore_state"), app)
    if s == "committed":
        report["message"] = "Committed."
    elif s == "refused" and report.get("unconfirmed"):
        tail = (f"Check {' and '.join(report['unconfirmed'])} before you save: the write was turned away, and its "
                f"value could not be read back.")
        if report["rollback"]:
            tail = "Finished steps were rolled back. " + tail
        report["message"] = f"Refused: {reason}. {tail}{alerts}"
    elif s == "refused":
        tail = "Finished steps were rolled back." if report["rollback"] else "Nothing was written."
        if report["left"]:
            tail += (f" Left as it is: {', '.join(report['left'])}, which holds a value the commit did not write.")
        report["message"] = f"Refused: {reason}. {tail}{alerts}"
    elif s == "unknown":
        report["message"] = (f"Outcome unknown: {reason}. Check {' and '.join(cells)} before you save, because a write "
                             f"may still complete.{alerts}")
    else:
        report["message"] = f"Refused, and not fully rolled back: {reason}. Check {' and '.join(cells)}.{alerts}"
