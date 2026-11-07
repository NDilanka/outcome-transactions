"""Which Word calls hang, and which return, under the conditions that matter for the Word commit.

  py -3 windows\\unit1\\word_probes.py writes      the commit's write, Paragraphs(2).Range.Text, under four conditions
  py -3 windows\\unit1\\word_probes.py prompts     calls that raise a Word prompt: SaveAs2 onto a read-only file, SaveAs2 and
                                                  Documents.Open onto a file another instance holds
  py -3 windows\\unit1\\word_probes.py modal       a Word Open dialog up in the instance: the readiness reads and the write

Each case runs in a child process. The parent limits the stage that a call is in, lists the visible Word dialogs while
a call is stuck, and kills only the PIDs the child reported starting: its own Word instances and its own helper
process. Results: results/word/probes/, with a table in unit1-word-probes.md. Work folders are under work/word/
(git-ignored).
"""
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
WORK = os.path.join(HERE, "work", "word", "probes")
RESULTS = os.path.join(HERE, "results", "word", "probes")
STAGE_LIMIT_S = 25.0
DOCX_FORMAT = 16  # wdFormatDocumentDefault
WD_DIALOG_FILE_OPEN = 80
WM_CLOSE = 0x0010
GROUPS = {
    "writes": ["baseline", "readonly-file", "changed-on-disk", "protected"],
    "prompts": ["save-readonly-target", "save-file-in-use", "open-file-in-use"],
    "modal": ["modal-open-dialog"],
}
DESCRIPTIONS = {
    "baseline": "write, file as copied",
    "readonly-file": "write, file read-only on disk when opened",
    "changed-on-disk": "write, file replaced on disk after it was opened (mtime moved)",
    "protected": "write, document protected for reading only",
    "save-readonly-target": "SaveAs2 onto a read-only file, alerts on (save prompt)",
    "save-file-in-use": "SaveAs2 onto a file a second instance holds open (File In Use)",
    "open-file-in-use": "Documents.Open of a file a second instance holds open (File In Use)",
    "modal-open-dialog": "Word Open dialog up in the instance: readiness reads, then the write",
}


def emit(**kw):
    print(json.dumps(kw, default=str), flush=True)


def timed_call(call, fn):
    """Runs one COM call and reports how it ended and how long it took."""
    emit(stage="call-start", call=call)
    t0 = time.monotonic()
    try:
        fn()
        out = "returned"
    except Exception as e:  # noqa: BLE001
        out = f"raised {repr(e)[:160]}"
    emit(stage="result", outcome=out, seconds=round(time.monotonic() - t0, 2))


def write_total(doc):
    """The commit's write: paragraph 2 without its paragraph mark."""
    r = doc.Paragraphs(2).Range
    r.MoveEnd(1, -1)
    r.Text = "Total: 5000"


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

    def add_text(h, _):
        text = win32gui.GetWindowText(h)[:200]
        if text:
            out.append(f"{win32gui.GetClassName(h)}: {text}")

    win32gui.EnumChildWindows(hwnd, add_text, None)
    return out[:12]


def dialogs_of(pids):
    return [dict(pid=pid, cls=w["cls"], title=w["title"], text=dialog_text(w["hwnd"]))
            for pid in pids for w in word_windows(pid) if is_dialog(w)]


def helper(path, log, word_pid):
    """Helper process: opens Word's Open dialog through COM, and only for the Word instance under test."""
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


def child(case):
    import open_doc_experiment as X
    d = os.path.join(WORK, f"{case}-{int(time.time())}")
    os.makedirs(d)
    path = os.path.abspath(os.path.join(d, "budget.docx"))
    ro = os.path.abspath(os.path.join(d, "readonly-target.docx"))
    shutil.copy(os.path.join(BASE, "budget.docx"), path)
    shutil.copy(os.path.join(BASE, "budget.docx"), ro)
    if case == "save-readonly-target":
        os.chmod(ro, stat.S_IREAD)
    a = X.Word()
    a.launch()
    emit(stage="launched", pid=a.pid)
    a.app.DisplayAlerts = -1
    if case in ("save-file-in-use", "open-file-in-use"):
        b = X.Word()
        b.launch()
        emit(stage="launched", pid=b.pid)
        b.app.DisplayAlerts = -1
        b.app.Documents.Open(path, False, False, False)
    if case == "readonly-file":
        os.chmod(path, stat.S_IREAD)
    if case == "modal-open-dialog":
        a.open(path)
        time.sleep(1)
        log = os.path.join(d, "helper.log")
        h = subprocess.Popen([sys.executable, os.path.abspath(__file__), "helper", path, log, str(a.pid)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        emit(stage="helper", pid=h.pid)
        t0 = time.time()
        dialogs = []
        while time.time() - t0 < 15:
            dialogs = [w for w in word_windows(a.pid) if is_dialog(w)]
            if dialogs:
                break
            time.sleep(0.2)
        emit(stage="dialog-up", waited_s=round(time.time() - t0, 2),
             dialogs=[dict(cls=w["cls"], title=w["title"], text=dialog_text(w["hwnd"])) for w in dialogs])
        reads = {}
        for name, fn in (("app_name", lambda: a.app.Name),
                         ("paragraph2", lambda: a.doc.Paragraphs(2).Range.Text)):
            t = time.monotonic()
            try:
                reads[name] = dict(value=str(fn())[:40], seconds=round(time.monotonic() - t, 2))
            except Exception as e:  # noqa: BLE001
                reads[name] = dict(error=repr(e)[:160], seconds=round(time.monotonic() - t, 2))
        emit(stage="reads", reads=reads)
        timed_call("write Paragraphs(2).Range.Text", lambda: write_total(a.doc))
        for w in dialogs:
            win32gui_close(w["hwnd"])
        return
    if case == "open-file-in-use":
        timed_call("Documents.Open of a file another instance holds",
                   lambda: a.app.Documents.Open(path, False, False, False))
        return
    if case in ("save-file-in-use", "save-readonly-target"):
        target = path if case == "save-file-in-use" else ro
        scratch = a.app.Documents.Add()
        timed_call(f"SaveAs2 onto {os.path.basename(target)}", lambda: scratch.SaveAs2(target, DOCX_FORMAT))
        return
    a.open(path)
    if case == "changed-on-disk":
        t = time.time() + 120
        os.utime(path, (t, t))
    if case == "protected":
        a.doc.Protect(3, True)
    timed_call("write Paragraphs(2).Range.Text", lambda: write_total(a.doc))


def win32gui_close(hwnd):
    import win32gui
    win32gui.PostMessage(hwnd, WM_CLOSE, 0, 0)


def parent(case):
    from otx_win import kill_pid, pid_alive, redact
    p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "child", case], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)
    lines = queue.Queue()

    def reader():
        for line in p.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=reader, daemon=True).start()
    row = dict(case=case, description=DESCRIPTIONS[case], outcome=None, hung=False, pids=[], stages=[])
    stage, stage_t = "launch", time.monotonic()
    while True:
        if stage != "result" and time.monotonic() - stage_t > STAGE_LIMIT_S:
            row.update(hung=True, outcome=f"HUNG: no result within {STAGE_LIMIT_S:.0f} s (last stage: {stage})")
            row["hung_dialogs"] = dialogs_of(row["pids"])
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
        elif stage == "call-start":
            row["call"] = msg["call"]
        elif stage == "result":
            row.update(outcome=msg["outcome"], seconds=msg["seconds"])
        elif stage == "dialog-up":
            row.update(dialogs=msg["dialogs"], dialog_waited_s=msg["waited_s"])
        elif stage == "reads":
            row["reads"] = msg["reads"]
        stage_t = time.monotonic()
    p.kill()
    p.wait()
    time.sleep(0.5)
    row["hung_dialogs"] = row.get("hung_dialogs") or []
    for pid in row["pids"]:
        if pid_alive(pid):
            kill_pid(pid)
            row.setdefault("killed_pids", []).append(pid)
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, f"{case}.json"), "w", encoding="utf-8") as f:
        f.write(redact(json.dumps(row, indent=1, default=str)))
    print(json.dumps({k: row.get(k) for k in ("case", "outcome", "seconds")}), flush=True)
    return row


def write_table():
    """Build the table from every saved case, so a run of one group does not drop the others."""
    lines = ["## Word probes: which calls hang", "",
             "Each case: a child process, stage limit 25 s, Word dialogs listed while a call is stuck, Word PIDs killed "
             "by PID only.", "",
             "| case | condition | call | outcome | seconds | Word dialogs while stuck |", "|---|---|---|---|---|---|"]
    for case in [c for g in GROUPS.values() for c in g]:
        path = os.path.join(RESULTS, f"{case}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            r = json.load(f)
        dl = "; ".join(f"{d['title']} ({d['cls']}): " + " / ".join(t for t in d["text"][:2] if t.startswith("Static"))
                       for d in r.get("hung_dialogs", [])) or "-"
        lines.append(f"| {r['case']} | {r['description']} | {r.get('call', '-')} | {r.get('outcome')} | "
                     f"{r.get('seconds', '-')} | {dl.replace('|', '/')} |")
    text = "\n".join(lines) + "\n"
    with open(os.path.join(RESULTS, "unit1-word-probes.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "child":
        child(sys.argv[2])
    elif cmd == "helper":
        helper(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "all" or cmd in GROUPS:
        for case in ([c for g in GROUPS.values() for c in g] if cmd == "all" else GROUPS[cmd]):
            parent(case)
        write_table()
    else:
        raise SystemExit(f"unknown command {cmd}")
