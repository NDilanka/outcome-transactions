import json, os, collections
root = r"D:\dev\interface-compiler\research\OSWorld"
ta = json.load(open(os.path.join(root, "evaluation_examples", "test_all.json")))
pc = collections.Counter(); cmds = []
for dom, ids in ta.items():
    for i in ids:
        t = json.load(open(os.path.join(root, "evaluation_examples", "examples", dom, i + ".json"), encoding="utf-8"))
        ev = t["evaluator"]
        for p in ev.get("postconfig", []) or []:
            pc[p.get("type")] += 1
        f = ev["func"]; fs = f if isinstance(f, list) else [f]
        rs = ev.get("result"); rs = rs if isinstance(rs, list) else [rs]*len(fs)
        for k, fn in enumerate(fs):
            r = rs[k] if k < len(rs) else None
            if isinstance(r, dict) and r.get("type") in ("vm_command_line","vm_command_error","vm_terminal_output"):
                c = r.get("command"); c = " ".join(c) if isinstance(c, list) else str(c)
                cmds.append(f"{fn} | {c[:150]}")
print(pc.most_common())
print("\n".join(cmds))
