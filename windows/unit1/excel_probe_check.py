"""Checks two measurement tools before trusting Unit 1 numbers.

1. Undo route: can an Excel COM edit on a dirty, focused workbook be undone by a script, and does
   the undo revert only the agent's edit? Tries CommandBars.FindControl(Id=128) and ExecuteMso.
2. Dialog detector: does the Watchdog record a real Excel dialog? A SaveAs over an existing file
   with alerts on raises the "replace?" prompt. The Watchdog must record it and close it.

Run: py -3 excel_probe_check.py   (launches one Excel instance, closes it)
"""
import os
import shutil
import time

import win32com.client

from otx_win import Watchdog, force_foreground, image_pids, kill_pid, new_image_pid, pid_alive

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "work", "excel-probe-check")


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    doc = os.path.join(WORK, "budget.xlsx")
    other = os.path.join(WORK, "other.xlsx")
    shutil.copy(os.path.join(HERE, "base", "budget.xlsx"), doc)
    shutil.copy(os.path.join(HERE, "base", "budget.xlsx"), other)

    before = image_pids("EXCEL.EXE")
    app = win32com.client.DispatchEx("Excel.Application")
    app.Visible = True
    pid = new_image_pid("EXCEL.EXE", before)
    wd = Watchdog(pid)
    wd.start()
    out = {}
    try:
        wb = app.Workbooks.Open(doc, 0, False)
        ws = wb.Worksheets("Budget")
        ws.Range("D1").Value = "user note"
        ws.Range("B2").Value = 5000
        out["saved_dirty"] = bool(wb.Saved)
        wb.Windows(1).Activate()
        out["focus_ok"] = force_foreground(wb.Windows(1).Hwnd)
        time.sleep(0.5)

        shell = win32com.client.Dispatch("WScript.Shell")

        def ctrl_z():
            from otx_win import foreground_desc
            if foreground_desc()["pid"] != pid:
                raise RuntimeError("Excel is not foreground, Ctrl+Z not sent")
            shell.SendKeys("^z")

        for name, call in (
            ("findcontrol128", lambda: app.CommandBars.FindControl(Id=128).Execute()),
            ("execmso_undo", lambda: app.CommandBars.ExecuteMso("Undo")),
            ("sendkeys_ctrl_z", ctrl_z),
        ):
            try:
                call()
                out[name] = "ok"
            except Exception as e:
                out[name] = repr(e)[:160]
            out[name + "_B2_after"] = ws.Range("B2").Value
            out[name + "_D1_after"] = ws.Range("D1").Value
            if out[name + "_B2_after"] == 1000.0:
                break

        ws.Range("E1").Select()
        shell.SendKeys("ui edit{ENTER}")
        time.sleep(0.5)
        out["ui_typed_E1"] = ws.Range("E1").Value
        shell.SendKeys("^z")
        time.sleep(0.5)
        out["ui_typed_E1_after_ctrl_z"] = ws.Range("E1").Value
        out["ui_edit_undone_by_ctrl_z"] = ws.Range("E1").Value is None

        wd.phase = "dialog"
        app.DisplayAlerts = True
        try:
            wb.SaveAs(other, 51)
            out["saveas_dialog_raised"] = False
        except Exception as e:
            out["saveas_dialog_raised"] = repr(e)[:160]
        time.sleep(1)
        wb.Close(False)
    finally:
        out["dialog_events"] = [e.get("title") or e.get("class") for e in wd.events if e["kind"] == "dialog"]
        wd.stop()
        try:
            app.Quit()
        except Exception:
            pass
        time.sleep(1)
        if pid_alive(pid):
            kill_pid(pid)
    for k, v in out.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
