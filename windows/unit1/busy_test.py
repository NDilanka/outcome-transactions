"""Forced-busy test for the in-app Excel commit: the readiness gate and the checked writes (com_gate.py).

Excel is made busy with a modal Open dialog. A helper process opens it through COM ("hold"), and while it is open
Excel turns away calls from other processes. The commit is the matrix's in-app edit (B2 1000 -> 5000, with the
user's D1 note unsaved), made by Excel.live_agent.

  control           no dialog. The gate passes and the write commits.
  gate-busy         dialog open before the commit. The gate refuses ("Excel busy") and no write is tried.
  write-retry-ok    gate passes. The dialog opens before the write and closes 3 s later, inside the 10 s write
                    budget. The rejected writes are retried and the commit lands.
  write-exhausted   gate passes. The dialog stays open past the 10 s write budget. The commit refuses, and the
                    target reads back unchanged after every rejection.
  guard-no-prompt   layer 1 on the commit path. A save over an existing file inside the write raises no prompt,
                    because the commit's DisplayAlerts = False stays in force. The commit lands.
  hang-late-yes     layer 3. A replace prompt (alerts on) blocks the write call. The 5 s timeout fires, the target is
                    polled, the prompt is answered at 8 s, the write returns late, and the commit rolls it back.
  hang-no-answer    layer 3. The same prompt is not answered during the commit. The outcome is reported unknown after
                    the reconcile budget. Then the harness answers No, and the call returns with nothing landed.

After each run the dialog is closed, the disk file is checked, and the user saves. The disk file must hold the
user's note, and the agent's edit only when the commit landed.

  py -3 windows\\unit1\\busy_test.py run <case> <rep>
  py -3 windows\\unit1\\busy_test.py matrix      3 reps of each case, results/busy/
  py -3 windows\\unit1\\busy_test.py report
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

import win32gui
import win32process

from com_gate import describe, is_busy, ready_gate, remote_error
from open_doc_experiment import BASE, Excel, excel_ready_probe, xlsx_state
from otx_win import free_mb, kill_pid, pid_alive, redact, wait_for_memory

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "work", "busy")
RESULTS = os.path.join(HERE, "results", "busy")
MIN_FREE_MB = 350
WM_CLOSE = 0x0010
CASES = {
    "control": dict(dialog=None, expect="control"),
    "gate-busy": dict(dialog="before-gate", expect="gate-busy"),
    "write-retry-ok": dict(dialog="before-write", close_after_s=3.0, expect="retry-ok"),
    "write-exhausted": dict(dialog="before-write", close_after_s=None, expect="write-exhausted"),
    # Layer 1 on the commit path: the guard has DisplayAlerts off, so the save over an existing file goes through with
    # no prompt, and the commit lands.
    "guard-no-prompt": dict(dialog="prompt-in-write", alerts_on=False, expect="guard-no-prompt"),
    # Layer 3. The write call makes Excel show a replace prompt. alerts_on sets DisplayAlerts back on inside the write:
    # the test raises a prompt the guard did not stop, which the guard alone cannot rule out. The timeout fires, and
    # the reconcile poll sees the target while the call is pending.
    "hang-late-yes": dict(dialog="prompt-in-write", alerts_on=True, answer="Yes", answer_after_s=8.0,
                          expect="late-landed"),
    "hang-no-answer": dict(dialog="prompt-in-write", alerts_on=True, answer="No", answer_after_s=None,
                           expect="unknown"),
}


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def excel_windows(pid, visible_only=True):
    """Top-level windows of one Excel process, other than its main window. Hidden windows are listed only when asked,
    so a dialog that never showed can be diagnosed."""
    found = []

    def visit(hwnd, _):
        visible = bool(win32gui.IsWindowVisible(hwnd))
        if visible_only and not visible:
            return
        _, wpid = win32process.GetWindowThreadProcessId(hwnd)
        cls = win32gui.GetClassName(hwnd)
        if wpid == pid and cls != "XLMAIN":
            found.append(dict(hwnd=hwnd, cls=cls, title=win32gui.GetWindowText(hwnd), visible=visible))

    win32gui.EnumWindows(visit, None)
    return found


def is_dialog(w):
    return w["cls"] == "#32770" or "bosa" in w["cls"].lower()


BM_CLICK = 0x00F5


def click_dialog_button(pid, label):
    """Click the button with this label (Yes, No, OK) in every dialog of one Excel process. PostMessage, so the
    harness never waits on Excel. Returns the labels clicked."""
    clicked = []
    for w in excel_windows(pid):
        if not is_dialog(w):
            continue
        buttons = []

        def child(h, _):
            if win32gui.GetClassName(h) == "Button":
                buttons.append((h, win32gui.GetWindowText(h).replace("&", "")))

        win32gui.EnumChildWindows(w["hwnd"], child, None)
        for h, text in buttons:
            if text == label:
                win32gui.PostMessage(h, BM_CLICK, 0, 0)
                clicked.append(text)
    return clicked


def close_dialogs(pid):
    """Cancel every open dialog of this Excel process (WM_CLOSE on the dialog window)."""
    closed = []
    for w in excel_windows(pid):
        if is_dialog(w):
            win32gui.PostMessage(w["hwnd"], WM_CLOSE, 0, 0)
            closed.append(w["cls"])
    return closed


HELPERS = []  # helper processes this run started; killed in the run's cleanup


def hold(path, log_path):
    """Helper process: opens the workbook's Open dialog through COM. Returns when the dialog is closed.

    It refuses to open the dialog unless the workbook belongs to the Excel process under test, so the dialog
    cannot land in another instance."""
    import win32com.client
    import win32process

    def note(msg):
        with open(log_path, "a") as f:
            f.write(f"{time.time():.2f} {msg}\n")

    note(f"helper pid {os.getpid()}")
    wb = win32com.client.GetObject(os.path.abspath(path))
    app_pid = win32process.GetWindowThreadProcessId(wb.Application.Hwnd)[1]
    note(f"workbook belongs to Excel pid {app_pid}; wanted {os.environ.get('BUSY_EXCEL_PID')}")
    if str(app_pid) != os.environ.get("BUSY_EXCEL_PID"):
        note("refused: not the Excel under test")
        sys.exit(3)
    note("calling Dialogs(1).Show")
    result = wb.Application.Dialogs(1).Show()  # xlDialogOpen
    note(f"Show returned {result}")


class HolderError(RuntimeError):
    """The Open dialog did not show. diag says what the harness could see: the helper's state and log, and every
    window of the Excel process, hidden ones included."""

    def __init__(self, msg, diag):
        super().__init__(msg)
        self.diag = diag


def helper_diag(p, log_path, pid):
    return dict(helper_alive=p.poll() is None, helper_log=_read(log_path),
                excel_windows=[dict(cls=w["cls"], visible=w["visible"])
                               for w in excel_windows(pid, visible_only=False)])


def start_holder(path, pid, log_path):
    if os.path.exists(log_path):
        os.remove(log_path)
    env = dict(os.environ, BUSY_EXCEL_PID=str(pid))
    p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "hold", path, log_path],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    HELPERS.append(p)
    t0 = time.time()
    while time.time() - t0 < 15:
        if p.poll() is not None:
            raise HolderError(f"dialog helper exited {p.returncode}", helper_diag(p, log_path, pid))
        seen = excel_windows(pid)
        if any(is_dialog(w) for w in seen):
            return p, [w["cls"] for w in seen]
        time.sleep(0.2)
    diag = helper_diag(p, log_path, pid)
    p.kill()
    raise HolderError("the Excel dialog did not open within 15 s", diag)


def _read(path):
    try:
        with open(path) as f:
            return f.read()[-400:]
    except OSError:
        return "(no log)"


def dialog_seconds(log_path):
    """Seconds the helper held the dialog: Show called to Show returned, from the helper's own log."""
    try:
        with open(log_path) as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    start = next((float(x.split()[0]) for x in lines if "calling Dialogs" in x), None)
    end = next((float(x.split()[0]) for x in lines if "Show returned" in x), None)
    return round(end - start, 2) if start and end else None


def wait_busy(app, budget_s=2.0):
    """Poll Excel until it is busy: a call is turned away, or Application.Ready is False. With a modal dialog open,
    Excel answers Ready = False with no error (results/busy/unit1-modal-probe.md), so a check for exceptions alone
    misses it. The probe runs inside the commit's write call, so its budget stays well under CALL_BUDGET_S."""
    t0 = time.time()
    tries = 0
    while time.time() - t0 < budget_s:
        tries += 1
        try:
            ready = app.Ready
        except Exception as e:
            # pywin32 reports a turned-away member lookup as AttributeError with no code, so the classification is
            # the gate's (com_gate.is_busy), not a check of hresult alone.
            r = remote_error(e)
            if is_busy(r):
                return dict(busy=True, tries=tries, last_error=describe(r))
            return dict(busy=False, tries=tries, last_error=repr(e)[:120])
        if not ready:
            return dict(busy=True, tries=tries, last_error="Application.Ready is False")
        time.sleep(0.1)
    return dict(busy=False, tries=tries, last_error=None)


def start_closer(pid, delay_s, log_path):
    return subprocess.Popen([sys.executable, os.path.abspath(__file__), "close-after", str(pid), str(delay_s),
                             log_path])


def display_alerts(adapter):
    """Application.DisplayAlerts as the harness reads it now. Excel turns a read away while a prompt is open."""
    try:
        return bool(adapter.app.DisplayAlerts)
    except Exception as e:
        return f"unreadable: {repr(e)[:80]}"


def mem_or_unreadable(adapter):
    """adapter.mem_state(), or a record that the state could not be read. Excel turns reads away while a dialog is
    open, so a failed read after the commit fails the verdict instead of ending the run."""
    try:
        return adapter.mem_state()
    except Exception as e:
        return dict(agent=None, user=None, others_ok=None, unreadable=repr(e)[:160])


def finish_helper(p):
    if p is None:
        return None
    try:
        p.wait(timeout=20)
    except subprocess.TimeoutExpired:
        p.kill()
        return "killed after 20 s"
    return f"exit {p.returncode}"


def verdict(spec, rec):
    c = rec["commit"]
    disk = rec["disk_after_user_save"]
    mem = rec["mem_after_commit"]
    kind = spec["expect"]
    base_ok = (disk["user"] and disk["others_ok"] and mem["user"] and mem["others_ok"]
               and rec.get("display_alerts_final") is True)
    if kind == "late-landed":
        rc = c.get("reconcile") or {}
        ok = (c["status"] == "refused" and c.get("late_landing") == "landed after the timeout, rolled back"
              and rc.get("state") == "landed" and rc.get("returned") is True
              and rec.get("alerts_seen_in_write") is False and rec.get("scratch_saved") is True
              and rec["commit_seconds"] < 45 and not disk["agent"] and not mem["agent"] and base_ok)
        label = "write timed out, prompt answered, the late landing caught and rolled back, file and user edit unchanged"
    elif kind == "unknown":
        rc = c.get("reconcile") or {}
        restore = c.get("app_restore") or []
        ok = (c["status"] == "unknown" and "Check B2 before you save" in (c.get("message") or "")
              and rc.get("state") == "unknown" and rc.get("returned") is False
              and rec["commit_seconds"] < 35 and rec.get("answer_after_commit") == ["No"]
              and rec.get("alerts_seen_in_write") is False and rec.get("scratch_saved") is False
              and [x["status"] for x in restore] == ["restored"]  # already: the injected write had set it back on
              and (c.get("late_outcome") or {}).get("state") == "unchanged"
              and rec.get("mem_after_answer", {}).get("agent") is False
              and not disk["agent"] and not mem["agent"] and base_ok)
        label = ("write timed out with no answer: outcome reported unknown, prompt then declined, nothing landed, "
                 "alerts restored when the call returned")
    elif kind == "guard-no-prompt":
        ok = (c["status"] == "committed" and rec.get("alerts_seen_in_write") is False
              and rec.get("scratch_saved") is True and c["rejections"] == 0 and rec["commit_seconds"] < 10
              and disk["agent"] and mem["agent"] and base_ok)
        label = "guard kept alerts off: the save over an existing file raised no prompt, and the commit committed"
    elif kind in ("control", "retry-ok"):
        ok = (c["status"] == "committed" and disk["agent"] and mem["agent"] and base_ok
              and (c["rejections"] >= 1) == (kind == "retry-ok")
              and all(x == repr(1000.0) for x in c["checks"]))
        label = "committed" if kind == "control" else f"committed after {c['rejections']} rejected writes retried"
    elif kind == "gate-busy":
        ok = (c["status"] == "refused" and c["reason"] == "Excel busy" and c["gate"]["ok"] is False
              and c["rejections"] == 0 and rec["sha_after_commit"] == rec["sha_before"]
              and not disk["agent"] and not mem["agent"] and base_ok)
        label = "refused by the gate, no write tried, file and user edit unchanged"
    else:
        # A read-back during the dialog is either unchanged (1000.0) or unreadable (busy); the harness reads the
        # file and the cell again after the dialog closes. The alert setting was off while Excel was busy, so the
        # refusal says so, and the restore lands once the dialog closes.
        ok = (c["status"] == "refused" and c["rejections"] >= 1
              and (c["reason"].startswith("busy: rejected") or c["reason"].startswith("rejected ("))
              and all(x == repr(1000.0) or x.startswith("unreadable") for x in c["checks"])
              and "temporarily off" in (c.get("message") or "") and c.get("app_restore_state") == "restored"
              and not disk["agent"] and not mem["agent"] and base_ok)
        label = ("write rejected, retry budget spent, commit refused, file and user edit unchanged, alerts "
                 "restored after the dialog closed")
    if ok:
        return "CORRECT: " + label
    return "WRONG: " + json.dumps(dict(commit=c, disk=disk, mem=mem, sha_same=rec["sha_after_commit"] == rec["sha_before"]),
                                   default=str)[:600]


def run(case, rep):
    spec = CASES[case]
    name = f"{case}-r{rep}"
    d = os.path.join(WORK, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    path = os.path.join(d, "budget.xlsx")
    shutil.copy(os.path.join(BASE, "budget.xlsx"), path)
    rec = dict(run=name, case=case, rep=rep, expect=spec["expect"], status="ok", dialog_windows=[])
    adapter = Excel()
    holder = closer = answerer = None
    try:
        rec["free_mb_before"] = free_mb()
        if not wait_for_memory(MIN_FREE_MB, 120):
            rec["status"] = f"skipped: free memory below {MIN_FREE_MB} MB"
            return rec
        adapter.launch()
        rec["office"] = adapter.version
        rec["pid"] = adapter.pid
        with open(os.path.join(d, "pid.txt"), "w") as f:
            f.write(str(adapter.pid))
        adapter.open(path)
        time.sleep(1)
        adapter.user_edit()
        rec["mem_before_commit"] = adapter.mem_state()
        rec["sha_before"] = sha(path)

        def open_dialog_before_write(app):
            """Runs inside the first write call, on the commit's worker thread: after the pre-write read, before Excel
            sees the write. app is the worker's own Application object. A COM object made on the main thread cannot be
            called here (Excel answers RPC_E_WRONG_THREAD), so the probe would read the dialog as absent."""
            nonlocal holder, closer
            try:
                holder, seen = start_holder(path, adapter.pid, os.path.join(d, "holder.log"))
            except HolderError as e:
                rec["dialog_windows"].append(dict(when="before-first-write", error=str(e), diag=e.diag))
                raise
            probe = wait_busy(app)
            rec["dialog_windows"].append(dict(when="before-first-write", classes=seen, busy_probe=probe))
            if not probe["busy"]:
                raise RuntimeError(f"Excel was not busy with the dialog open: {probe}")
            if spec.get("close_after_s") is not None:
                closer = start_closer(adapter.pid, spec["close_after_s"], os.path.join(d, "closer.log"))

        def wrap(step):
            real_write = step.write
            armed = [True]

            def write(view, v):
                if armed[0]:
                    armed[0] = False
                    open_dialog_before_write(view.Application)
                return real_write(view, v)
            return step._replace(write=write)

        scratch_target = os.path.join(d, "scratch-target.xlsx")
        shutil.copy(path, scratch_target)

        def prompt_in_write(step):
            """The write call makes Excel show a replace prompt: SaveAs of a scratch workbook over an existing file.
            It runs on the commit's worker thread, inside the write call, and the user's write runs only if the save
            went through. With alerts_on, DisplayAlerts is set back on inside the write: a prompt the guard did not
            stop. Without it, the guard's DisplayAlerts = False stays in force and the save raises no prompt."""
            real_write = step.write
            armed = [True]

            def write(view, v):
                nonlocal answerer
                if armed[0]:
                    armed[0] = False
                    app = view.Application
                    rec["alerts_seen_in_write"] = bool(app.DisplayAlerts)
                    if spec.get("alerts_on"):
                        app.DisplayAlerts = True
                        rec["injected_prompt_at"] = round(time.time(), 2)
                        if spec.get("answer_after_s") is not None:
                            answerer = subprocess.Popen([sys.executable, os.path.abspath(__file__), "answer-after",
                                                         str(adapter.pid), str(spec["answer_after_s"]), spec["answer"],
                                                         os.path.join(d, "answer.log")])
                            HELPERS.append(answerer)
                    scratch = app.Workbooks.Add()
                    rec["scratch_saved"] = False
                    try:
                        scratch.SaveAs(scratch_target, 51)  # with alerts on, this blocks on Excel's replace prompt
                    except Exception as e:  # answering No makes SaveAs raise (-2146827284)
                        rec["save_error"] = repr(e)[:160]
                        raise
                    rec["scratch_saved"] = scratch.FullName.lower() == scratch_target.lower()
                    if not rec["scratch_saved"]:
                        raise RuntimeError("the save was declined")
                return real_write(view, v)
            return step._replace(write=write)

        if spec["dialog"] == "before-gate":
            try:
                holder, seen = start_holder(path, adapter.pid, os.path.join(d, "holder.log"))
            except HolderError as e:
                rec["dialog_windows"].append(dict(when="before-gate", error=str(e), diag=e.diag))
                raise
            rec["dialog_windows"].append(dict(when="before-gate", classes=seen))
        wrap_fn = {"before-write": wrap, "prompt-in-write": prompt_in_write}.get(spec["dialog"])
        t_commit = time.monotonic()
        crep = adapter.live_agent(wrap=wrap_fn)
        rec["commit_seconds"] = round(time.monotonic() - t_commit, 2)
        rec["commit"] = crep
        rec["closed_by_harness"] = close_dialogs(adapter.pid) if holder is not None else []
        if spec.get("answer_after_s") is None and spec.get("answer"):
            # No answer during the commit: the harness answers the prompt now, as the user would, after the report.
            rec["answer_after_commit"] = click_dialog_button(adapter.pid, spec["answer"])
            time.sleep(2)
            rec["mem_after_answer"] = adapter.mem_state()
        rec["helper_exit"] = finish_helper(holder)
        rec["closer_exit"] = finish_helper(closer)
        rec["answerer_exit"] = finish_helper(answerer)
        rec["answer_log"] = _read(os.path.join(d, "answer.log"))
        rec["dialog_open_s"] = dialog_seconds(os.path.join(d, "holder.log"))
        # The restore of Excel's alert setting may run on a background thread after the commit returns. Wait for it,
        # up to 15 s, before the value is read.
        t_alerts = time.monotonic()
        while time.monotonic() - t_alerts < 15 and display_alerts(adapter) is not True:
            time.sleep(0.25)
        rec["alerts_wait_s"] = round(time.monotonic() - t_alerts, 2)
        rec["display_alerts_final"] = display_alerts(adapter)
        rec["sha_after_commit"] = sha(path)
        rec["mem_after_commit"] = mem_or_unreadable(adapter)
        adapter.save()
        time.sleep(1)
        rec["disk_after_user_save"] = xlsx_state(path)
        rec["verdict"] = verdict(spec, rec)
    except Exception:
        rec["status"] = "error"
        rec["traceback"] = traceback.format_exc()[-1500:]
    finally:
        for p in HELPERS + [closer]:
            if p is not None and p.poll() is None:
                p.kill()
        pid = getattr(adapter, "pid", None)
        if pid is not None:
            # A dialog that a failed run left open would keep Excel busy, so it is closed before the quit.
            rec["closed_in_cleanup"] = close_dialogs(pid)
        try:
            # An unanswered prompt leaves an unsaved scratch workbook behind. With alerts off, Quit does not ask.
            adapter.app.DisplayAlerts = False
            adapter.close_doc()
            adapter.quit()
            rec["quit_ok"] = True
        except Exception as e:
            rec["quit_ok"] = False
            rec["quit_error"] = repr(e)[:200]
        if pid is not None:
            time.sleep(1)
            if pid_alive(pid):
                kill_pid(pid)
                rec["killed_excel_pid"] = pid
        os.makedirs(RESULTS, exist_ok=True)
        with open(os.path.join(RESULTS, name + ".json"), "w") as f:
            f.write(redact(json.dumps(rec, indent=1, default=str)))
    return rec


def matrix():
    os.makedirs(RESULTS, exist_ok=True)
    for case in CASES:
        for rep in (1, 2, 3):
            name = f"{case}-r{rep}"
            print("running", name, flush=True)
            try:
                subprocess.run([sys.executable, os.path.abspath(__file__), "run", case, str(rep)],
                               timeout=240, capture_output=True, text=True)
            except subprocess.TimeoutExpired:
                pid_file = os.path.join(WORK, name, "pid.txt")
                if os.path.exists(pid_file):
                    kill_pid(int(open(pid_file).read()))
                with open(os.path.join(RESULTS, name + ".json"), "w") as f:
                    json.dump({"run": name, "status": "timeout"}, f)
                print("  timeout", flush=True)
    report()


def report():
    rows = []
    for p in sorted(glob.glob(os.path.join(RESULTS, "*-r*.json"))):
        with open(p) as f:
            rows.append(json.load(f))
    lines = ["## Forced-busy commit per run", "",
             "| case | rep | commit | gate | rejections | read-back after each rejection | disk after commit | "
             "disk after user save | verdict |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r.get("status") != "ok":
            lines.append(f"| {r.get('case')} | {r.get('rep')} | - | - | - | - | - | - | {r.get('status')} |")
            continue
        c = r["commit"]
        gate = c.get("gate") or {}
        gate_s = "ok" if gate.get("ok") else f"{gate.get('reason')} after {gate.get('tries')} tries"
        disk = r["disk_after_user_save"]
        disk_s = "agent edit" if disk["agent"] else "prior value"
        lines.append(f"| {r['case']} | {r['rep']} | {c['status']}"
                     f"{' (' + c['reason'] + ')' if c.get('reason') else ''} | {gate_s} | {c.get('rejections', 0)} | "
                     f"{', '.join(c.get('checks', [])) or '-'} | "
                     f"{'agent edit' if r['sha_after_commit'] != r['sha_before'] else 'unchanged'} | "
                     f"{disk_s}, user note {'kept' if disk['user'] else 'lost'} | {r['verdict'].split(':')[0]} |")
    text = "\n".join(lines) + "\n"
    with open(os.path.join(RESULTS, "unit1-busy.md"), "w") as f:
        f.write(redact(text))
    print(redact(text))


HANG_PROBES = ("ready", "hwnd", "read-b2", "saved", "write-b2", "close-doc", "quit", "gate", "live-commit",
               "close-prompt", "quit-prompt", "write-circular", "write-circular-alerts-off",
               "saveas-prompt", "saveas-prompt-alerts-off", "close-prompt-alerts-off")
PROMPT_PROBES = ("close-prompt", "quit-prompt", "write-circular", "write-circular-alerts-off",
                 "saveas-prompt", "saveas-prompt-alerts-off", "close-prompt-alerts-off",
                 "savecopy-prompt", "savecopy-answer-yes", "scratch-prompt", "scratch-prompt-answer-yes")  # no holder: the call itself makes Excel show a modal
# prompt (save prompt on close, SaveAs over an existing file, circular-reference warning on a formula write)
HANG_LIMIT_S = 30.0


def probe_call(name, a):
    """One COM call, made the way the harness makes it, with no timeout. Each probe runs in its own child process."""
    if name == "ready":
        return a.app.Ready
    if name == "hwnd":
        return a.app.Hwnd
    if name == "read-b2":
        return a.ws.Range("B2").Value
    if name == "saved":
        return a.wb.Saved
    if name == "write-b2":
        a.ws.Range("B2").Value = 5000
        return "written"
    if name == "close-doc":
        a.wb.Close(False)
        return "closed"
    if name == "quit":
        a.app.Quit()
        return "quit"
    if name == "gate":
        return ready_gate(a.app, lambda: a.ws.Range("B2").Value)
    if name == "live-commit":
        return a.live_agent()
    if name == "close-prompt":
        a.wb.Close()  # no argument: a dirty workbook asks to save, inside the call
        return "closed"
    if name == "quit-prompt":
        a.app.Quit()
        return "quit"
    if name == "close-prompt-alerts-off":
        a.app.DisplayAlerts = False
        a.wb.Close()
        return "closed"
    if name == "write-circular":
        a.ws.Range("G7").Formula = "=G7+1"  # a circular reference: Excel warns with a modal message box
        return "written"
    if name == "write-circular-alerts-off":
        a.app.DisplayAlerts = False
        a.ws.Range("G7").Formula = "=G7+1"
        return "written"
    if name in ("scratch-prompt", "scratch-prompt-answer-yes"):
        # A scratch workbook, so the user's workbook keeps its name: SaveAs over an existing file asks to replace it.
        other = os.path.join(os.path.dirname(a.path), "scratch-target.xlsx")
        shutil.copy(a.path, other)
        if name == "scratch-prompt-answer-yes":
            subprocess.Popen([sys.executable, os.path.abspath(__file__), "answer-after", str(a.pid), "3", "Yes",
                              os.path.join(os.path.dirname(a.path), "answer.log")])
        a.app.DisplayAlerts = True
        scratch = a.app.Workbooks.Add()
        scratch.SaveAs(other, 51)
        scratch.Close(False)
        return "saved-scratch"
    if name in ("savecopy-prompt", "savecopy-answer-yes"):
        # SaveCopyAs over an existing copy: Excel asks before it replaces the file. The answer comes from a helper
        # that clicks Yes after 3 s (savecopy-answer-yes); savecopy-prompt is never answered, so it hangs.
        other = os.path.join(os.path.dirname(a.path), "copy.xlsx")
        shutil.copy(a.path, other)
        if name == "savecopy-answer-yes":
            subprocess.Popen([sys.executable, os.path.abspath(__file__), "answer-after", str(a.pid), "3", "Yes",
                              os.path.join(os.path.dirname(a.path), "answer.log")])
        a.app.DisplayAlerts = True
        a.wb.SaveCopyAs(other)
        return "saved-copy"
    if name in ("saveas-prompt", "saveas-prompt-alerts-off"):
        other = os.path.join(os.path.dirname(a.path), "other.xlsx")
        shutil.copy(a.path, other)  # the target already exists, so Excel asks before it replaces it
        if name.endswith("alerts-off"):
            a.app.DisplayAlerts = False
        a.wb.SaveAs(other, 51)
        return "saved"
    raise ValueError(name)


def hang_child(name):
    """Child process: Excel with the Open dialog up, then one call. Prints JSON lines: stage, then the outcome."""
    d = os.path.join(WORK, "hang", name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    path = os.path.join(d, "budget.xlsx")
    shutil.copy(os.path.join(BASE, "budget.xlsx"), path)
    a = Excel()
    a.launch()
    print(json.dumps({"stage": "launched", "excel_pid": a.pid}), flush=True)
    a.open(path)
    time.sleep(1)
    if name in PROMPT_PROBES:
        a.user_edit()  # unsaved change, so that closing asks to save
        holder, seen, busy = None, [], None
    else:
        holder, seen = start_holder(path, a.pid, os.path.join(d, "holder.log"))
        busy = wait_busy(a.app)
    print(json.dumps({"stage": "dialog-open", "windows": seen, "busy_probe": busy}), flush=True)
    t0 = time.monotonic()
    try:
        out = dict(outcome="returned", value=repr(probe_call(name, a))[:160], error=None)
    except Exception as e:
        out = dict(outcome="raised", value=None, error=f"{type(e).__name__}: {repr(e)[:160]}")
    out["seconds"] = round(time.monotonic() - t0, 2)
    print(json.dumps({"stage": "result", **out}), flush=True)
    close_dialogs(a.pid)
    if holder is not None:
        holder.kill()
    try:
        a.close_doc()
        a.quit()
    except Exception:
        pass
    time.sleep(1)
    if pid_alive(a.pid):
        kill_pid(a.pid)


def hang_repro():
    """Each probe runs with the Open dialog up. A probe that does not return within HANG_LIMIT_S is a hang: the
    child is killed, and its Excel with it."""
    import queue
    import threading

    os.makedirs(RESULTS, exist_ok=True)
    rows = []
    names = sys.argv[2:] or HANG_PROBES
    for name in names:
        print("probe", name, flush=True)
        p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "hang-child", name],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        lines = queue.Queue()

        def reader(stream=p.stdout):
            for line in stream:
                lines.put(line)
            lines.put(None)

        threading.Thread(target=reader, daemon=True).start()
        row = dict(probe=name, outcome=None, seconds=None, stage="start", excel_pid=None, busy_probe=None)
        opened_at = None
        t_begin = time.monotonic()
        while True:
            now = time.monotonic()
            if opened_at is not None and now - opened_at > HANG_LIMIT_S:
                row["outcome"] = f"HUNG: no return within {HANG_LIMIT_S:.0f} s (child killed)"
                row["seconds"] = f">{HANG_LIMIT_S:.0f}"
                p.kill()
                break
            try:
                line = lines.get(timeout=0.5)
            except queue.Empty:
                if opened_at is None and now - t_begin > 180:
                    row["outcome"] = "setup failed: no dialog within 180 s"
                    p.kill()
                    break
                continue
            if line is None:
                break
            msg = json.loads(line)
            if msg["stage"] == "launched":
                row["excel_pid"] = msg["excel_pid"]
            elif msg["stage"] == "dialog-open":
                row["stage"] = "dialog-open"
                row["busy_probe"] = msg["busy_probe"]
                opened_at = time.monotonic()
            elif msg["stage"] == "result":
                row.update(outcome=f"{msg['outcome']}: {msg['value'] if msg['outcome'] == 'returned' else msg['error']}",
                           seconds=msg["seconds"])
        p.wait()
        if row["excel_pid"] and pid_alive(row["excel_pid"]):
            kill_pid(row["excel_pid"])
        rows.append(row)
        print("  ", row["outcome"], row["seconds"], flush=True)
    lines_md = ["## Hang probe: one COM call with the Open dialog up (no timeout)", "",
                "| call | outcome | seconds | busy probe before the call |", "|---|---|---|---|"]
    for r in rows:
        bp = r["busy_probe"] or {}
        lines_md.append(f"| {r['probe']} | {r['outcome']} | {r['seconds']} | "
                        f"{'busy' if bp.get('busy') else bp.get('last_error', '-')} |")
    text = "\n".join(lines_md) + "\n"
    with open(os.path.join(RESULTS, "unit1-hang-repro.md"), "w") as f:
        f.write(redact(text))
    print(redact(text))


OLD_REF = "a284a78"  # the shipped commit before the hang fix
OLD_MARKS = os.path.join(WORK, "old-commit")


def load_old_module():
    """The shipped open_doc_experiment.py, read from git, so the run exercises that code and not this tree's."""
    src = subprocess.run(["git", "-C", os.path.dirname(os.path.dirname(HERE)), "show",
                          f"{OLD_REF}:windows/unit1/open_doc_experiment.py"], capture_output=True, check=True).stdout
    os.makedirs(OLD_MARKS, exist_ok=True)
    path = os.path.join(OLD_MARKS, f"open_doc_experiment_{OLD_REF}.py")
    with open(path, "wb") as f:
        f.write(src)
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"open_doc_experiment_{OLD_REF}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PromptingRange:
    """The shipped commit writes ws.Range("B2").Value = 5000. Its setter first makes Excel show the replace prompt
    (SaveAs of a scratch workbook over an existing file, alerts on, as the shipped code leaves them), then writes."""

    def __init__(self, rng, app, target):
        self._rng, self._app, self._target = rng, app, target

    @property
    def Value(self):
        return self._rng.Value

    @Value.setter
    def Value(self, v):
        scratch = self._app.Workbooks.Add()
        scratch.SaveAs(self._target, 51)  # blocks here on the prompt
        self._rng.Value = v


class PromptingSheet:
    def __init__(self, ws, app, target):
        self._ws, self._app, self._target = ws, app, target

    def Range(self, ref):
        r = self._ws.Range(ref)
        return PromptingRange(r, self._app, self._target) if ref == "B2" else r


def old_commit_child():
    """Child process: the shipped commit (no timeout, no guard) makes one write with the replace prompt inside."""
    old = load_old_module()
    d = os.path.join(WORK, "old-commit")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    path = os.path.join(d, "budget.xlsx")
    target = os.path.join(d, "scratch-target.xlsx")
    shutil.copy(os.path.join(BASE, "budget.xlsx"), path)
    shutil.copy(path, target)
    a = old.Excel()
    a.launch()
    print(json.dumps({"stage": "launched", "excel_pid": a.pid}), flush=True)
    a.open(path)
    time.sleep(1)
    a.user_edit()
    a.ws = PromptingSheet(a.ws, a.app, target)
    print(json.dumps({"stage": "commit-start"}), flush=True)
    t0 = time.monotonic()
    a.live_agent()
    print(json.dumps({"stage": "result", "outcome": "returned", "seconds": round(time.monotonic() - t0, 2)}),
          flush=True)


def old_commit():
    """Parent: runs the shipped commit in a child with the prompt inside its write. It must return within HANG_LIMIT_S."""
    import queue
    import threading

    os.makedirs(RESULTS, exist_ok=True)
    p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "old-commit-child"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    lines = queue.Queue()

    def reader():
        for line in p.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=reader, daemon=True).start()
    row = dict(commit=f"shipped {OLD_REF} live_agent", outcome=None, seconds=None, excel_pid=None, started=None)
    started = None
    while True:
        if started is not None and time.monotonic() - started > HANG_LIMIT_S:
            row.update(outcome=f"HUNG: the commit did not return within {HANG_LIMIT_S:.0f} s (child killed)",
                       seconds=f">{HANG_LIMIT_S:.0f}")
            p.kill()
            break
        try:
            line = lines.get(timeout=0.5)
        except queue.Empty:
            continue
        if line is None:
            break
        msg = json.loads(line)
        if msg["stage"] == "launched":
            row["excel_pid"] = msg["excel_pid"]
        elif msg["stage"] == "commit-start":
            started = time.monotonic()
        elif msg["stage"] == "result":
            row.update(outcome=f"returned: {msg['outcome']}", seconds=msg["seconds"])
    p.wait()
    if row["excel_pid"] and pid_alive(row["excel_pid"]):
        kill_pid(row["excel_pid"])
    text = "\n".join([
        f"## Shipped commit under the same prompt ({OLD_REF}, no timeout, no guard)", "",
        "| commit | outcome | seconds |", "|---|---|---|",
        f"| {row['commit']} | {row['outcome']} | {row['seconds']} |", ""])
    with open(os.path.join(RESULTS, f"unit1-hang-old-commit-{OLD_REF}.md"), "w") as f:
        f.write(redact(text))
    with open(os.path.join(RESULTS, f"unit1-hang-old-commit-{OLD_REF}.json"), "w") as f:
        json.dump(row, f, indent=1)
    print(redact(text))


MODAL_PROBE_MD = os.path.join(RESULTS, "unit1-modal-probe.md")


def modal_probe_rows(state, path, app, ws):
    """Calls made with Excel's Open dialog up (or not). pre-bound: objects bound before the dialog opened, as the
    commit's write holds them. fresh: a new binding made now, as a readiness probe or read makes it."""
    import win32com.client
    rows = []

    def add(name, fn):
        t0 = time.time()
        try:
            out = f"ok {fn()!r}"[:60]
        except Exception as e:
            out = f"error {describe(remote_error(e))}"
        rows.append(dict(state=state, call=name, outcome=out, seconds=round(time.time() - t0, 3)))

    add("pre-bound Application.Ready", lambda: app.Ready)
    add("pre-bound Application.Name", lambda: app.Name)
    add("pre-bound Range(B2).Value read", lambda: ws.Range("B2").Value)
    add("pre-bound Range(B2).Value write 1000 (unchanged value)", lambda: setattr(ws.Range("B2"), "Value", 1000))
    add("excel_ready_probe on pre-bound view", lambda: excel_ready_probe(ws))
    add("wait_busy on pre-bound Application", lambda: wait_busy(app))
    add("fresh GetObject(path).Application", lambda: win32com.client.GetObject(path).Application)
    return rows


def modal_probe():
    """Records how Excel answers this harness's calls with its Open dialog up. Evidence for the readiness gate and
    the write-busy classification (com_gate.BUSY_CODES). Excel only; writes nothing to the workbook except B2 = 1000,
    its own value, on a scratch copy."""
    import pythoncom
    os.makedirs(RESULTS, exist_ok=True)
    d = os.path.join(WORK, "modal-probe")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    path = os.path.join(d, "budget.xlsx")
    shutil.copy(os.path.join(BASE, "budget.xlsx"), path)
    pythoncom.CoInitialize()
    a = Excel()
    holder = None
    rows = []
    try:
        a.launch()
        a.open(path)
        time.sleep(1)
        rows += modal_probe_rows("dialog not open", path, a.app, a.ws)
        holder, seen = start_holder(path, a.pid, os.path.join(d, "holder.log"))
        rows += modal_probe_rows("Open dialog up", path, a.app, a.ws)
        rows += modal_probe_rows("Open dialog up (second round)", path, a.app, a.ws)
        closed = close_dialogs(a.pid)
        helper = finish_helper(holder)
        holder = None
        rows += modal_probe_rows("dialog closed", path, a.app, a.ws)
    finally:
        try:
            a.app.DisplayAlerts = False
            a.app.Quit()
        except Exception:
            pass
        if holder is not None and holder.poll() is None:
            holder.kill()
        if a.pid and pid_alive(a.pid):
            kill_pid(a.pid)
        pythoncom.CoUninitialize()
    lines = ["## Excel answers with its Open dialog up (measured)", "",
             f"Dialog windows seen: {seen}. Closed by the harness: {closed}. Helper: {helper}.", "",
             "| state | call | outcome | seconds |", "|---|---|---|---|"]
    lines += [f"| {r['state']} | {r['call']} | {r['outcome']} | {r['seconds']} |" for r in rows]
    text = "\n".join(lines) + "\n"
    with open(MODAL_PROBE_MD, "w") as f:
        f.write(redact(text))
    with open(os.path.join(RESULTS, "unit1-modal-probe.json"), "w") as f:
        json.dump(rows, f, indent=1)
    print(redact(text))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "modal-probe":
        modal_probe()
    elif cmd == "run":
        result = run(sys.argv[2], int(sys.argv[3]))
        print(json.dumps({"run": result.get("run"), "status": result.get("status"), "verdict": result.get("verdict")}))
    elif cmd == "matrix":
        matrix()
    elif cmd == "report":
        report()
    elif cmd == "hang":
        hang_repro()
    elif cmd == "hang-child":
        hang_child(sys.argv[2])
    elif cmd == "old-commit":
        old_commit()
    elif cmd == "old-commit-child":
        old_commit_child()
    elif cmd == "hold":
        hold(sys.argv[2], sys.argv[3])
    elif cmd == "answer-after":
        pid, delay_s, label, log_path = int(sys.argv[2]), float(sys.argv[3]), sys.argv[4], sys.argv[5]
        time.sleep(delay_s)
        clicked = click_dialog_button(pid, label)
        with open(log_path, "a") as f:
            f.write(f"{time.time():.2f} answer pid {os.getpid()}: clicked {label} on {clicked}\n")
    elif cmd == "close-after":
        pid, delay_s, log_path = int(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
        time.sleep(delay_s)
        seen = [(w["cls"], w["title"], bool(win32gui.IsWindowVisible(w["hwnd"]))) for w in excel_windows(pid)]
        closed = close_dialogs(pid)
        time.sleep(0.5)
        still = [w["cls"] for w in excel_windows(pid)]
        with open(log_path, "a") as f:
            f.write(f"{time.time():.2f} closer pid {os.getpid()}: seen {seen}; closed {closed}; still {still}\n")
