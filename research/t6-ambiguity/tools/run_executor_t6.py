#!/usr/bin/env python3
"""T6 step 3: run the frozen executor (specexec.py at c909d02) on all 80 end states.

Also runs each spec against the unchanged start tree (control: start vs start), so a spec
that accepts the untouched file is visible.
Writes /home/factory-user/t6-work/executor_results.json.
"""
import hashlib
import importlib.util
import json
import os
import sys
import time

import yaml

REPO = "/home/factory-user/repos/outcome-transactions"
SPECEXEC = os.path.join(REPO, "research/exp6-executed/specexec.py")
SPEC_DIR = os.path.join(REPO, "research/t6-ambiguity/specs")
T6 = "/home/factory-user/t6-work"
SNAP = os.path.join(REPO, "research/exp5-grounded/snapshots")
OUT = os.path.join(T6, "executor_results.json")


def verify_freeze():
    bad = []
    n = 0
    for line in open(os.path.join(SPEC_DIR, "FROZEN.sha256")):
        digest, name = line.split()
        n += 1
        h = hashlib.sha256(open(os.path.join(SPEC_DIR, name), "rb").read()).hexdigest()
        if h != digest:
            bad.append(name)
    assert n == 80, n
    assert not bad, f"spec hash mismatch: {bad}"
    return n


def load_exec():
    spec = importlib.util.spec_from_file_location("specexec_c909d02", SPECEXEC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    n = verify_freeze()
    print(f"freeze OK: {n} spec hashes match FROZEN.sha256", flush=True)
    se = load_exec()
    amb = json.load(open(os.path.join(T6, "private/ambiguity-set.json")))
    results = []
    t0 = time.time()
    for item in amb:
        aid = item["id"]
        spec_list = yaml.safe_load(open(os.path.join(SPEC_DIR, f"{aid}.yaml")))
        assert isinstance(spec_list, list) and len(spec_list) == 1, aid
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
        results.append(rec)
        ra, rb, rs = rec["runs"]["A"], rec["runs"]["B"], rec["runs"]["START"]
        print(f"{aid} A={ra['decision']}/{ra['empty_all_undecided_decision']} "
              f"B={rb['decision']}/{rb['empty_all_undecided_decision']} "
              f"START={rs['decision']}/{rs['empty_all_undecided_decision']} "
              f"({time.time() - t0:.0f}s)", flush=True)
    json.dump(results, open(OUT, "w"), indent=1, default=str)
    print(f"wrote {OUT}: {len(results)} requests, {2 * len(results)} end states", flush=True)


if __name__ == "__main__":
    sys.exit(main())
