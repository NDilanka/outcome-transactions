import ast, os, sys, re, json
root = r"D:\dev\interface-compiler\research\OSWorld\desktop_env\evaluators\metrics"
names = set(sys.argv[2].split(","))
maxl = int(sys.argv[3])
for fnm in sys.argv[1].split(","):
    s = open(os.path.join(root, fnm), encoding="utf-8").read()
    lines = s.splitlines()
    tree = ast.parse(s)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and (node.name in names or "*" in names):
            body = lines[node.lineno-1:node.end_lineno]
            # drop docstring
            ds = ast.get_docstring(node)
            out = []
            in_doc = False
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], "value", None), ast.Constant):
                d0, d1 = node.body[0].lineno, node.body[0].end_lineno
            else: d0 = d1 = -1
            for k, l in enumerate(body, start=node.lineno):
                if d0 <= k <= d1: continue
                st = l.strip()
                if not st or st.startswith("#") or st.startswith("logger.") or st.startswith("print("): continue
                out.append(l.rstrip())
            print(f"=== {fnm}:{node.name}")
            print("\n".join(out[:maxl]) + ("\n  ...[%d more]" % (len(out)-maxl) if len(out) > maxl else ""))
