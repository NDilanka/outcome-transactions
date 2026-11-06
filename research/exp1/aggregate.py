import json, statistics as S
base=r"D:\dev\interface-compiler\research\exp1"
runs=[json.load(open(f"{base}\\run{n}\\results.json")) for n in (1,2,3)]
tasks=[k for k in runs[0] if k.startswith("T")]
print("task | resident_MB | naive_cow_MB | delta_cmp_KB | fullpage_cmp_KB | ratio_naive/delta | new_pages% | pages<=16B% | wall_s | cpu_s | wall-cpu share | asleep_share")
agg={}
for t in tasks:
    m=lambda f: S.median(f(r[t]) for r in runs)
    res=m(lambda r:r["memory"]["resident_bytes_before"])/2**20
    nv=m(lambda r:r["memory"]["dirty_bytes_naive_cow"])/2**20
    dc=m(lambda r:r["memory"]["delta_compressed"])/1024
    fc=m(lambda r:r["memory"]["fullpage_compressed"])/1024
    newp=m(lambda r:r["memory"]["new_pages"]/max(r["memory"]["dirty_pages"],1))*100
    small=m(lambda r:r["memory"]["changed_bytes_hist"]["<=16"]/max(r["memory"]["dirty_pages"],1))*100
    w=m(lambda r:r["timing"]["wall_to_settle_s"]); c=m(lambda r:r["timing"]["cpu_s"]); a=m(lambda r:r["timing"]["all_asleep_sample_share"])
    pw=[r[t]["timing"].get("driver_s") for r in runs]
    agg[t]=dict(resident_MB=res,naive_MB=nv,delta_KB=dc,full_KB=fc,ratio=nv*1024/max(dc,1e-9),new_pct=newp,small_pct=small,wall=w,cpu=c,asleep=a)
    print(f"{t} | {res:.0f} | {nv:.2f} | {dc:.0f} | {fc:.0f} | {nv*1024/dc:.1f}x | {newp:.0f} | {small:.0f} | {w:.2f} | {c:.2f} | {max(0,1-c/w) if w else 0:.2f} | {a:.2f}")
json.dump(agg,open(base+"\\aggregate.json","w"),indent=1)
