"""Guards that keep the harness away from the user's own Office session.

Rules the Office harnesses follow:
- Office is driven only through an instance the harness started with DispatchEx. The instance's PID comes from its
  own window (Application.Hwnd), and it must be a process that was not running before the launch.
- Quit is called only on such an instance. A force-kill is taskkill by that PID, never by image name.
- Every other process of the same image is left alone. Before and after a check, the foreign processes are listed. A
  foreign process that exits during the check stops the check; one that starts during it is named and not touched.
- If a user session is named (OTX_USER_OFFICE_PID, optional), its state is read before and after a check, and a change
  stops the check.

The user session is named by environment variables, so no account or document name is written to tracked files:
  OTX_USER_OFFICE_PID   the user's Office PID (optional)
  OTX_USER_OFFICE_DOC   the full path of the user's document in that session (optional)

  py -3 windows\\unit1\\office_guard.py status                print the named user session state (read-only)
  py -3 windows\\unit1\\office_guard.py instance-check Word   start a separate instance, check the rules, quit it
  py -3 windows\\unit1\\office_guard.py instance-check Excel
"""
import os
import subprocess
import sys
import time

import pythoncom
import win32com.client
import win32process

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PROGS = {"Word": ("Word.Application", "WINWORD.EXE", "docx"), "Excel": ("Excel.Application", "EXCEL.EXE", "xlsx")}


class GuardError(RuntimeError):
    pass


def pid_alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


def own_pid(hwnd, before):
    """The PID of the instance the harness just started, read from a window that instance owns: Excel's Application
    window, or a document window for Word (Word's Application has no Hwnd). The PID must be new, and not one running
    before the launch: a PID taken from a process diff could be another user's instance."""
    pid = win32process.GetWindowThreadProcessId(hwnd)[1]
    if pid in before:
        raise GuardError(f"the launched instance has PID {pid}, which was running before the launch")
    user = user_pid()
    if user is not None and pid == user:
        raise GuardError("the launched instance is the user's session")
    return pid


def user_pid():
    value = os.environ.get("OTX_USER_OFFICE_PID")
    return int(value) if value else None


def user_session():
    """Read-only state of the named user session: alive, doc_open, and the document's Saved flag. None when not named."""
    pid = user_pid()
    if pid is None:
        return None
    state = dict(pid=pid, alive=pid_alive(pid), doc_open=None, saved=None)
    doc = os.environ.get("OTX_USER_OFFICE_DOC")
    if state["alive"] and doc:
        pythoncom.CoInitialize()
        try:
            d = win32com.client.GetObject(os.path.abspath(doc))  # binds to the running document; reads Saved only
            state.update(doc_open=True, saved=bool(d.Saved))
        except Exception as e:
            state.update(doc_open=False, error=type(e).__name__)
        finally:
            pythoncom.CoUninitialize()
    return state


def assert_user_unchanged(before, after):
    """Raise GuardError if the user's session changed between two snapshots (PID gone, or Saved flipped)."""
    if before is None or after is None:
        return
    if before["alive"] and not after["alive"]:
        raise GuardError(f"the user's session (PID {before['pid']}) exited during the run")
    if before.get("saved") is not None and after.get("saved") != before.get("saved"):
        raise GuardError(f"the user's document Saved flag changed from {before['saved']} to {after.get('saved')}")


def instance_check(which):
    """Starts a separate instance, opens a harness copy, checks the PID rules, closes the copy, and quits only the
    instance this check started. Foreign processes of the same image are snapshotted before and after and never
    touched. Touches only files under work/office-guard/."""
    import shutil
    prog, image, ext = PROGS[which]
    here_work = os.path.join(HERE, "work", "office-guard")
    os.makedirs(here_work, exist_ok=True)
    base = os.path.join(HERE, "base", f"budget.{ext}")
    doc = os.path.join(here_work, f"budget.{ext}")
    shutil.copy(base, doc)
    pythoncom.CoInitialize()
    before_pids = set(_image_pids(image))
    before_user = user_session()
    app = win32com.client.DispatchEx(prog)
    app.Visible = False
    pid = None
    checks = [f"foreign {image} PIDs before the check: {sorted(before_pids)}"]
    try:
        if which == "Word":
            probe = app.Documents.Add()  # Word's Application has no Hwnd: the PID comes from this blank document's window
            pid = own_pid(probe.ActiveWindow.Hwnd, before_pids)
            probe.Close(0)
            wb = app.Documents.Open(os.path.abspath(doc), False, False, False)
        else:
            pid = own_pid(app.Hwnd, before_pids)
            wb = app.Workbooks.Open(os.path.abspath(doc), 0, False)
        checks.append(f"own instance PID {pid}: new, not running before the check")
        checks.append(f"opened the harness copy in PID {pid}")
        wb.Close(False)
        checks.append("closed the harness copy without saving")
        app.Quit()
        app = None
        checks.append("quit the instance this check started")
    finally:
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()
        if pid is not None:
            t0 = time.monotonic()
            while pid_alive(pid) and time.monotonic() - t0 < 5:
                time.sleep(0.2)
            if pid_alive(pid):
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
                checks.append(f"PID {pid} still alive 5 s after quit: force-killed by that PID")
            else:
                checks.append(f"PID {pid} exited after quit")
    after_pids = set(_image_pids(image))
    gone = sorted(before_pids - after_pids)
    named = sorted(after_pids - before_pids - {pid})
    checks.append(f"foreign {image} PIDs after the check: {sorted(after_pids - {pid})}")
    if named:
        checks.append(f"foreign {image} PIDs that started during the check (left alone, not the harness's): {named}")
    after_user = user_session()
    assert_user_unchanged(before_user, after_user)
    if before_user is not None:
        checks.append(f"named user session before {before_user} after {after_user}: unchanged")
    for c in checks:
        print(c)
    if gone:
        raise GuardError(f"foreign {image} PIDs exited during the check: {gone}")
    print(f"no foreign {image} process exited during the check")


def _image_pids(image):
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    pids = set()
    for line in out.splitlines():
        parts = line.strip('"').split('","')
        if len(parts) > 1 and parts[1].isdigit():
            pids.add(int(parts[1]))
    return pids


if __name__ == "__main__":
    if sys.argv[1] == "status":
        print(user_session())
    elif sys.argv[1] == "instance-check":
        instance_check(sys.argv[2])
    else:
        raise SystemExit(f"unknown command {sys.argv[1]}")
