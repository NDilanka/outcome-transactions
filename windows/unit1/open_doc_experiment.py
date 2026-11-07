"""Unit 1: commit a new version of a file that Word or Excel has open, clean or with unsaved edits.

  python open_doc_experiment.py bases                      build base/budget.xlsx and base/budget.docx
  python open_doc_experiment.py run excel clean replace    one scenario in one process
  python open_doc_experiment.py matrix                     all scenarios, then results/unit1-results.md

Each scenario, with the app visible: open the base copy, optionally make a user edit without
saving, take a snapshot through the app (no change to the user's document), commit the agent's
edit with one method, read the result back through COM and through a copy, run an undo probe
(undo, then redo), then the user's save. The disk file is read after each step, so a commit the
app later overwrites shows up. A watchdog counts foreground changes, window changes and dialogs."""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile

import win32com.client

from otx_win import (Watchdog, docx_paras, flat_opc_paras, foreground_desc, force_foreground, free_mb,
                     image_pids, kill_pid, lock_info, new_image_pid, pid_alive, rm_holders,
                     wait_for_memory, xlsx_cells)

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "base")
WORK = os.path.join(HERE, "work")
RESULTS = os.path.join(HERE, "results")
MIN_FREE_MB = 350

XLSX_OTHERS = {"A1": "Item", "B1": "Amount", "A2": "Travel", "A3": "Food", "B3": 250.0}
DOCX_OTHERS = ["Budget report", "Food: 250"]

MATRIX = {
    "clean": ["replace", "sibling-rename", "inplace", "reload-after-replace", "close-replace-reopen",
              "live-com", "live-com-quiet", "live-com-quiet-focused", "control-focused"],
    "dirty": ["replace", "sibling-rename", "inplace", "live-com", "live-com-quiet", "live-com-focused",
              "live-com-quiet-focused", "control-focused"],
}
APPS = ["excel", "word"]


def xlsx_state(path):
    cells = xlsx_cells(path)
    return {
        "agent": cells.get("B2") == 5000.0,
        "user": cells.get("D1") == "user note",
        "others_ok": all(cells.get(k) == v for k, v in XLSX_OTHERS.items()) and set(cells) <= set(XLSX_OTHERS) | {"B2", "D1"},
    }


def docx_state_from_paras(paras):
    rest = [p for p in paras if p not in ("Total: 5000", "Total: 1000", "User note")]
    return {
        "agent": "Total: 5000" in paras,
        "user": "User note" in paras,
        "others_ok": rest == DOCX_OTHERS,
    }


def read_state(ext, path):
    if ext == "xlsx":
        return xlsx_state(path)
    return docx_state_from_paras(docx_paras(path))


def agent_bytes(ext, path):
    """The agent's edit as a file-level rewrite of the disk file: B2 1000 -> 5000, or the Total paragraph."""
    with open(path, "rb") as f:
        data = f.read()
    if ext == "xlsx":
        buf = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                body = zin.read(info.filename)
                if info.filename == "xl/worksheets/sheet1.xml":
                    text, n = re.subn(rb'(<c r="B2"[^>]*>\s*<v>)1000(</v>)', rb"\g<1>5000\2", body)
                    assert n == 1, "B2 not found in sheet1.xml"
                    body = text
                zout.writestr(info.filename, body)
        return buf.getvalue()
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            body = zin.read(info.filename)
            if info.filename == "word/document.xml":
                assert body.count(b"Total: 1000") == 1, "Total paragraph not found in document.xml"
                body = body.replace(b"Total: 1000", b"Total: 5000")
            zout.writestr(info.filename, body)
    return buf.getvalue()


def commit_file(method, path, new):
    """Transplant new bytes onto the file while the app may have it open."""
    rec = {"method": method, "steps": [], "write_ok": False, "error": None}
    tmp = path + ".otx-tmp"
    try:
        if method == "inplace":
            with open(path, "r+b") as f:
                f.write(new)
                f.truncate()
            rec["steps"].append("in-place overwrite ok")
        else:
            with open(tmp, "wb") as f:
                f.write(new)
            if method == "sibling-rename":
                os.remove(path)
                rec["steps"].append("remove target ok")
                os.rename(tmp, path)
                rec["steps"].append("rename sibling into place ok")
            else:
                os.replace(tmp, path)
                rec["steps"].append("os.replace ok")
        rec["write_ok"] = True
    except OSError as e:
        rec["error"] = f"{type(e).__name__} winerror={getattr(e, 'winerror', None)}: {e.strerror}"
        rec["steps"].append("FAILED: " + rec["error"])
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return rec


def undo_probe(adapter):
    """One undo, then one redo. Shows what the user's undo stack holds: the agent's edit, the
    user's edit, or nothing. The redo must put the document back exactly as it was."""
    before = adapter.mem_state()
    rec = {"before": before, "activated_for_probe": False}
    try:
        adapter.undo()
        rec["undo_error"] = None
    except Exception as e:
        rec["undo_first_error"] = repr(e)[:200]
        adapter.activate()
        rec["activated_for_probe"] = True
        try:
            adapter.undo()
            rec["undo_error"] = None
        except Exception as e2:
            rec["undo_error"] = repr(e2)[:200]
            return rec
    after_undo = adapter.mem_state()
    rec["reverted"] = [k for k in before if before[k] != after_undo[k]]
    try:
        adapter.redo()
        rec["redo_error"] = None
    except Exception as e:
        rec["redo_error"] = repr(e)[:200]
    rec["restored_after_redo"] = adapter.mem_state() == before
    return rec


def snapshot_step(adapter, d, stage, ext):
    """Copy the live document without changing it: name, dirty flag and user state must not move."""
    path = os.path.join(d, f"snap-{stage}." + ("xml" if ext == "docx" else "xlsx"))
    rec = {"saved_before": adapter.saved(), "fullname_before": adapter.fullname()}
    try:
        rec["state"] = adapter.snapshot(path)
        rec["error"] = None
    except Exception as e:
        rec["state"] = None
        rec["error"] = repr(e)[:200]
    rec["saved_after"] = adapter.saved()
    rec["fullname_after"] = adapter.fullname()
    rec["mem_after"] = adapter.mem_state()
    return rec


class _Office:
    prog = None
    ext = None
    image = None

    def launch(self):
        before = image_pids(self.image)
        self.app = win32com.client.DispatchEx(self.prog)
        self.app.Visible = True
        self.pid = new_image_pid(self.image, before)
        self.version = f"{self.app.Name} {self.app.Version} build {self.app.Build}"


class Excel(_Office):
    prog, ext, image = "Excel.Application", "xlsx", "EXCEL.EXE"

    def open(self, path):
        self.path = path
        self.wb = self.app.Workbooks.Open(path, 0, False)
        self.ws = self.wb.Worksheets("Budget")

    def saved(self):
        return bool(self.wb.Saved)

    def fullname(self):
        return self.wb.FullName

    def activate(self):
        self.wb.Windows(1).Activate()
        self.focus_ok = force_foreground(self.wb.Windows(1).Hwnd)

    def user_edit(self):
        self.ws.Range("D1").Value = "user note"

    def live_agent(self, quiet=False):
        if quiet:
            self.app.ScreenUpdating = False
        try:
            self.ws.Range("B2").Value = 5000
        finally:
            if quiet:
                self.app.ScreenUpdating = True

    def mem_state(self):
        r = self.wb.Worksheets("Budget").Range
        cells = {k: r(k).Value for k in ("A1", "B1", "A2", "B2", "A3", "B3", "D1")}
        agent = cells["B2"] == 5000.0
        user = cells["D1"] == "user note"
        others = all(cells[k] == v for k, v in XLSX_OTHERS.items())
        return {"agent": agent, "user": user, "others_ok": others}

    def snapshot(self, path):
        self.wb.SaveCopyAs(os.path.abspath(path))
        return xlsx_state(path)

    def undo(self):
        self._send_keys("^z")

    def redo(self):
        self._send_keys("^y")

    def _send_keys(self, keys):
        if foreground_desc()["pid"] != self.pid:
            raise RuntimeError("Excel is not the foreground window")
        win32com.client.Dispatch("WScript.Shell").SendKeys(keys)
        time.sleep(0.5)

    def save(self):
        self.wb.Save()

    def reload(self):
        self.wb.Close(False)
        self.open(self.path)

    def close_doc(self):
        try:
            self.wb.Close(False)
        except Exception as e:
            print("close_doc:", repr(e), file=sys.stderr)

    def quit(self):
        self.app.Quit()


class Word(_Office):
    prog, ext, image = "Word.Application", "docx", "WINWORD.EXE"

    def open(self, path):
        self.path = path
        self.doc = self.app.Documents.Open(path, False, False, False)

    def saved(self):
        return bool(self.doc.Saved)

    def fullname(self):
        return self.doc.FullName

    def activate(self):
        self.doc.Activate()
        self.focus_ok = force_foreground(self.doc.ActiveWindow.Hwnd)

    def user_edit(self):
        end = self.doc.Content.End - 1
        self.doc.Range(end, end).InsertAfter("\rUser note")

    def live_agent(self, quiet=False):
        if quiet:
            self.app.ScreenUpdating = False
        try:
            r = self.doc.Paragraphs(2).Range
            r.MoveEnd(1, -1)
            r.Text = "Total: 5000"
        finally:
            if quiet:
                self.app.ScreenUpdating = True

    def mem_state(self):
        paras = [self.doc.Paragraphs(i).Range.Text.rstrip("\r\x07") for i in range(1, self.doc.Paragraphs.Count + 1)]
        return docx_state_from_paras(paras)

    def snapshot(self, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.doc.WordOpenXML)
        return docx_state_from_paras(flat_opc_paras(path))

    def undo(self):
        self.doc.Undo(1)

    def redo(self):
        self.doc.Redo(1)

    def save(self):
        self.doc.Save()

    def reload(self):
        self.doc.Close(0)
        self.open(self.path)

    def close_doc(self):
        try:
            self.doc.Close(0)
        except Exception as e:
            print("close_doc:", repr(e), file=sys.stderr)

    def quit(self):
        self.app.Quit()


ADAPTERS = {"excel": Excel, "word": Word}


def run(app_name, state, method):
    adapter = ADAPTERS[app_name]()
    ext = adapter.ext
    name = f"{app_name}-{state}-{method}"
    d = os.path.join(WORK, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    doc = os.path.join(d, f"budget.{ext}")
    shutil.copy(os.path.join(BASE, f"budget.{ext}"), doc)
    rec = {"run": name, "app": app_name, "state": state, "method": method, "status": "ok"}
    t0 = time.time()
    wd = None
    try:
        rec["free_mb_before"] = free_mb()
        if not wait_for_memory(MIN_FREE_MB, 120):
            rec["status"] = f"skipped: free memory below {MIN_FREE_MB} MB"
            return rec
        rec["holders_before_open"] = rm_holders(doc)
        rec["lock_before_open"] = lock_info(doc)

        adapter.launch()
        rec["office"] = adapter.version
        rec["pid"] = adapter.pid
        with open(os.path.join(d, "pid.txt"), "w") as f:
            f.write(str(adapter.pid))
        wd = Watchdog(adapter.pid)
        wd.start()

        wd.phase = "open"
        adapter.open(doc)
        time.sleep(1)
        rec["holders_open"] = rm_holders(doc)
        rec["lock_open"] = lock_info(doc)
        rec["saved_open"] = adapter.saved()
        rec["mem_open"] = adapter.mem_state()

        if state == "dirty":
            wd.phase = "user-edit"
            adapter.user_edit()
            rec["saved_after_user_edit"] = adapter.saved()
            rec["mem_after_user_edit"] = adapter.mem_state()

        wd.phase = "snapshot-pre"
        rec["snapshot_pre"] = snapshot_step(adapter, d, "pre", ext)
        time.sleep(0.5)

        base = method.replace("-focused", "")
        if method.endswith("-focused"):
            wd.phase = "focus"
            adapter.activate()
            time.sleep(0.5)
            rec["focus_ok"] = getattr(adapter, "focus_ok", None)
        wd.phase = "commit"
        rec["fg_before_commit"] = foreground_desc()
        if base in ("live-com", "live-com-quiet"):
            adapter.live_agent(quiet=(base == "live-com-quiet"))
            commit = {"method": method, "steps": ["in-app COM edit, no save, no activation"],
                      "write_ok": True, "error": None}
        elif base == "control":
            commit = {"method": method, "steps": ["control: no commit, same waits"], "write_ok": True, "error": None}
        elif method == "reload-after-replace":
            commit = commit_file("replace", doc, agent_bytes(ext, doc))
            adapter.reload()
            commit["steps"].append("app reloaded after transplant")
        elif method == "close-replace-reopen":
            adapter.close_doc()
            commit = commit_file("replace", doc, agent_bytes(ext, doc))
            adapter.open(doc)
            commit["steps"].append("app closed, transplant, app reopened")
        else:
            commit = commit_file(method, doc, agent_bytes(ext, doc))
        rec["commit"] = commit
        time.sleep(2)
        rec["fg_after_commit"] = foreground_desc()
        rec["mem_after_commit"] = adapter.mem_state()
        rec["saved_after_commit"] = adapter.saved()
        rec["disk_after_commit"] = read_state(ext, doc)
        rec["holders_after_commit"] = rm_holders(doc)
        rec["lock_after_commit"] = lock_info(doc)

        wd.phase = "verify"
        rec["snapshot_post"] = snapshot_step(adapter, d, "post", ext)

        wd.phase = "user-save"
        try:
            adapter.save()
            rec["save_error"] = None
        except Exception as e:
            rec["save_error"] = repr(e)[:300]
        time.sleep(1)
        rec["mem_after_save"] = adapter.mem_state()
        rec["disk_after_save"] = read_state(ext, doc)
        rec["holders_after_save"] = rm_holders(doc)
        rec["verdict"] = verdict(rec)

        wd.phase = "probe"
        try:
            rec["undo_probe"] = undo_probe(adapter)
        except Exception as e:
            rec["undo_probe"] = {"probe_error": repr(e)[:200]}
    except Exception:
        rec["status"] = "error"
        rec["traceback"] = traceback.format_exc()[-1500:]
    finally:
        if wd is not None:
            wd.stop()
            rec["watch_counts"] = {f"{p}|{k}": n for (p, k), n in wd.counts.items()}
            rec["watch_events"] = wd.events
        try:
            adapter.close_doc()
            adapter.quit()
            rec["quit_ok"] = True
        except Exception as e:
            rec["quit_ok"] = False
            rec["quit_error"] = repr(e)[:200]
        if hasattr(adapter, "pid"):
            time.sleep(1)
            if pid_alive(adapter.pid):
                kill_pid(adapter.pid)
                rec["killed_office_pid"] = adapter.pid
        rec["holders_after_close"] = rm_holders(doc)
        rec["lock_after_close"] = lock_info(doc)
        rec["seconds"] = round(time.time() - t0, 1)
        os.makedirs(RESULTS, exist_ok=True)
        with open(os.path.join(RESULTS, name + ".json"), "w") as f:
            json.dump(rec, f, indent=1, default=str)
    return rec


def verdict(rec):
    if rec["method"].startswith("control"):
        return "CONTROL: no commit, measures focus drift only"
    dirty = rec["state"] == "dirty"
    final = rec["disk_after_save"]
    commit = rec["commit"]
    if final["agent"] and final["others_ok"] and (final["user"] or not dirty):
        return "PASS: disk correct after the user's save"
    if not commit["write_ok"]:
        return "REFUSED: write failed, nothing committed"
    if rec["disk_after_commit"]["agent"] and not final["agent"]:
        return "LOST: commit on disk, then the app's save overwrote it"
    if not final["agent"]:
        return "LOST: commit never reached disk"
    if dirty and not final["user"]:
        return "USER EDITS LOST"
    return "CHECK: " + json.dumps({"final": final})


def scrub_author(path):
    """Office writes the Windows account name into docProps/core.xml. Fixtures get a neutral author instead."""
    tmp = path + ".tmp"
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "docProps/core.xml":
                text = data.decode("utf-8")
                text = re.sub(r"(<dc:creator>).*?(</dc:creator>)", r"\g<1>fixture\g<2>", text)
                text = re.sub(r"(<cp:lastModifiedBy>).*?(</cp:lastModifiedBy>)", r"\g<1>fixture\g<2>", text)
                data = text.encode("utf-8")
            dst.writestr(info, data)
    os.replace(tmp, path)


def bases():
    os.makedirs(BASE, exist_ok=True)
    before = image_pids("EXCEL.EXE")
    xl = win32com.client.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    pid = new_image_pid("EXCEL.EXE", before)
    try:
        wb = xl.Workbooks.Add()
        ws = wb.Worksheets(1)
        ws.Name = "Budget"
        ws.Range("A1").Value = "Item"
        ws.Range("B1").Value = "Amount"
        ws.Range("A2").Value = "Travel"
        ws.Range("B2").Value = 1000
        ws.Range("A3").Value = "Food"
        ws.Range("B3").Value = 250
        wb.SaveAs(os.path.abspath(os.path.join(BASE, "budget.xlsx")), 51)
        wb.Close(False)
    finally:
        xl.Quit()
        time.sleep(1)
        if pid_alive(pid):
            kill_pid(pid)
    before = image_pids("WINWORD.EXE")
    wd_app = win32com.client.DispatchEx("Word.Application")
    wd_app.Visible = False
    wd_app.DisplayAlerts = 0
    pid = new_image_pid("WINWORD.EXE", before)
    try:
        doc = wd_app.Documents.Add()
        doc.Content.Text = "Budget report\rTotal: 1000\rFood: 250"
        doc.SaveAs2(os.path.abspath(os.path.join(BASE, "budget.docx")), 16)
        doc.Close(0)
    finally:
        wd_app.Quit()
        time.sleep(1)
        if pid_alive(pid):
            kill_pid(pid)
    for name in ("budget.xlsx", "budget.docx"):
        scrub_author(os.path.join(BASE, name))
    print("bases written to", BASE)


def matrix():
    os.makedirs(RESULTS, exist_ok=True)
    for app in APPS:
        for state, methods in MATRIX.items():
            for method in methods:
                name = f"{app}-{state}-{method}"
                print("running", name, flush=True)
                try:
                    subprocess.run([sys.executable, os.path.abspath(__file__), "run", app, state, method],
                                   timeout=300, capture_output=True, text=True)
                except subprocess.TimeoutExpired:
                    pid_file = os.path.join(WORK, name, "pid.txt")
                    if os.path.exists(pid_file):
                        kill_pid(int(open(pid_file).read()))
                    with open(os.path.join(RESULTS, name + ".json"), "w") as f:
                        json.dump({"run": name, "status": "timeout"}, f)
                    print("  timeout", flush=True)
    report()


def _dialog_text(r):
    return "; ".join(f"{e['phase']}: {e.get('title') or e.get('class')}" for e in r.get("watch_events", [])
                     if e["kind"] == "dialog") or "none"


def _count(r, phase, kind):
    return r.get("watch_counts", {}).get(f"{phase}|{kind}", 0)


def report():
    import glob
    rows = []
    for p in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        if os.path.basename(p).startswith("unit1-"):
            continue
        with open(p) as f:
            rows.append(json.load(f))
    yn = lambda b: "yes" if b else "no"
    main = [
        "| app | state | method | write ok | app shows commit before save | disk after commit | disk after user save | user edit kept | copy after commit correct | focus changes in commit | window changes in commit | undo first reverts | dialogs | verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    snap = [
        "| app | state | snapshot ok | user edit in snapshot | dirty flag unchanged | name unchanged | snapshot state correct | undo probe restored after redo |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r.get("status") != "ok":
            main.append(f"| {r.get('app')} | {r.get('state')} | {r.get('method')} | - | - | - | - | - | - | - | - | - | - | {r.get('status')} |")
            continue
        c = r["commit"]
        dirty = r["state"] == "dirty"
        cp = r["snapshot_post"]["state"] or {"agent": False, "user": False, "others_ok": False}
        copy_ok = cp["agent"] and cp["others_ok"] and (cp["user"] or not dirty)
        probe = r["undo_probe"]
        if "probe_error" in probe:
            reverted = "probe error"
        elif probe.get("undo_error") is not None:
            reverted = "undo error"
        else:
            reverted = ", ".join(probe.get("reverted", [])) or "nothing"
        main.append(
            f"| {r['app']} | {r['state']} | {r['method']} | {yn(c['write_ok']) if c['write_ok'] else 'no: ' + str(c['error'])} | "
            f"{yn(r['mem_after_commit']['agent'])} | {'new' if r['disk_after_commit']['agent'] else 'old'} | "
            f"{'new' if r['disk_after_save']['agent'] else 'old'} | "
            f"{(yn(r['disk_after_save']['user']) if dirty else 'n/a')} | {yn(copy_ok)} | "
            f"{_count(r, 'commit', 'foreground')} | {_count(r, 'commit', 'window-appeared') + _count(r, 'commit', 'window-gone')} | "
            f"{reverted} | {_dialog_text(r)} | {r['verdict']} |")
        sp = r["snapshot_pre"]
        snap.append(
            f"| {r['app']} | {r['state']} | {yn(sp['error'] is None)} | "
            f"{(yn(sp['state']['user']) if sp['state'] else 'n/a') if dirty else 'n/a'} | "
            f"{yn(sp['saved_before'] == sp['saved_after'])} | {yn(sp['fullname_before'] == sp['fullname_after'])} | "
            f"{yn(sp['state'] is not None and sp['state']['others_ok'] and not sp['state']['agent'])} | "
            f"{yn(r['undo_probe'].get('restored_after_redo'))} |")
    out = os.path.join(RESULTS, "unit1-results.md")
    text = ("## Commit and verdict per run\n\n" + "\n".join(main) +
            "\n\n## Snapshot through the owner (before the commit)\n\n" + "\n".join(snap) + "\n")
    with open(out, "w") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "bases":
        bases()
    elif cmd == "run":
        run(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "matrix":
        matrix()
    elif cmd == "report":
        report()
