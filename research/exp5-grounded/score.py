"""Unblind judge verdicts and compare blind (4b) vs grounded (5) specs, paired by task."""
import os, json, glob, collections
H = os.path.dirname(os.path.abspath(__file__))
key = json.load(open(os.path.join(H, "judge_key.json")))
V = [v for f in sorted(glob.glob(os.path.join(H, "judge", "verdicts_*.json"))) for v in json.load(open(f, encoding="utf-8"))]
has_files = {f[:-3] for f in os.listdir(os.path.join(H, "inspections"))}
GOOD = {"equivalent", "stricter_reasonable", "different_spec_better"}
WRONG = {"stricter_overstrict", "looser", "different_official_better", "unverifiable"}
rows = []
for v in V:
    xg = key[v["id"]] == "X=grounded"
    g, b = (v["verdict_X"], v["verdict_Y"]) if xg else (v["verdict_Y"], v["verdict_X"])
    better = {"tie": "tie", "X": "grounded" if xg else "blind", "Y": "blind" if xg else "grounded"}.get(v["better"], v["better"])
    rows.append(dict(id=v["id"], grounded=g, blind=b, better=better, files=v["id"] in has_files, ref=v.get("official_uses_reference_file"),
                     notes_grounded=v["notes_X"] if xg else v["notes_Y"], notes_blind=v["notes_Y"] if xg else v["notes_X"]))
def summary(rs, label):
    n = len(rs)
    if not n: return
    c = lambda arm: collections.Counter(r[arm] for r in rs)
    print(f"\n== {label} (n={n})")
    for arm in ("blind", "grounded"):
        cc = c(arm); w = sum(cc[k] for k in WRONG)
        print(f"{arm:9s} wrong={w} ({w/n:.1%})  " + "  ".join(f"{k}={cc[k]}" for k in sorted(cc)))
    bt = collections.Counter(r["better"] for r in rs); print("better:", dict(bt))
    fixed = [r["id"][:8] for r in rs if r["blind"] in WRONG and r["grounded"] not in WRONG]
    broke = [r["id"][:8] for r in rs if r["blind"] not in WRONG and r["grounded"] in WRONG]
    print(f"fixed by grounding ({len(fixed)}): {fixed}\nbroken by grounding ({len(broke)}): {broke}")
print(f"verdicts: {len(V)} of {len(key)}")
summary(rows, "all tasks")
summary([r for r in rows if r["files"]], "tasks with starting files (grounding possible)")
summary([r for r in rows if not r["files"]], "tasks without starting files (control)")
summary([r for r in rows if r["ref"]], "official uses a gold reference file")
json.dump(rows, open(os.path.join(H, "paired_results.json"), "w"), indent=1)
