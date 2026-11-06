import json, glob, os, collections
base=r"D:\dev\interface-compiler\research\OSWorld\evaluation_examples"
test=json.load(open(os.path.join(base,"test_all.json")))
print("test_all domains", {k:len(v) for k,v in test.items()}, sum(len(v) for v in test.values()))
types=collections.Counter(); funcs=collections.Counter(); ex_by_type=collections.defaultdict(list)
missing=0
for dom,ids in test.items():
    for i in ids:
        p=os.path.join(base,"examples",dom,i+".json")
        if not os.path.exists(p): missing+=1; continue
        t=json.load(open(p,encoding="utf-8"))
        ev=t.get("evaluator",{})
        f=ev.get("func"); f=f if isinstance(f,list) else [f]
        for x in f: funcs[x]+=1
        r=ev.get("result")
        rs=r if isinstance(r,list) else ([r] if r else [])
        for x in rs:
            types[x.get("type")]+=1
            if len(ex_by_type[x.get("type")])<2: ex_by_type[x.get("type")].append((dom,t["instruction"][:90]))
print("missing",missing)
print("RESULT TYPES"); [print(f"  {k}: {v}  e.g. {ex_by_type[k]}") for k,v in types.most_common()]
print("FUNCS"); print(funcs.most_common())
