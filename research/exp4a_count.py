import json, os, collections, glob
root = r"D:\dev\interface-compiler\research\OSWorld"
ta = json.load(open(os.path.join(root, "evaluation_examples", "test_all.json")))
cnt = collections.Counter(); ex = {}; getters = collections.Counter(); multi = 0; conj = collections.Counter()
for dom, ids in ta.items():
    for i in ids:
        p = os.path.join(root, "evaluation_examples", "examples", dom, i + ".json")
        t = json.load(open(p, encoding="utf-8"))
        ev = t["evaluator"]
        f = ev["func"]; fs = f if isinstance(f, list) else [f]
        if isinstance(f, list): multi += 1; conj[ev.get("conj", "and")] += 1
        for x in set(fs):
            cnt[x] += 1; ex.setdefault(x, f"{dom}/{i}")
        for k in ("result", "expected"):
            g = ev.get(k)
            gs = g if isinstance(g, list) else [g]
            for gg in gs:
                if isinstance(gg, dict): getters[gg.get("type")] += 1
print(len(cnt), sum(len(v) for v in ta.values()), "multi", multi, dict(conj))
for k, v in cnt.most_common(): print(k, v, ex[k])
print("GETTERS", len(getters))
for k, v in getters.most_common(): print(" ", k, v)
