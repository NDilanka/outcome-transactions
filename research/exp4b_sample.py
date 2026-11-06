import json, os, random
base=r"D:\dev\interface-compiler\research\OSWorld\evaluation_examples"
out=r"D:\dev\interface-compiler\research\exp4b"
os.makedirs(out,exist_ok=True)
test=json.load(open(os.path.join(base,"test_all.json")))
random.seed(42)
blind=[]; key=[]
for dom,ids in test.items():
    feas=[]
    for i in ids:
        t=json.load(open(os.path.join(base,"examples",dom,i+".json"),encoding="utf-8"))
        f=t["evaluator"]["func"]; f=f if isinstance(f,list) else [f]
        if "infeasible" in f: continue
        feas.append(t)
    n=12 if dom=="multi_apps" else 6
    for t in random.sample(feas,min(n,len(feas))):
        blind.append({"id":t["id"],"domain":dom,"instruction":t["instruction"],"starting_state_setup":t.get("config",[]),"related_apps":t.get("related_apps",[])})
        key.append({"id":t["id"],"domain":dom,"instruction":t["instruction"],"evaluator":t["evaluator"]})
json.dump(blind,open(os.path.join(out,"blind_tasks.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
os.makedirs(os.path.join(out,"answer_key"),exist_ok=True)
json.dump(key,open(os.path.join(out,"answer_key","official_evaluators.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
print(len(blind))
