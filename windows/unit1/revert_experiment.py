"""Excel in-app commit with a recorded revert (gate G6).

One run: a visible Excel opens a copy of base/revert.xlsx. An optional user edit happens. The used range is
recorded (value, formula, number format, bold, fill, merged, and comment presence) before the agent's COM edit.
The agent edit is made in memory, without a save, and the used range is recorded again. The footprint is the set
of cells that differ between the two records. Then the user may edit (after the commit), and one revert runs.

A revert writes the recorded prior state of the footprint back through COM. It refuses when a footprint cell no
longer holds what the agent left, which is the same cell-level rule as the commit. Formula, merged, and comment
changes are not captured well enough for a guaranteed revert, so the first call only reports them. A second call
with confirm=True applies the write-back. The user then saves, and the disk file is read back.

  py -3 windows\\unit1\\revert_experiment.py fixture          write base/revert.xlsx
  py -3 windows\\unit1\\revert_experiment.py matrix           8 cases x 3 reps, results/revert/
  py -3 windows\\unit1\\revert_experiment.py run <case> <rep>
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile

import win32api
import win32com.client

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "unit2"))
sys.path.insert(0, HERE)

import xlsx_props as XP  # noqa: E402
from open_doc_experiment import scrub_author  # noqa: E402
from otx_win import (Watchdog, foreground_desc, free_mb, image_pids, kill_pid, new_image_pid,  # noqa: E402
                     pid_alive, wait_for_memory)

BASE = os.path.join(HERE, "base", "revert.xlsx")
WORK = os.path.join(HERE, "work", "revert")
RESULTS = os.path.join(HERE, "results", "revert")
MIN_FREE_MB = 350
XL_NONE = -4142
EMPTY = dict(value=None, formula=None, numfmt="General", bold=False, fill=None, merged=False)
USER_NOTE = "user note"
USER_B2 = 77

CASES = {
    "clean-value": dict(user="none", agent="value", expect="reverted"),
    "clean-format": dict(user="none", agent="format", expect="reverted"),
    "dirty-user-elsewhere": dict(user="before-D1", agent="value", expect="reverted"),
    "after-same-cell": dict(user="after-B2", agent="value", expect="refused"),
    "after-other-cell": dict(user="after-D1", agent="value", expect="reverted"),
    "formula": dict(user="none", agent="formula", expect="confirm"),
    "merged": dict(user="none", agent="merged", expect="confirm"),
    "comment": dict(user="none", agent="comment", expect="confirm"),
}


def _col(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _order(ref):
    m = re.fullmatch(r"([A-Z]+)(\d+)", ref)
    return int(m.group(2)), len(m.group(1)), m.group(1)


def cell_props(ws, ref):
    c = ws.Range(ref)
    return dict(value=c.Value, formula=c.Formula if c.HasFormula else None, numfmt=c.NumberFormat,
                bold=bool(c.Font.Bold), fill=None if c.Interior.Pattern == XL_NONE else c.Interior.Color,
                merged=bool(c.MergeCells))


def write_props(ws, ref, p):
    c = ws.Range(ref)
    if p["formula"] is not None:
        c.Formula = p["formula"]
    elif p["value"] is None:
        c.ClearContents()
    else:
        c.Value = p["value"]
    c.NumberFormat = p["numfmt"]
    c.Font.Bold = p["bold"]
    if p["fill"] is None:
        c.Interior.Pattern = XL_NONE
    else:
        c.Interior.Color = p["fill"]


def snapshot(ws):
    ur = ws.UsedRange
    refs = [f"{_col(c)}{r}" for r in range(ur.Row, ur.Row + ur.Rows.Count)
            for c in range(ur.Column, ur.Column + ur.Columns.Count)]
    cells = {ref: cell_props(ws, ref) for ref in refs}
    comments = sorted(f"{_col(cm.Parent.Column)}{cm.Parent.Row}"
                      for cm in (ws.Comments.Item(i) for i in range(1, ws.Comments.Count + 1)))
    return dict(used=str(ur.Address), cells=cells, comments=comments)


def cell_of(snap, ref):
    return snap["cells"].get(ref, EMPTY)


INPUT_KEYS = ("formula", "numfmt", "bold", "fill", "merged")


def same_state(now, want):
    """A formula cell is compared on its formula and format. Its value follows its precedents, so it is not compared."""
    keys = INPUT_KEYS if want["formula"] or now["formula"] else INPUT_KEYS + ("value",)
    return all(now[k] == want[k] for k in keys)


def make_plan(before, after):
    """The footprint is the cells the agent changed. Confirm reasons mark the changes a guaranteed revert cannot cover."""
    refs = sorted(set(before["cells"]) | set(after["cells"]), key=_order)
    changed = [r for r in refs if not same_state(cell_of(after, r), cell_of(before, r))]
    reasons = []
    for r in changed:
        b, a = cell_of(before, r), cell_of(after, r)
        if b["formula"] or a["formula"]:
            reasons.append(f"{r}: formula cell")
        if b["merged"] or a["merged"]:
            reasons.append(f"{r}: merged range")
    if before["comments"] != after["comments"]:
        reasons.append("comment added or removed, which the record does not capture")
    return dict(footprint=changed, prior={r: cell_of(before, r) for r in changed},
                committed={r: cell_of(after, r) for r in changed}, confirm_reasons=reasons)


def revert(ws, plan, confirm):
    conflicts = [r for r in plan["footprint"] if not same_state(cell_props(ws, r), plan["committed"][r])]
    if conflicts:
        return dict(status="refused", confirm=confirm, conflicts=conflicts, written=[])
    if plan["confirm_reasons"] and not confirm:
        return dict(status="confirm_required", confirm=confirm, conflicts=[], written=[])
    for r in plan["footprint"]:
        write_props(ws, r, plan["prior"][r])
    return dict(status="reverted", confirm=confirm, conflicts=[], written=list(plan["footprint"]))


def _set(ws, ref, value):
    ws.Range(ref).Value = value


AGENT = {
    "value": lambda ws: _set(ws, "B2", 5000),
    "format": lambda ws: (_set(ws, "B2", 5000), setattr(ws.Range("B2"), "NumberFormat", "$#,##0")),
    "formula": lambda ws: setattr(ws.Range("E2"), "Formula", "=B2*3"),
    "merged": lambda ws: _set(ws, "E5", "agent note"),
    "comment": lambda ws: (_set(ws, "B2", 5000), ws.Range("B2").AddComment("agent note")),
}
USER = {
    "none": lambda ws: None,
    "before-D1": lambda ws: _set(ws, "D1", USER_NOTE),
    "after-B2": lambda ws: _set(ws, "B2", USER_B2),
    "after-D1": lambda ws: _set(ws, "D1", USER_NOTE),
}


def fixture():
    """A small workbook: a number, a fill, a number format, a formula, and a merged range."""
    os.makedirs(os.path.dirname(BASE), exist_ok=True)
    before = image_pids("EXCEL.EXE")
    app = win32com.client.DispatchEx("Excel.Application")
    app.Visible = False
    app.DisplayAlerts = False
    pid = new_image_pid("EXCEL.EXE", before)
    try:
        wb = app.Workbooks.Add()
        ws = wb.Worksheets(1)
        ws.Name = "Budget"
        for ref, v in {"A1": "Item", "B1": "Amount", "A2": "Travel", "B2": 1000, "A3": "Food", "B3": 250}.items():
            ws.Range(ref).Value = v
        ws.Range("A1:B1").Font.Bold = True
        ws.Range("A3").Interior.Color = 65535
        ws.Range("B3").NumberFormat = "#,##0.00"
        ws.Range("E2").Formula = "=B2*2"
        ws.Range("E5").Value = "merged note"
        ws.Range("E5:F5").Merge()
        wb.SaveAs(os.path.abspath(BASE), 51)
        wb.Close(False)
    finally:
        app.Quit()
        time.sleep(1)
        if pid_alive(pid):
            kill_pid(pid)
    scrub_author(BASE)
    print("fixture written to", BASE)


def _norm_fmt(code):
    return code.replace("\\", "").replace('"', "")


def _fill_hex(color):
    if color is None:
        return None
    return f"{color & 0xFF:02X}{(color >> 8) & 0xFF:02X}{(color >> 16) & 0xFF:02X}"


def disk_matches(disk, ref, p):
    d = disk.get(ref, XP.EMPTY)
    formula = p["formula"].lstrip("=") if p["formula"] else None
    return (d["value"] == p["value"] and d["formula"] == formula and _norm_fmt(d["numfmt"]) == _norm_fmt(p["numfmt"])
            and d["bold"] == p["bold"] and d["merged"] == p["merged"] and d["fill"] == _fill_hex(p["fill"]))


def mem_matches(ws, targets):
    return all(cell_props(ws, r) == p for r, p in targets.items())


def _launch():
    before = image_pids("EXCEL.EXE")
    app = win32com.client.DispatchEx("Excel.Application")
    app.Visible = True
    app.DisplayAlerts = False
    return app, new_image_pid("EXCEL.EXE", before)


def run(case, rep):
    spec = CASES[case]
    name = f"{case}-r{rep}"
    d = os.path.join(WORK, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    path = os.path.join(d, "budget.xlsx")
    shutil.copy(BASE, path)
    rec = dict(run=name, case=case, rep=rep, expect=spec["expect"], status="ok", calls=[])
    t0 = time.time()
    app, pid, wd, wb = None, None, None, None
    try:
        rec["free_mb_before"] = free_mb()
        if not wait_for_memory(MIN_FREE_MB, 120):
            rec["status"] = f"skipped: free memory below {MIN_FREE_MB} MB"
            return rec
        app, pid = _launch()
        rec["pid"] = pid
        wd = Watchdog(pid)
        wd.start()
        wd.phase = "open"
        wb = app.Workbooks.Open(os.path.abspath(path))
        ws = wb.Worksheets("Budget")
        time.sleep(1)
        if spec["user"] == "before-D1":
            wd.phase = "user-edit"
            USER["before-D1"](ws)
        wd.phase = "snapshot-pre"
        before = snapshot(ws)
        wd.phase = "commit"
        rec["fg_before_commit"] = foreground_desc()
        AGENT[spec["agent"]](ws)
        after = snapshot(ws)
        rec["fg_after_commit"] = foreground_desc()
        plan = make_plan(before, after)
        rec["plan"] = dict(footprint=plan["footprint"], confirm_reasons=plan["confirm_reasons"],
                           prior={r: plan["prior"][r] for r in plan["footprint"]},
                           committed={r: plan["committed"][r] for r in plan["footprint"]})
        if spec["user"].startswith("after-"):
            wd.phase = "user-after-commit"
            USER[spec["user"]](ws)
        wd.phase = "revert"
        first = revert(ws, plan, confirm=False)
        rec["calls"].append(first)
        rec["mem_after_first_call"] = {r: cell_props(ws, r) for r in plan["footprint"]}
        if first["status"] == "confirm_required":
            wd.phase = "confirm"
            rec["calls"].append(revert(ws, plan, confirm=True))
        rec["mem_after_revert"] = {r: cell_props(ws, r) for r in plan["footprint"]}
        rec["mem_user"] = {k: cell_props(ws, k) for k in ("B2", "D1")}
        rec["comments_after_revert"] = snapshot(ws)["comments"]
        wd.phase = "save"
        wb.Save()
        time.sleep(1)
        disk = XP.read_props(path)["cells"]
        rec["disk"] = {r: disk.get(r, XP.EMPTY) for r in plan["footprint"] + ["B2", "D1"]}
        rec["disk_matches_prior"] = all(disk_matches(disk, r, plan["prior"][r]) for r in plan["footprint"])
        rec["disk_matches_committed"] = all(disk_matches(disk, r, plan["committed"][r]) for r in plan["footprint"])
        rec["verdict"] = judge(spec, rec)
    except Exception:
        rec["status"] = "error"
        rec["traceback"] = traceback.format_exc()[-1500:]
    finally:
        if wd is not None:
            wd.stop()
            rec["watch_counts"] = {f"{p}|{k}": n for (p, k), n in wd.counts.items()}
            rec["watch_events"] = wd.events[:60]
        try:
            if wb is not None:
                wb.Close(False)
            if app is not None:
                app.Quit()
        except Exception as e:
            rec["quit_error"] = repr(e)[:200]
        if pid is not None:
            time.sleep(1)
            if pid_alive(pid):
                kill_pid(pid)
                rec["killed_excel_pid"] = pid
        rec["seconds"] = round(time.time() - t0, 1)
        os.makedirs(RESULTS, exist_ok=True)
        with open(os.path.join(RESULTS, name + ".json"), "w") as f:
            f.write(redact(json.dumps(rec, indent=1, default=str)))
    return rec


HOME = os.path.expanduser("~")
PROFILE_NAMES = {os.path.basename(HOME), os.path.basename(win32api.GetShortPathName(HOME))}


def redact(text):
    """Window titles of other apps can show the profile path. The account name is not written to results."""
    for name in PROFILE_NAMES:
        text = re.sub(re.escape(name), "<user>", text, flags=re.IGNORECASE)
    return text


def judge(spec, rec):
    """Checks the outcome the case expects against the in-memory state and the disk file after the user's save."""
    calls = rec["calls"]
    final = calls[-1]["status"]
    user = spec["user"]
    user_ok = True
    if user in ("before-D1", "after-D1"):
        user_ok = rec["mem_user"]["D1"]["value"] == USER_NOTE and rec["disk"]["D1"]["value"] == USER_NOTE
    if user == "after-B2":
        user_ok = rec["mem_user"]["B2"]["value"] == USER_B2 and rec["disk"]["B2"]["value"] == USER_B2
    if spec["expect"] == "reverted":
        ok = len(calls) == 1 and final == "reverted" and rec["disk_matches_prior"] and not rec["comments_after_revert"]
    elif spec["expect"] == "refused":
        ok = len(calls) == 1 and final == "refused" and calls[0]["conflicts"] == ["B2"]
    else:
        ok = (len(calls) == 2 and calls[0]["status"] == "confirm_required" and not calls[0]["written"]
              and rec["mem_after_first_call"] == rec["plan"]["committed"]
              and final == "reverted" and rec["disk_matches_prior"])
    if ok and user_ok:
        return "CORRECT: " + {"reverted": "zero-click revert", "refused": "refused on conflict",
                              "confirm": "confirm needed, revert done on confirm"}[spec["expect"]]
    return "WRONG: " + json.dumps({"calls": calls, "disk_matches_prior": rec["disk_matches_prior"],
                                   "user_ok": user_ok})


def matrix():
    os.makedirs(RESULTS, exist_ok=True)
    for case in CASES:
        for rep in (1, 2, 3):
            print("running", case, rep, flush=True)
            try:
                subprocess.run([sys.executable, os.path.abspath(__file__), "run", case, str(rep)],
                               timeout=300, capture_output=True, text=True)
            except subprocess.TimeoutExpired:
                with open(os.path.join(RESULTS, f"{case}-r{rep}.json"), "w") as f:
                    json.dump({"run": f"{case}-r{rep}", "status": "timeout"}, f)
                print("  timeout", flush=True)
    report()


def _fg_changes(r):
    counts = r.get("watch_counts", {})
    return counts.get("revert|foreground", 0) + counts.get("confirm|foreground", 0)


def _state_label(r, where):
    """What the footprint holds: the recorded prior state, the agent's commit, the user's value, or something else."""
    plan = r["plan"]
    if where == "memory":
        state, prior_ok, committed_ok = r["mem_after_revert"], None, None
    else:
        state, prior_ok, committed_ok = None, r["disk_matches_prior"], r["disk_matches_committed"]
    if prior_ok or (state and all(state[k] == plan["prior"][k] for k in plan["footprint"])):
        return "prior"
    if committed_ok or (state and all(state[k] == plan["committed"][k] for k in plan["footprint"])):
        return "committed"
    b2 = r["mem_user"]["B2"]["value"] if where == "memory" else r["disk"]["B2"]["value"]
    if "B2" in plan["footprint"] and b2 == USER_B2:
        return f"user value ({USER_B2})"
    return "other"


def report():
    rows = []
    for p in sorted(glob.glob(os.path.join(RESULTS, "*-r*.json"))):
        with open(p) as f:
            rows.append(json.load(f))
    head = ["| case | rep | expected | revert calls | revert results | footprint | confirm reasons | "
            "in memory after revert | on disk after save | residue left by revert | foreground changes in revert | "
            "dialogs | verdict |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    lines = []
    for r in rows:
        if r.get("status") != "ok":
            lines.append(f"| {r.get('case')} | {r.get('rep')} | - | - | - | - | - | - | - | - | - | - | {r.get('status')} |")
            continue
        calls = r["calls"]
        results = " then ".join(c["status"] + (" (confirm)" if c["confirm"] else "") for c in calls)
        dialogs = sum(v for k, v in r.get("watch_counts", {}).items() if k.endswith("|dialog"))
        residue = "comment on " + ", ".join(r["comments_after_revert"]) if r["comments_after_revert"] else "none"
        lines.append(f"| {r['case']} | {r['rep']} | {r['expect']} | {len(calls)} | {results} | "
                     f"{', '.join(r['plan']['footprint'])} | {'; '.join(r['plan']['confirm_reasons']) or 'none'} | "
                     f"{_state_label(r, 'memory')} | {_state_label(r, 'disk')} | {residue} | "
                     f"{_fg_changes(r)} | {dialogs} | {r['verdict'].split(':')[0]} |")
    text = "## Revert per run\n\n" + "\n".join(head + lines) + "\n"
    out = os.path.join(RESULTS, "unit1-revert.md")
    with open(out, "w") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "fixture":
        fixture()
    elif cmd == "run":
        result = run(sys.argv[2], int(sys.argv[3]))
        print(json.dumps({"run": result.get("run"), "status": result.get("status"), "verdict": result.get("verdict")}))
    elif cmd == "matrix":
        matrix()
    elif cmd == "report":
        report()
