"""Run-to-run variance for the Unit 1 open-document matrix.

Reruns every cell whose verdict in results/ starts with PASS or REFUSED, three times. Each rep writes to its own
folder under results/variance/. Each run is a fresh process, one Office app at a time, as in the matrix.

  py -3 windows\\unit1\\variance_runs.py      3 reps x (16 PASS + 14 REFUSED) = 90 runs
"""
import glob
import json
import os
import subprocess
import sys

from otx_win import redact

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "results")
VAR = os.path.join(MAIN, "variance")
OPEN_DOC = os.path.join(HERE, "open_doc_experiment.py")
REPS = 3
EXPECTED = {"PASS": 16, "REFUSED": 14}


def _label(r):
    """Verdict of one run. A run that errored has no verdict, so its status is shown instead."""
    if r is None:
        return "missing"
    if r.get("verdict"):
        return r["verdict"].split(":")[0]
    return f"status {r.get('status')}"


def main_cells():
    cells = {kind: [] for kind in EXPECTED}
    for p in sorted(glob.glob(os.path.join(MAIN, "*.json"))):
        if os.path.basename(p).startswith("unit1-"):
            continue
        with open(p) as f:
            r = json.load(f)
        verdict = r.get("verdict") or ""
        for kind in EXPECTED:
            if verdict.startswith(kind):
                cells[kind].append((r["app"], r["state"], r["method"]))
    return cells


def run_cells(cells):
    for rep in range(1, REPS + 1):
        rdir = os.path.join(VAR, f"rep{rep}")
        env = dict(os.environ, OTX_RESULTS=rdir, OTX_WORK=os.path.join(HERE, "work", "variance", f"rep{rep}"))
        os.makedirs(rdir, exist_ok=True)
        for kind in EXPECTED:
            for app, state, method in cells[kind]:
                print("rep", rep, kind, app, state, method, flush=True)
                try:
                    res = subprocess.run([sys.executable, OPEN_DOC, "run", app, state, method],
                                         env=env, timeout=300, capture_output=True, text=True)
                    if res.stderr.strip():
                        with open(os.path.join(rdir, f"{app}-{state}-{method}.stderr.txt"), "w",
                                  encoding="utf-8") as f:
                            f.write(redact(res.stderr))
                except subprocess.TimeoutExpired:
                    pid_file = os.path.join(env["OTX_WORK"], f"{app}-{state}-{method}", "pid.txt")
                    if os.path.exists(pid_file):
                        subprocess.run(["taskkill", "/PID", open(pid_file).read().strip(), "/T", "/F"],
                                       capture_output=True)
                    print("  timeout", flush=True)
        subprocess.run([sys.executable, OPEN_DOC, "report"], env=env, capture_output=True, text=True)


def _load(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def summarize(cells):
    head = ["| app | state | method | main verdict | rep 1 | rep 2 | rep 3 | stable | "
            "foreground changes in commit (reps 1, 2, 3) | dialogs (reps 1, 2, 3) |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    lines, unstable, fg_runs = [], [], []
    total = 0
    for kind in EXPECTED:
        for app, state, method in cells[kind]:
            name = f"{app}-{state}-{method}"
            reps = [_load(os.path.join(VAR, f"rep{rep}", name + ".json")) for rep in range(1, REPS + 1)]
            verdicts = [_label(r) for r in reps]
            fg = [(r or {}).get("watch_counts", {}).get("commit|foreground", 0) for r in reps]
            dialogs = [sum(v for k, v in (r or {}).get("watch_counts", {}).items() if k.endswith("|dialog"))
                       for r in reps]
            total += len(reps)
            stable = len(set(verdicts)) == 1 and verdicts[0] == kind
            if not stable:
                unstable.append(name)
            for rep, n in enumerate(fg, 1):
                if n:
                    fg_runs.append(f"{name} rep {rep}: {n}")
            lines.append(f"| {app} | {state} | {method} | {kind} | {verdicts[0]} | {verdicts[1]} | {verdicts[2]} | "
                         f"{'yes' if stable else 'no'} | {fg[0]}, {fg[1]}, {fg[2]} | "
                         f"{dialogs[0]}, {dialogs[1]}, {dialogs[2]} |")
    text = (f"## Variance: {total} runs, {REPS} reps per cell\n\n" + "\n".join(head + lines) + "\n\n"
            f"Cells that changed verdict across reps: {unstable or 'none'}.\n\n"
            f"Foreground changes during commit, runs with at least one: {fg_runs or 'none'}.\n")
    os.makedirs(VAR, exist_ok=True)
    with open(os.path.join(VAR, "unit1-variance.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    if "--summary-only" in sys.argv:
        summarize(main_cells())
    else:
        cells = main_cells()
        counts = {k: len(v) for k, v in cells.items()}
        if counts != EXPECTED:
            raise SystemExit(f"expected {EXPECTED} cells in results/, found {counts}")
        run_cells(cells)
        summarize(cells)
