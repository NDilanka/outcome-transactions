#!/usr/bin/env python3
"""Independent tree-diff check for T6 end states (not the builders' own checks).

For each request: start = exp5 snapshot for the task; A/B = endstates/<amb>/{A,B}.
Reports per state: files that differ from start (added/removed/changed),
whether the target file changed, and whether A and B differ from each other.
"""
import hashlib
import json
import os
import sys

T6 = "/home/factory-user/t6-work"
SNAP = "/home/factory-user/repos/outcome-transactions/research/exp5-grounded/snapshots"
AMB = json.load(open(os.path.join(T6, "private/ambiguity-set.json")))


def tree(root):
    out = {}
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            if f.endswith(".pyc") or "__pycache__" in dp:
                continue
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, root)
            with open(full, "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def diff(a, b):
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    return added, removed, changed


def main(only=None):
    rows = []
    for item in AMB:
        aid = item["id"]
        if only and aid not in only:
            continue
        start = tree(os.path.join(SNAP, item["task_id"]))
        target = item["file"]
        states = {}
        for s in ("A", "B"):
            states[s] = tree(os.path.join(T6, "endstates", aid, s))
        ab_add, ab_rem, ab_chg = diff(states["A"], states["B"])
        ab_equal = not (ab_add or ab_rem or ab_chg)
        rec = {"id": aid, "target": target, "ab_equal": ab_equal, "ab_diff": ab_chg + ab_add + ab_rem}
        for s in ("A", "B"):
            add, rem, chg = diff(start, states[s])
            rec[s] = {
                "added": add,
                "removed": rem,
                "changed": chg,
                "target_changed": target in chg,
                "target_present": target in states[s],
                "any_change": bool(add or rem or chg),
            }
        rows.append(rec)
        flag = []
        if not rec["A"]["any_change"]:
            flag.append("A_NO_CHANGE")
        if not rec["B"]["any_change"]:
            flag.append("B_NO_CHANGE")
        if ab_equal:
            flag.append("A==B")
        extra_A = [f for f in rec["A"]["added"] + rec["A"]["removed"] + rec["A"]["changed"] if f != target]
        extra_B = [f for f in rec["B"]["added"] + rec["B"]["removed"] + rec["B"]["changed"] if f != target]
        if extra_A:
            flag.append("A_OTHER_FILES:" + ",".join(extra_A))
        if extra_B:
            flag.append("B_OTHER_FILES:" + ",".join(extra_B))
        if not rec["A"]["target_present"]:
            flag.append("A_TARGET_MISSING")
        if not rec["B"]["target_present"]:
            flag.append("B_TARGET_MISSING")
        print(f"{aid} target={target.split('/')[-1]} A_changed={rec['A']['target_changed']} "
              f"B_changed={rec['B']['target_changed']} "
              f"A_nfiles={len(states['A'])} B_nfiles={len(states['B'])} start_nfiles={len(start)} "
              + (" | " + " ".join(flag) if flag else ""))
    json.dump(rows, open(os.path.join(T6, "verify_endstates.json"), "w"), indent=1)


if __name__ == "__main__":
    only = set(sys.argv[1:]) or None
    main(only)
