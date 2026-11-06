import json, os, collections
root = r"D:\dev\interface-compiler\research\OSWorld"
ta = json.load(open(os.path.join(root, "evaluation_examples", "test_all.json")))
rt = collections.Counter(); tasks = collections.defaultdict(set); props = collections.Counter(); methods=collections.Counter()
for dom, ids in ta.items():
    for i in ids:
        t = json.load(open(os.path.join(root, "evaluation_examples", "examples", dom, i + ".json"), encoding="utf-8"))
        ev = t["evaluator"]; f = ev["func"]; fs = f if isinstance(f, list) else [f]
        opts = ev.get("options", {}); opts = opts if isinstance(opts, list) else [opts]*len(fs)
        exps = ev.get("expected"); exps = exps if isinstance(exps, list) else [exps]*len(fs)
        for k, fn in enumerate(fs):
            if fn != "compare_table": continue
            o = opts[k] if k < len(opts) else {}
            for r in (o or {}).get("rules", []):
                rt[r["type"]] += 1; tasks[r["type"]].add(i)
                pr = r.get("props") or {}
                for p, v in (pr.items() if isinstance(pr, dict) else []):
                    props[p]+=1
                    if isinstance(v, dict): methods[v.get("method")]+=1
            e = exps[k] if k < len(exps) else None
            tasks["_has_expected_"+str(type(e).__name__ if e is None else e.get("type"))].add(i)
for k, v in rt.most_common(): print(k, v, len(tasks[k]))
for k in tasks:
    if k.startswith("_"): print(k, len(tasks[k]))
print(props.most_common()); print(methods.most_common())
