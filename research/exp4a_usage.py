import json, os, collections, ast, sys
root = r"D:\dev\interface-compiler\research\OSWorld"
ta = json.load(open(os.path.join(root, "evaluation_examples", "test_all.json")))
info = collections.defaultdict(lambda: {"res": collections.Counter(), "exp": collections.Counter(), "opts": set(), "post": 0, "n":0, "ex": None})
for dom, ids in ta.items():
    for i in ids:
        t = json.load(open(os.path.join(root, "evaluation_examples", "examples", dom, i + ".json"), encoding="utf-8"))
        ev = t["evaluator"]; f = ev["func"]
        fs = f if isinstance(f, list) else [f]
        def L(x, n):
            if isinstance(x, list): return x
            return [x]*n
        rs = L(ev.get("result"), len(fs)); es = L(ev.get("expected"), len(fs)); os_ = L(ev.get("options", {}), len(fs))
        for k, fn in enumerate(fs):
            d = info[fn]; d["n"] += 1
            r = rs[k] if k < len(rs) else None; e = es[k] if k < len(es) else None; o = os_[k] if k < len(os_) else {}
            d["res"][(r or {}).get("type") if isinstance(r, dict) else str(r)] += 1
            d["exp"][(e or {}).get("type") if isinstance(e, dict) else str(e)] += 1
            if isinstance(o, dict): d["opts"] |= set(o.keys())
            if ev.get("postconfig"): d["post"] += 1
            if d["ex"] is None: d["ex"] = json.dumps({"instr": t.get("instruction","")[:200], "res": r, "exp": e, "opt": o})[:700]
out = []
for fn, d in sorted(info.items(), key=lambda x: -x[1]["n"]):
    out.append(f"### {fn} n={d['n']} post={d['post']} res={dict(d['res'])} exp={dict(d['exp'])} opts={sorted(d['opts'])}\n  {d['ex']}")
open(r"D:\dev\interface-compiler\research\exp4a_usage.txt","w",encoding="utf-8").write("\n".join(out))
# function source index
src = {}
mdir = os.path.join(root, "desktop_env", "evaluators", "metrics")
for fnm in os.listdir(mdir):
    if not fnm.endswith(".py"): continue
    s = open(os.path.join(mdir, fnm), encoding="utf-8").read()
    tree = ast.parse(s)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            src[node.name] = (fnm, node.lineno, node.end_lineno)
missing = [f for f in info if f not in src]
print("missing", missing)
lines = []
for fn in sorted(info, key=lambda x: (src.get(x, ("z",))[0], src.get(x,("z",0))[1] if x in src else 0)):
    if fn in src: lines.append(f"{fn}: {src[fn][0]}:{src[fn][1]}-{src[fn][2]} ({src[fn][2]-src[fn][1]+1} lines)")
print("\n".join(lines))
