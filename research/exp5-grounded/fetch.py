"""Rebuild each task's starting files (the 'download' steps of its setup) into snapshots/<id>/."""
import json, os, sys, urllib.request, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__))
tasks = json.load(open(os.path.join(HERE, "..", "exp4b", "blind_tasks.json")))
jobs = []
for t in tasks:
    for step in t["starting_state_setup"]:
        if step["type"] == "download":
            for f in step["parameters"]["files"]:
                jobs.append((t["id"], f["url"], f["path"]))
def get(job):
    tid, url, path = job
    dst = os.path.join(HERE, "snapshots", tid, path.lstrip("/"))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst) and os.path.getsize(dst) > 0: return tid, path, os.path.getsize(dst), None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as o: o.write(r.read())
        return tid, path, os.path.getsize(dst), None
    except Exception as e:
        return tid, path, 0, str(e)[:120]
with cf.ThreadPoolExecutor(8) as ex:
    res = list(ex.map(get, jobs))
bad = [r for r in res if r[3]]
print(f"{len(res)} files for {len({r[0] for r in res})} tasks, {sum(r[2] for r in res)/1e6:.1f} MB, {len(bad)} failed")
for r in bad: print("FAIL", r)
