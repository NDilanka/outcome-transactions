"""Preflight-to-replace race for the Excel commit.

The commit's preflight sees no holder of budget.xlsx. Then the injected hook runs, after the preflight and before
the replace. In a race run the hook opens the real workbook in Excel and keeps it open for DELAY_S seconds, so the
replace runs while Excel holds the file. The control runs the same delay without opening the file.

Expected: the replace refuses with a sharing or access error, the file keeps its bytes, and nothing is committed.
If the file changes while Excel holds it, the replace overwrote a file a user has open, which is a blocker.

  py -3 windows\\unit2\\race_experiment.py
"""
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results", "race")
os.environ["OTX_RESULTS"] = RESULTS
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "unit1"))
sys.path.insert(0, HERE)

import otx_win  # noqa: E402
import scenarios as S  # noqa: E402
from excel_com import ExcelSession  # noqa: E402

DELAY_S = 3
RUNS = [("race-1", True), ("race-2", True), ("race-3", True), ("control", False)]


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def make_hook(opens, state):
    def hook(real):
        path = os.path.join(real, "budget.xlsx")
        state["sha_before_replace"] = _sha(path)
        if opens:
            xl = ExcelSession()
            xl.__enter__()
            state["xl"] = xl
            xl.open(path)
        time.sleep(DELAY_S)
        state["holders_at_replace"] = otx_win.rm_holders(path)
        state["lock_at_replace"] = otx_win.lock_info(path)
    return hook


def run_one(tag, opens):
    state = {}
    sc = S.Scenario("normal", "excel", before_replace=make_hook(opens, state), tag=f"-{tag}")
    try:
        res = sc.run()
    finally:
        if "xl" in state:
            state["xl"].__exit__(None, None, None)
    sha_after = _sha(os.path.join(sc.real, "budget.xlsx"))
    write = (res.get("commit_writes") or [{}])[0]
    row = dict(run=tag, excel_held_file=opens, outcome=res["outcome"], holders_at_replace=state.get("holders_at_replace"),
               lock_at_replace=state.get("lock_at_replace"), replace_error=write.get("error"),
               write_ok=write.get("write_ok"), budget_sha_before=state.get("sha_before_replace"),
               budget_sha_after=sha_after, file_overwritten=sha_after != state.get("sha_before_replace"),
               real_B2=res.get("real_B2"), notes_preserved=res.get("notes_preserved"))
    row["verdict"] = verdict(row)
    with open(os.path.join(RESULTS, f"race-summary-{tag}.json"), "w", encoding="utf-8") as f:
        json.dump(row, f, indent=1, default=str)
    return row


def verdict(row):
    if row["excel_held_file"]:
        if row["file_overwritten"]:
            return "BLOCKER: replace overwrote a file Excel held open"
        if row["outcome"] == "refused" and row["write_ok"] is False:
            return "REFUSED loudly: replace failed, file unchanged"
        return f"CHECK: outcome {row['outcome']}"
    if row["outcome"] == "committed" and row["file_overwritten"]:
        return "CONTROL: committed with no holder"
    return f"CHECK: control outcome {row['outcome']}"


def main():
    os.makedirs(RESULTS, exist_ok=True)
    rows = []
    for tag, opens in RUNS:
        print("running", tag, flush=True)
        rows.append(run_one(tag, opens))
        print(json.dumps({k: rows[-1][k] for k in ("run", "outcome", "verdict")}), flush=True)
    head = ["| run | Excel held the file at replace | holders at replace | outcome | replace error | file changed | real B2 | notes kept | verdict |",
            "|---|---|---|---|---|---|---|---|---|"]
    lines = [f"| {r['run']} | {'yes' if r['excel_held_file'] else 'no'} | {len(r['holders_at_replace'] or [])} | "
             f"{r['outcome']} | {r['replace_error'] or '-'} | {'yes' if r['file_overwritten'] else 'no'} | "
             f"{r['real_B2']} | {r['notes_preserved']} | {r['verdict']} |" for r in rows]
    text = "## Preflight-to-replace race\n\n" + "\n".join(head + lines) + "\n"
    with open(os.path.join(RESULTS, "unit2-race.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
