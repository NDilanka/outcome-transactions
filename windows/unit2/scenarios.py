"""Windows outcome-transaction scenarios: normal, conflict, and same_cell.

  py -3 windows/unit2/scenarios.py --offline          template workspace, XML fork methods, no Office
  py -3 windows/unit2/scenarios.py --excel            Excel COM workspace and forks (run by the orchestrator)
  add --only <scenario> to run one scenario
"""
import contextlib
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "unit1"))
sys.path.insert(0, HERE)

import backend as B  # noqa: E402
import make_workspace as MW  # noqa: E402
import otx_win  # noqa: E402
import spec_win as SW  # noqa: E402
import xlsx_edit as XE  # noqa: E402
from open_doc_experiment import commit_file  # noqa: E402

WORK = os.path.join(HERE, "work")
RESULTS = os.path.join(HERE, "results")
TIMEOUT_S = 240
MAX_TRIES = 3
NOTE = "user typed this during the search\n"
USER_CELL = {"conflict": ("C3", 77), "same_cell": ("B2", 77)}
SCENARIOS = ["normal", "conflict", "same_cell"]
OFFICE = ("EXCEL.EXE", "WINWORD.EXE")
MODES = {
    "offline": dict(excel=False, direct="direct_xlsx", null="null_xlsx", wrong="wrong_xlsx"),
    "excel": dict(excel=True, direct="com_excel", null="com_null", wrong="wrong_xlsx"),
}
SPEC = {
    "request": "Q3 budget with B2 = 5000, exported as out/q3.csv",
    "must": [("xlsx_cell", "budget.xlsx", "B2", "==", 5000), ("exists", "out/q3.csv"),
             ("file_contains", "out/q3.csv", "5000")],
    "footprint": ["budget.xlsx", "out/q3.csv"],
    "preserve": [("xlsx_cells_except", "budget.xlsx", ["B2"])],
}
# name, cell edits, write out/q3.csv, append to notes.txt, expected to pass
MUTANTS = [
    ("start_state", [], False, False, False),
    ("wrong_value_B2_4999", [("B2", 4999)], True, False, False),
    ("no_q3_csv", [("B2", 5000)], False, False, False),
    ("collateral_C5", [("B2", 5000), ("C5", 1)], True, False, False),
    ("outside_footprint_notes", [("B2", 5000)], True, True, False),
    ("positive_control", [("B2", 5000)], True, False, True),
]


def make_mutant(d, edits, csv, notes):
    xlsx = os.path.join(d, "budget.xlsx")
    for ref, val in edits:
        XE.set_number(xlsx, ref, val)
    if csv:
        XE.write_csv(otx_win.xlsx_cells(xlsx), os.path.join(d, "out", "q3.csv"))
    if notes:
        with open(os.path.join(d, "notes.txt"), "a", encoding="utf-8", newline="") as f:
            f.write("x\n")


def mutation_test(root, snap):
    """Deliberately wrong outcomes must be rejected and the positive control accepted, or the spec is not trusted."""
    results = {}
    for name, edits, csv, notes, expect in MUTANTS:
        d = os.path.join(root, "mut", name)
        shutil.copytree(snap, d)
        make_mutant(d, edits, csv, notes)
        ok, reasons, _ = SW.evaluate(SPEC, snap, d)
        results[name] = dict(expected_pass=expect, passed=ok, correct=ok == expect, reasons=reasons[:3])
    return results


def _read_or_none(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return f.read()


class Scenario:
    def __init__(self, name, mode):
        self.name = name
        self.mode = mode
        self.cfg = MODES[mode]
        self.refuse_office = not self.cfg["excel"]
        os.makedirs(WORK, exist_ok=True)
        self.root = tempfile.mkdtemp(prefix=f"{name}-{mode}-", dir=WORK)
        self.real = os.path.join(self.root, "real")
        self.snap = os.path.join(self.root, "snap")
        self.base = {}
        self.noise = []
        self.forks = {}
        self.res = dict(scenario=name, mode=mode, root=self.root, snapshot_method=B.SNAPSHOT_METHOD,
                        isolation=B.ISOLATION, timings={})

    @contextlib.contextmanager
    def timed(self, key):
        t0 = time.monotonic()
        try:
            yield
        finally:
            self.res["timings"][key] = round(self.res["timings"].get(key, 0) + time.monotonic() - t0, 2)

    def run(self):
        t0 = time.monotonic()
        try:
            self.res["outcome"] = self._pipeline()
        except Exception:
            self.res["outcome"] = "error"
            self.res["error"] = traceback.format_exc()[-1500:]
        self._finish()
        self.res["timings"]["total"] = round(time.monotonic() - t0, 2)
        self._write()
        return self.res

    def _pipeline(self):
        with self.timed("setup"):
            MW.build(self.real, excel=self.cfg["excel"])
        with self.timed("snapshot"):
            self.base = B.snapshot(self.real, self.snap)
        self.res["spec_hash"] = hashlib.sha256(json.dumps(SPEC, sort_keys=True).encode()).hexdigest()[:12]
        with self.timed("mutation"):
            self.res["mutation"] = mutation_test(self.root, self.snap)
        if not all(m["correct"] for m in self.res["mutation"].values()):
            return "spec_rejected"
        self._search()
        self.noise = B.changed_paths(self.snap, self._fork_dir("f0_null"))
        with self.timed("verify"):
            verdicts = {n: self._verdict(self.snap, self._fork_dir(n), self.forks[n], self.noise)
                        for n in ("f0_null", "f1_direct", "f2_wrong")}
        self.res["forks"] = verdicts
        self.res["noise"] = self.noise
        agreement = self._agreement(verdicts)
        self.res["agreement"] = agreement
        if agreement != "direct_only":
            return agreement
        self.res["winner"] = self.winner = "f1_direct"
        return self._merge(verdicts["f1_direct"])

    def _fork_dir(self, name):
        return os.path.join(self.root, "forks", name)

    def _search(self):
        plan = [("f0_null", self.cfg["null"]), ("f1_direct", self.cfg["direct"]), ("f2_wrong", self.cfg["wrong"])]
        with self.timed("search"):
            for i, (name, method) in enumerate(plan):
                self.forks[name] = B.run_fork(method, self.snap, self._fork_dir(name), TIMEOUT_S,
                                              refuse_office=self.refuse_office)
                if i == 0:
                    self._user_edit()
        self.res["user_edit_after"] = "f0_null"

    def _user_edit(self):
        with open(os.path.join(self.real, "notes.txt"), "a", encoding="utf-8", newline="") as f:
            f.write(NOTE)
        if self.name in USER_CELL:
            ref, val = USER_CELL[self.name]
            XE.set_number(os.path.join(self.real, "budget.xlsx"), ref, val)

    @staticmethod
    def _verdict(base, fd, run, noise):
        ok, reasons, changed = SW.evaluate(SPEC, base, fd, noise)
        if run["rc"] != 0:
            ok, reasons = False, [f"method exit code {run['rc']}"] + reasons
        return dict(run, verified=ok, reasons=reasons[:4], changed=changed,
                    outcome=SW.semantic_diff(base, fd, SPEC))

    @staticmethod
    def _agreement(v):
        if v["f0_null"]["verified"] or v["f2_wrong"]["verified"]:
            return "spec_ambiguous"
        return "direct_only" if v["f1_direct"]["verified"] else "no_passing_fork"

    def _merge(self, winner):
        fd = self._fork_dir(self.winner)
        now = B.tree_hashes(self.real)
        moved = sorted(f for f in winner["changed"] if now.get(f) != self.base.get(f))
        user_changed = sorted(k for k in set(now) | set(self.base) if now.get(k) != self.base.get(k))
        self.res["merge"] = dict(user_changes_since_snapshot=user_changed, footprint_conflicts=moved)
        if not moved:
            return self._commit(fd, winner["changed"], before=None)
        if moved != ["budget.xlsx"]:
            return "true_conflict"
        m = SW.merge_test(os.path.join(self.snap, "budget.xlsx"), os.path.join(self.real, "budget.xlsx"),
                          os.path.join(fd, "budget.xlsx"))
        self.res["merge_test"] = m
        if m["outcome"] == "true_conflict":
            return "true_conflict"
        return self._replay_and_commit()

    def _replay_and_commit(self):
        self.res["replay_verdicts"] = []
        for attempt in range(1, MAX_TRIES + 1):
            self.res["replays"] = attempt
            start = B.tree_hashes(self.real)
            base = os.path.join(self.root, f"base{attempt}")
            fd = self._fork_dir(f"replay{attempt}")
            with self.timed("replay"):
                B.snapshot(self.real, base)
                run = B.run_fork(self.cfg["direct"], base, fd, TIMEOUT_S, refuse_office=self.refuse_office)
                verdict = self._verdict(base, fd, run, self.noise)
            self.res["replay_verdicts"].append(dict(verdict, attempt=attempt))
            if not verdict["verified"]:
                return "replay_failed"
            if B.tree_hashes(self.real) == start:
                self.res["winner"] = self.winner = f"replay{attempt}"
                return self._commit(fd, verdict["changed"], before=base)
        return "replay_retries_exhausted"

    def _commit(self, fd, changed, before):
        real_xlsx = os.path.join(self.real, "budget.xlsx")
        holders, lock = otx_win.rm_holders(real_xlsx), otx_win.lock_info(real_xlsx)
        self.res["commit_preflight"] = dict(holders=holders, lock_file=lock)
        if holders != [] or lock is not None:
            return "routed_to_owner"
        with self.timed("commit"):
            if before is None:
                before = os.path.join(self.root, "pre")
                B.snapshot(self.real, before)
            saved = {f: _read_or_none(os.path.join(self.real, f)) for f in changed}
            writes = self._transplant(fd, changed)
            self.res["commit_writes"] = writes
            if not all(w["write_ok"] for w in writes):
                self._rollback(saved)
                return "rolled_back"
            ok, reasons, _ = SW.evaluate(SPEC, before, self.real, self.noise)
            self.res["reverify"] = dict(ok=ok, reasons=reasons[:4])
            if not ok:
                self._rollback(saved)
                return "rolled_back"
        return "committed"

    def _transplant(self, fd, changed):
        out = []
        for f in changed:
            src, dst = os.path.join(fd, f), os.path.join(self.real, f)
            if not os.path.exists(src):
                out.append(dict(file=f, write_ok=False, error="missing in fork"))
                break
            with open(src, "rb") as fh:
                rec = commit_file("replace", dst, fh.read())
            out.append(dict(rec, file=f))
            if not rec["write_ok"]:
                break
        return out

    def _rollback(self, saved):
        self.res["rollback"] = []
        for f, data in saved.items():
            dst = os.path.join(self.real, f)
            if data is None:
                if os.path.exists(dst):
                    os.remove(dst)
                self.res["rollback"].append(dict(file=f, action="removed file this run created"))
            else:
                rec = commit_file("replace", dst, data)
                self.res["rollback"].append(dict(file=f, write_ok=rec["write_ok"], error=rec["error"]))

    def _finish(self):
        try:
            with open(os.path.join(self.real, "notes.txt"), encoding="utf-8") as f:
                notes = f.read()
            cells = otx_win.xlsx_cells(os.path.join(self.real, "budget.xlsx"))
        except Exception as e:
            self.res["final_read_error"] = repr(e)
            return
        self.res["notes_preserved"] = NOTE in notes
        self.res["real_B2"] = cells.get("B2")
        if self.name in USER_CELL:
            ref, val = USER_CELL[self.name]
            self.res["user_cell_preserved"] = cells.get(ref) == float(val)
        else:
            self.res["user_cell_preserved"] = None

    def _write(self):
        os.makedirs(RESULTS, exist_ok=True)
        suffix = "" if self.mode == "offline" else "-excel"
        path = os.path.join(RESULTS, f"{self.name}{suffix}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.res, f, indent=1, default=str)


def _row(r):
    t, forks = r["timings"], r.get("forks", {})
    div = " / ".join(str(forks[n]["divergence_bytes"]) for n in ("f1_direct", "f2_wrong", "f0_null") if n in forks)
    mut = r.get("mutation", {})
    mut_ok = f"{sum(m['correct'] for m in mut.values())}/{len(mut)}" if mut else "-"
    net = forks.get("f1_direct", {}).get("network", {})
    guard = f"{net.get('network_guard', '-')}; office COM {net.get('office_com', '-')}"
    committed = "yes" if r["outcome"] == "committed" else "no"
    cols = [r["scenario"], r["outcome"], r.get("winner", "-"), str(r.get("replays", 0)),
            str(r.get("notes_preserved")), str(r.get("user_cell_preserved")), committed,
            str(t.get("snapshot", "-")), str(t.get("search", "-")), str(t.get("verify", "-")),
            str(t.get("commit", "-")), str(t.get("total", "-")), div or "-", mut_ok, guard]
    return "| " + " | ".join(cols) + " |"


def write_table(results, mode):
    name = "unit2-results.md" if mode == "offline" else "unit2-results-excel.md"
    head = ["Scenario", "Outcome", "Winner", "Replays", "Notes kept", "User cell kept", "Committed",
            "Snapshot s", "Search s", "Verify s", "Commit s", "Total s", "Divergence bytes direct / wrong / null",
            "Mutation correct", "Network guard"]
    lines = [f"# Unit 2 results ({mode})", "",
             f"Isolation: {B.ISOLATION}. Snapshot method: {B.SNAPSHOT_METHOD}.", "",
             "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += [_row(r) for r in results]
    with open(os.path.join(RESULTS, name), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def _office_pids():
    return {img: otx_win.image_pids(img) for img in OFFICE}


def main(argv):
    if "--offline" in argv:
        mode = "offline"
    elif "--excel" in argv:
        mode = "excel"
    else:
        print("usage: scenarios.py --offline | --excel [--only NAME]", file=sys.stderr)
        return 2
    names = [argv[argv.index("--only") + 1]] if "--only" in argv else SCENARIOS
    if mode == "offline":
        B.refuse_office_com()
    office_before = _office_pids()
    results = [Scenario(n, mode).run() for n in names]
    started = {img: sorted(otx_win.image_pids(img) - office_before[img]) for img in OFFICE}
    if names == SCENARIOS:
        write_table(results, mode)
    print(json.dumps(dict(mode=mode, new_office_pids_during_run=started,
                          outcomes={r["scenario"]: r["outcome"] for r in results})))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
