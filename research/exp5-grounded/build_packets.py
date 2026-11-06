"""Build blind paired judge packets: for each task, the 4b blind spec and the new grounded spec,
labelled X/Y in a seeded random order. The key mapping X/Y -> version is written separately."""
import os, json, random, glob, yaml
H = os.path.dirname(os.path.abspath(__file__))
old = {s["id"]: s for s in yaml.safe_load(open(os.path.join(H, "..", "exp4b", "generated_specs.yaml"), encoding="utf-8"))}
new = {}
for f in sorted(glob.glob(os.path.join(H, "specs", "batch_*.yaml"))):
    for s in yaml.safe_load(open(f, encoding="utf-8")): new[s["id"]] = s
tasks = json.load(open(os.path.join(H, "..", "exp4b", "blind_tasks.json")))
rng = random.Random(20261106); key = {}; packets = []
for t in tasks:
    o, n = dict(old[t["id"]]), dict(new[t["id"]])
    n.pop("grounding_used", None)  # would reveal which spec is grounded
    x_is_new = rng.random() < 0.5
    key[t["id"]] = "X=grounded" if x_is_new else "X=blind"
    packets.append(dict(id=t["id"], domain=t["domain"], instruction=t["instruction"],
        inspection_report=f"research/exp5-grounded/inspections/{t['id']}.md" if os.path.exists(os.path.join(H, "inspections", t["id"] + ".md")) else None,
        spec_X=n if x_is_new else o, spec_Y=o if x_is_new else n))
os.makedirs(os.path.join(H, "judge"), exist_ok=True)
json.dump(key, open(os.path.join(H, "judge_key.json"), "w"), indent=1)
for i in range(6):
    json.dump(packets[i*11:(i+1)*11], open(os.path.join(H, "judge", f"packets_{i+1}.json"), "w"), indent=1, ensure_ascii=False)
print(len(old), len(new), len(packets), "missing new:", [t["id"] for t in tasks if t["id"] not in new])
