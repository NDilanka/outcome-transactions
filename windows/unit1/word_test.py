"""Word in-app commit under a dialog up in Word, and under in-call prompts.

  py -3 windows\\unit1\\word_test.py cases --label head|fixed [case ...]

Each case runs in a child process. The parent limits every stage, lists the Word dialogs while a call is stuck, and
kills only the PIDs the child reported starting: its own Word instance and its own helper process. Results go to
results/word/. Work folders are under work/word/ (git-ignored).

Cases:
  modal-dialog       a real Word Open dialog up in the instance under test (a helper process opens it, as busy_test
                     does for Excel). The commit runs with the dialog up.
  prompt-no-answer   SYNTHETIC HANG. The harness makes a real Word save prompt (SaveAs2 of a read-only copy, alerts on)
                     appear inside the commit's write call, and does not answer it during the commit.
  prompt-answer-8s   SYNTHETIC. The same prompt, cancelled 8 s after it appears.
  delay-landed-late  SYNTHETIC HANG. The harness sleeps 8 s inside the write call, then the write runs. No prompt.

The synthetic cases exercise the timeout and reconcile path. They are injected, not measured Word hangs: the committed
Word commit makes no save, open or close call, and no real commit call hung in the measurements.

The head label runs the committed Word.live_agent, which has no wrap hook, so the injection wraps the document it
reads. The fixed label runs the working tree's Word.live_agent with wrap, so the injection sits in the write step.
"""
import hashlib
import inspect
import json
import os
import queue
import shutil
import stat
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
BASE = os.path.join(HERE, "base")
WORK = os.path.join(HERE, "work", "word", "cases")
RESULTS = os.path.join(HERE, "results", "word")
REPO = os.path.dirname(os.path.dirname(HERE))
CASES = ("modal-dialog", "prompt-no-answer", "prompt-answer-8s", "delay-landed-late")
STAGE_LIMIT_S = 45.0  # the answer bound is 40 s; a stage past 45 s is a hang
LATE_WAIT_S = 12.0  # after the report, the harness answers any prompt, then waits for a late outcome
SYNTHETIC_DELAY_S = 8.0
SYNTHETIC_ANSWER_S = 8.0
DOCX_FORMAT = 16  # wdFormatDocumentDefault
WD_DIALOG_FILE_OPEN = 80
WM_CLOSE = 0x0010
EXPECT = {  # what the fixed commit must do; the head run is compared against the same expectations
    "modal-dialog": "refused by the gate as Word busy, nothing written, within 6.5 s",
    "prompt-no-answer": "unknown outcome, returned within 40 s, the cell left for the user to check",
    "prompt-answer-8s": "refused: the call returned later with nothing landed, within 40 s",
    "delay-landed-late": "refused, the late write rolled back, within 40 s",
}


def emit(**kw):
    print(json.dumps(kw, default=str), flush=True)


def word_windows(pid, visible_only=True):
    import win32gui
    import win32process
    found = []

    def visit(hwnd, _):
        _, wpid = win32process.GetWindowThreadProcessId(hwnd)
        if wpid != pid or (visible_only and not win32gui.IsWindowVisible(hwnd)):
            return
        cls = win32gui.GetClassName(hwnd)
        if cls != "OpusApp":
            found.append(dict(hwnd=hwnd, cls=cls, title=win32gui.GetWindowText(hwnd)[:200]))

    win32gui.EnumWindows(visit, None)
    return found


def is_dialog(w):
    return w["cls"] == "#32770" or w["cls"].startswith("bosa")


def dialog_text(hwnd):
    import win32gui
    out = []

    def child(h, _):
        text = win32gui.GetWindowText(h)[:200]
        if text:
            out.append(f"{win32gui.GetClassName(h)}: {text}")

    win32gui.EnumChildWindows(hwnd, child, None)
    return out[:12]


def close_dialogs(pid):
    """WM_CLOSE to each Word dialog of this instance: the harness's answer (cancel). PostMessage, so no COM call."""
    import win32gui
    closed = []
    for w in word_windows(pid):
        if is_dialog(w):
            win32gui.PostMessage(w["hwnd"], WM_CLOSE, 0, 0)
            closed.append(w["cls"])
    return closed


def timed_read(fn, budget_s=5.0):
    """Run a read on its own COM apartment with a fresh connection. Returns the value, an error, or not responding."""
    box = {}

    def work():
        import pythoncom
        pythoncom.CoInitialize()
        try:
            box["value"] = fn()
        except Exception as e:  # noqa: BLE001
            box["error"] = repr(e)[:160]
        finally:
            pythoncom.CoUninitialize()

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(budget_s)
    if t.is_alive():
        return "not responding"
    return box["value"] if "value" in box else box["error"]


def helper(path, log, word_pid):
    """Helper process: opens Word's Open dialog through COM. Refuses unless the document belongs to the Word under test."""
    import win32com.client
    import win32process

    def note(msg):
        with open(log, "a") as f:
            f.write(f"{time.time():.2f} {msg}\n")

    note(f"helper pid {os.getpid()}")
    doc = win32com.client.GetObject(os.path.abspath(path))
    app_pid = win32process.GetWindowThreadProcessId(doc.ActiveWindow.Hwnd)[1]
    note(f"document belongs to Word pid {app_pid}; wanted {word_pid}")
    if str(app_pid) != word_pid:
        note("refused: not the Word under test")
        sys.exit(3)
    note("calling Dialogs(80).Show")
    res = doc.Application.Dialogs(WD_DIALOG_FILE_OPEN).Show()
    note(f"Show returned {res}")


class InjectedDoc:
    """Head only: the committed Word.live_agent has no wrap hook, so its write setter is wrapped. The injection runs
    inside the commit's Range.Text assignment, which is the commit's write call."""

    def __init__(self, doc, app, inject):
        self._doc, self._app, self._inject = doc, app, inject

    @property
    def Paragraphs(self):
        return InjectedParagraphs(self._doc.Paragraphs, self._app, self._inject)


class InjectedParagraphs:
    def __init__(self, paras, app, inject):
        self._paras, self._app, self._inject = paras, app, inject

    def __call__(self, i):
        return InjectedParagraph(self._paras(i), self._app, self._inject)


class InjectedParagraph:
    def __init__(self, para, app, inject):
        self._para, self._app, self._inject = para, app, inject

    @property
    def Range(self):
        return InjectedRange(self._para.Range, self._app, self._inject)


class InjectedRange:
    def __init__(self, rng, app, inject):
        self._rng, self._app, self._inject = rng, app, inject

    def __getattr__(self, name):
        return getattr(self._rng, name)

    @property
    def Text(self):
        return self._rng.Text

    @Text.setter
    def Text(self, v):
        self._inject(self._app)
        self._rng.Text = v


def inject(case, app, state):
    """Runs inside the commit's write call, on the thread that makes it (the worker in the fixed code)."""
    if case == "delay-landed-late":
        emit(stage="injected", kind="sleep", seconds=SYNTHETIC_DELAY_S)
        time.sleep(SYNTHETIC_DELAY_S)
        return
    app.DisplayAlerts = -1  # alerts on inside the write: the prompt the guard should have kept away
    if case == "prompt-answer-8s":
        threading.Timer(SYNTHETIC_ANSWER_S, close_dialogs, args=(state["pid"],)).start()
    emit(stage="injected", kind="save-prompt", answer_after_s=SYNTHETIC_ANSWER_S if case == "prompt-answer-8s" else None)
    scratch = app.Documents.Add()
    try:
        scratch.SaveAs2(state["ro_target"], DOCX_FORMAT)  # blocks on Word's read-only prompt until answered
        state["save_returned"] = True
    except Exception as e:  # noqa: BLE001
        state["save_error"] = repr(e)[:160]
        raise


def summarize(rep):
    if rep is None:
        return None
    keep = ("status", "reason", "message", "rejections", "reconcile", "late_landing", "late_outcome", "rollback",
            "app_restore_state", "restore_log", "gate", "unconfirmed")
    return {k: rep.get(k) for k in keep}


def child(case):
    import win32com.client
    import open_doc_experiment as X
    d = os.path.join(WORK, case)
    if os.path.isdir(d):
        shutil.rmtree(d, onerror=lambda f, p, _: (os.chmod(p, stat.S_IWRITE), f(p)))
    os.makedirs(d)
    path = os.path.join(d, "budget.docx")
    ro_target = os.path.join(d, "readonly-target.docx")
    shutil.copy(os.path.join(BASE, "budget.docx"), path)
    shutil.copy(os.path.join(BASE, "budget.docx"), ro_target)
    os.chmod(ro_target, stat.S_IREAD)
    state = dict(pid=None, ro_target=os.path.abspath(ro_target))

    def fresh():
        return win32com.client.GetObject(os.path.abspath(path))

    a = X.Word()
    a.launch()
    state["pid"] = a.pid
    emit(stage="launched", pid=a.pid)
    a.app.DisplayAlerts = -1  # the user's Word runs with alerts on
    a.open(os.path.abspath(path))
    time.sleep(1)
    helper_proc = None
    if case == "modal-dialog":
        log = os.path.join(d, "helper.log")
        helper_proc = subprocess.Popen([sys.executable, os.path.abspath(__file__), "helper", os.path.abspath(path), log,
                                        str(a.pid)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        emit(stage="helper", pid=helper_proc.pid)
        t0 = time.time()
        dialogs = []
        while time.time() - t0 < 15:
            dialogs = [w for w in word_windows(a.pid) if is_dialog(w)]
            if dialogs:
                break
            time.sleep(0.2)
        emit(stage="dialog-up", waited_s=round(time.time() - t0, 2),
             dialogs=[dict(cls=w["cls"], title=w["title"], text=dialog_text(w["hwnd"])) for w in dialogs])
    injects = case != "modal-dialog"
    if "wrap" in inspect.signature(a.live_agent).parameters:
        def wrap(step):
            real_write = step.write
            armed = [True]

            def write(view, v):
                if armed[0] and injects:
                    armed[0] = False
                    inject(case, view.Application, state)
                return real_write(view, v)

            return step._replace(write=write)

        def commit():
            return a.live_agent(wrap=wrap)
    else:
        if injects:
            a.doc = InjectedDoc(a.doc, a.app, lambda app: inject(case, app, state))

        def commit():
            return a.live_agent()
    emit(stage="commit-start")
    t0 = time.monotonic()
    try:
        rep = commit()
        emit(stage="result", outcome="returned", seconds=round(time.monotonic() - t0, 2), report=summarize(rep))
    except Exception as e:  # noqa: BLE001
        rep = None
        emit(stage="result", outcome="raised", seconds=round(time.monotonic() - t0, 2), error=repr(e)[:200])
    closed = close_dialogs(a.pid)  # the harness answers any prompt still up, after the report, as the user would
    emit(stage="answered-after-report", closed=closed)
    time.sleep(LATE_WAIT_S)
    emit(stage="after", alerts=timed_read(lambda: fresh().Application.DisplayAlerts),
         para2=timed_read(lambda: fresh().Paragraphs(2).Range.Text.rstrip("\r\x07")),
         late=None if rep is None else dict(late_outcome=rep.get("late_outcome"),
                                            late_landing=rep.get("late_landing"),
                                            app_restore_state=rep.get("app_restore_state")),
         save_returned=state.get("save_returned"), save_error=state.get("save_error"))
    if helper_proc is not None:
        try:
            helper_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def verdict(case, row):
    if row.get("hung"):
        return "HUNG"
    rep = row.get("report") or {}
    sec = row.get("seconds")
    para2 = row.get("para2")
    if row.get("outcome") == "raised":
        return "WRONG: the commit raised an unclassified error"
    if case == "modal-dialog":
        ok = rep.get("status") == "refused" and "busy" in (rep.get("reason") or "") and para2 == "Total: 1000" \
            and sec is not None and sec <= 6.5
    elif case == "prompt-no-answer":
        ok = rep.get("status") == "unknown" and sec is not None and sec <= 40
    elif case == "prompt-answer-8s":
        ok = rep.get("status") == "refused" and sec is not None and sec <= 40 and "returned later" in \
            (rep.get("reason") or "") and para2 == "Total: 1000"
    else:
        lr = rep.get("late_landing") or ""
        ok = rep.get("status") == "refused" and "rolled back" in lr and para2 == "Total: 1000" and sec is not None \
            and sec <= 40
    return "CORRECT" if ok else "WRONG"


def git_state():
    head = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"], capture_output=True,
                          text=True).stdout.strip()
    diff = subprocess.run(["git", "-C", REPO, "diff", "--quiet", "HEAD", "--", "windows/unit1/open_doc_experiment.py"])
    return head, diff.returncode != 0


def live_agent_sha(src_path):
    with open(src_path, encoding="utf-8") as f:
        text = f.read()
    start = text.index("    def live_agent(", text.index("\nclass Word("))
    end = text.index("    def mem_state(", start)
    return hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()[:12]


def parent(case, label):
    from otx_win import kill_pid, pid_alive, redact
    p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "child", case], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)
    lines = queue.Queue()

    def reader():
        for line in p.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=reader, daemon=True).start()
    row = dict(case=case, label=label, outcome=None, pids=[], hung=False, stages=[])
    stage, stage_t = "launch", time.monotonic()
    while True:
        if time.monotonic() - stage_t > STAGE_LIMIT_S:
            row.update(hung=True, outcome=f"HUNG: stage '{stage}' did not finish within {STAGE_LIMIT_S:.0f} s")
            row["hung_dialogs"] = [dict(cls=w["cls"], title=w["title"], text=dialog_text(w["hwnd"]))
                                   for pid in row["pids"] for w in word_windows(pid) if is_dialog(w)]
            break
        try:
            line = lines.get(timeout=0.2)
        except queue.Empty:
            continue
        if line is None:
            break
        msg = json.loads(line)
        stage = msg.pop("stage")
        row["stages"].append(stage)
        if stage == "launched" or stage == "helper":
            row["pids"].append(msg["pid"])
        elif stage == "dialog-up":
            row["dialogs"] = msg["dialogs"]
            row["dialog_waited_s"] = msg["waited_s"]
        elif stage == "result":
            row.update(outcome=msg["outcome"], seconds=msg["seconds"], report=msg.get("report"),
                       error=msg.get("error"))
        elif stage == "after":
            row.update(alerts_after=msg["alerts"], para2=msg["para2"], late=msg["late"],
                       save_returned=msg.get("save_returned"), save_error=msg.get("save_error"))
        elif stage == "injected":
            row["injected"] = msg
        stage_t = time.monotonic()
    p.kill()
    p.wait()
    for pid in row["pids"]:
        if pid_alive(pid):
            kill_pid(pid)
            row.setdefault("killed_pids", []).append(pid)
    row["verdict"] = verdict(case, row)
    row["expected"] = EXPECT[case]
    return json.loads(redact(json.dumps(row, default=str)))


def cases(label, names):
    os.makedirs(RESULTS, exist_ok=True)
    head, differs = git_state()
    sha = live_agent_sha(os.path.join(HERE, "open_doc_experiment.py"))
    rows = []
    for name in names:
        row = parent(name, label)
        row.update(git_head=head, working_tree_differs_from_head=differs, live_agent_sha=sha)
        rows.append(row)
        with open(os.path.join(RESULTS, f"{label}-{name}.json"), "w") as f:
            json.dump(row, f, indent=1)
        print(json.dumps({k: row.get(k) for k in ("case", "outcome", "seconds", "verdict", "para2", "alerts_after")}),
              flush=True)
    write_table(label, rows, head, differs, sha)


def write_table(label, rows, head, differs, sha):
    lines = [f"## Word cases: {label}", "",
             f"Git HEAD {head}; working tree open_doc_experiment.py differs from HEAD: {differs}; live_agent sha "
             f"{sha}.", "",
             "| case | commit outcome | status | reason | seconds | DisplayAlerts after | paragraph 2 after | "
             "late outcome | expected | verdict |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        rep = r.get("report") or {}
        late = (r.get("late") or {}).get("late_outcome") or {}
        lines.append(f"| {r['case']} | {r.get('outcome') or r.get('error')} | {rep.get('status')} | "
                     f"{(rep.get('reason') or '').replace('|', '/')} | {r.get('seconds')} | {r.get('alerts_after')} | "
                     f"{r.get('para2')} | {late.get('state')} | {r['expected']} | {r['verdict']} |")
    text = "\n".join(lines) + "\n"
    with open(os.path.join(RESULTS, f"unit1-word-{label}.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "child":
        child(sys.argv[2])
    elif cmd == "helper":
        helper(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "cases":
        label = sys.argv[sys.argv.index("--label") + 1]
        names = [a for a in sys.argv[2:] if a not in ("--label", label)] or list(CASES)
        cases(label, names)
    else:
        raise SystemExit(f"unknown command {cmd}")
