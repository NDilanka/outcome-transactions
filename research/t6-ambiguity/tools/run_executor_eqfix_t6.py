#!/usr/bin/env python3
"""T6 sensitivity run: the frozen executor (specexec.py at c909d02) with __eq__/__hash__ added IN MEMORY
for CellObj (table cell text) and RunP (text run text + colour). The frozen file is not modified.

Same 40 requests x (A, B, START) as run_executor_t6.py. Writes results/executor_results_eqfix.json and prints
every decision that differs from the frozen run.
"""
import importlib.util
import json
import os
import sys

import yaml

REPO = "/home/factory-user/repos/outcome-transactions"
SPECEXEC = os.path.join(REPO, "research/exp6-executed/specexec.py")
SPEC_DIR = os.path.join(REPO, "research/t6-ambiguity/specs")
T6 = "/home/factory-user/t6-work"
SNAP = os.path.join(REPO, "research/exp5-grounded/snapshots")
FROZEN = os.path.join(T6, "executor_results.json")
OUT = os.path.join(T6, "executor_results_eqfix.json")


def load_patched():
    spec = importlib.util.spec_from_file_location("specexec_c909d02", SPECEXEC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def cell_eq(self, o):
        return isinstance(o, mod.CellObj) and self.text == o.text

    def run_eq(self, o):
        return isinstance(o, mod.RunP) and self.text == o.text and self.color == o.color

    mod.CellObj.__eq__ = cell_eq
    mod.CellObj.__hash__ = lambda self: hash(self.text)
    mod.RunP.__eq__ = run_eq
    mod.RunP.__hash__ = lambda self: hash((self.text, self.color))
    return mod


def main():
    se = load_patched()
    amb = json.load(open(os.path.join(T6, "private/ambiguity-set.json")))
    frozen = {r["id"]: r for r in json.load(open(FROZEN))}
    results = []
    changed = []
    for item in amb:
        aid = item["id"]
        spec_list = yaml.safe_load(open(os.path.join(SPEC_DIR, f"{aid}.yaml")))
        spec = spec_list[0]
        start_root = os.path.join(SNAP, item["task_id"])
        rec = {"id": aid, "task_id": item["task_id"], "file": item["file"], "runs": {}}
        for label, end_root in (
            ("A", os.path.join(T6, "endstates", aid, "A")),
            ("B", os.path.join(T6, "endstates", aid, "B")),
            ("START", start_root),
        ):
            r = se.run_spec(spec, end_root, start_root)
            rec["runs"][label] = {
                "decision": r["decision"],
                "empty_all_undecided_decision": r["empty_all_undecided_decision"],
                "statuses": [p["status"] for p in r["predicates"]],
                "predicates": r["predicates"],
            }
            fz = frozen[aid]["runs"][label]
            if fz["empty_all_undecided_decision"] != r["empty_all_undecided_decision"]:
                changed.append(f"{aid} {label}: frozen {fz['empty_all_undecided_decision']} -> eqfix {r['empty_all_undecided_decision']}")
        results.append(rec)
    json.dump(results, open(OUT, "w"), indent=1, default=str)
    print(f"wrote {OUT}")
    print(f"decision changes vs frozen: {len(changed)}")
    for c in changed:
        print("  " + c)


if __name__ == "__main__":
    sys.exit(main())
