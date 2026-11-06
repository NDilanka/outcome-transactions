#!/usr/bin/env python3
"""Experiment 1 + 2: memory divergence (soft-dirty, sub-page deltas) and time-warp headroom
for scripted GUI tasks in LibreOffice Calc under Xvfb. Run as root inside WSL."""
import os, sys, time, json, subprocess, struct, zlib, hashlib, re, glob, signal

PAGE = 4096
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/exp1"
os.makedirs(OUT, exist_ok=True)
ENV = dict(os.environ, DISPLAY=":99", HOME="/root", SAL_USE_VCLPLUGIN="gen")

def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, env=ENV, capture_output=True, text=True, **kw)

def pids_of(name):
    out = sh(f"pgrep -x {name}").stdout.split()
    return [int(p) for p in out]

def regions(pid):
    rs = []
    with open(f"/proc/{pid}/maps") as f:
        for line in f:
            parts = line.split()
            a, b = (int(x, 16) for x in parts[0].split("-"))
            perms = parts[1]
            name = parts[5] if len(parts) > 5 else ""
            if "w" not in perms or name.startswith("[vsyscall]") or name.startswith("[vvar"):
                continue
            rs.append((a, b, name))
    return rs

def read_mem(pid, pages):
    """Read only the given page addresses, coalescing contiguous runs; unreadable pages are skipped."""
    data = {}
    pages = sorted(pages)
    runs, i = [], 0
    while i < len(pages):
        j = i
        while j + 1 < len(pages) and pages[j + 1] == pages[j] + PAGE and j - i < 255:
            j += 1
        runs.append((pages[i], pages[j] + PAGE)); i = j + 1
    with open(f"/proc/{pid}/mem", "rb", 0) as m:
        for start, end in runs:
            try:
                m.seek(start); buf = m.read(end - start)
                for k in range(0, len(buf), PAGE):
                    data[start + k] = buf[k:k + PAGE]
            except OSError:
                for p in range(start, end, PAGE):
                    try:
                        m.seek(p); data[p] = m.read(PAGE)
                    except OSError:
                        pass
    return data

def pagemap_flags(pid, a, b):
    res = {}
    with open(f"/proc/{pid}/pagemap", "rb", 0) as pm:
        pm.seek((a // PAGE) * 8)
        raw = pm.read(((b - a) // PAGE) * 8)
    for i in range(len(raw) // 8):
        (v,) = struct.unpack_from("<Q", raw, i * 8)
        res[a + i * PAGE] = v
    return res

def snapshot(pids):
    snap = {}
    for pid in pids:
        with open(f"/proc/{pid}/clear_refs", "w") as f:
            f.write("4")
        pages = {}
        for a, b, _ in regions(pid):
            flags = pagemap_flags(pid, a, b)
            present = [p for p, v in flags.items() if v >> 63 & 1 or v >> 62 & 1]
            if not present:
                continue
            got = read_mem(pid, present)
            for p in present:
                if p in got:
                    pages[p] = got[p]
        snap[pid] = pages
    return snap

def measure(pids, base):
    st = dict(dirty_pages=0, new_pages=0, changed_bytes=0, delta_compressed=0,
              fullpage_compressed=0, zero_pages=0, unique_dirty=0, resident_pages_before=0,
              changed_bytes_hist={"<=16":0,"17-256":0,"257-2048":0,">2048":0})
    hashes = set()
    for pid in pids:
        bp = base.get(pid, {})
        st["resident_pages_before"] += len(bp)
        for a, b, _ in regions(pid):
            flags = pagemap_flags(pid, a, b)
            dirty = [p for p, v in flags.items() if (v >> 55 & 1) and (v >> 63 & 1)]
            if not dirty:
                continue
            got = read_mem(pid, dirty)
            for p in dirty:
                new = got.get(p)
                if new is None or len(new) != PAGE:
                    continue
                old = bp.get(p)
                if old is not None and old == new:
                    continue  # written but identical: costs nothing with content check
                st["dirty_pages"] += 1
                hashes.add(hashlib.blake2b(new, digest_size=16).digest())
                if new == bytes(PAGE):
                    st["zero_pages"] += 1
                st["fullpage_compressed"] += len(zlib.compress(new, 1))
                if old is None:
                    st["new_pages"] += 1
                    st["delta_compressed"] += len(zlib.compress(new, 1))
                    nb = PAGE
                else:
                    x = (int.from_bytes(old, "little") ^ int.from_bytes(new, "little")).to_bytes(PAGE, "little")
                    nb = PAGE - x.count(0)
                    st["delta_compressed"] += len(zlib.compress(x, 1))
                st["changed_bytes"] += nb
                h = st["changed_bytes_hist"]
                h["<=16" if nb <= 16 else "17-256" if nb <= 256 else "257-2048" if nb <= 2048 else ">2048"] += 1
    st["unique_dirty"] = len(hashes)
    st["dirty_bytes_naive_cow"] = st["dirty_pages"] * PAGE
    st["resident_bytes_before"] = st["resident_pages_before"] * PAGE
    return st

def cpu_ticks(pids):
    t = 0
    for pid in pids:
        for s in glob.glob(f"/proc/{pid}/task/*/stat"):
            try:
                f = open(s).read().rsplit(")", 1)[1].split()
                t += int(f[11]) + int(f[12])
            except Exception:
                pass
    return t

def thread_states(pids):
    st = []
    for pid in pids:
        for s in glob.glob(f"/proc/{pid}/task/*/stat"):
            try:
                st.append(open(s).read().rsplit(")", 1)[1].split()[0])
            except Exception:
                pass
    return st

HZ = os.sysconf("SC_CLK_TCK")

def run_task(pids, actions, quiet=0.5):
    """Execute actions, sample thread states every 2 ms until settled.
    Returns wall time to settle and CPU time and share of samples where every thread was asleep."""
    c0 = cpu_ticks(pids); t0 = time.monotonic()
    samples = asleep = 0
    for a in actions:
        if a[0] == "key": sh(f"xdotool key --delay 0 {a[1]}")
        elif a[0] == "type": sh(f"xdotool type --delay 20 '{a[1]}'")
        elif a[0] == "pause": time.sleep(a[1])
    t_act = time.monotonic()
    last_change = t_act; last = cpu_ticks(pids)
    while time.monotonic() - last_change < quiet:
        s = thread_states(pids); samples += 1
        if s and all(x in "S" for x in s): asleep += 1
        now = cpu_ticks(pids)
        if now != last: last = now; last_change = time.monotonic()
        time.sleep(0.002)
    settle = last_change - t0
    cpu = (cpu_ticks(pids) - c0) / HZ
    return dict(wall_to_settle_s=round(settle, 3), driver_s=round(t_act - t0, 3), cpu_s=round(cpu, 3),
                all_asleep_sample_share=round(asleep / max(samples, 1), 3))

def main():
    sh("pkill -x Xvfb; pkill -f soffice; sleep 1")
    subprocess.Popen("Xvfb :99 -screen 0 1280x800x24 -nolisten tcp", shell=True, env=ENV,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    subprocess.Popen("openbox", shell=True, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    work = "/tmp/exp1work"; sh(f"rm -rf {work}"); os.makedirs(work, exist_ok=True)
    with open(f"{work}/budget.csv", "w") as f:
        f.write("Item,Q1,Q2,Q3\n")
        for i in range(500):
            f.write(f"item{i},{i*3},{i*5},{i*7}\n")
    sh(f"cd {work} && soffice --headless --convert-to ods budget.csv", timeout=180)
    subprocess.Popen(f"soffice --calc --norestore --nologo {work}/budget.ods", shell=True, env=ENV,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(90):
        time.sleep(1)
        if "budget" in sh("xdotool search --name budget getwindowname").stdout: break
    time.sleep(8)
    wid = sh("xdotool search --name 'budget.ods'").stdout.split()[-1]
    shot = lambda tag: sh(f"xwd -root -silent | convert xwd:- {OUT}/{tag}.png")
    shot("start")
    sh(f"xdotool windowactivate --sync {wid}; xdotool windowfocus {wid}")
    pids = pids_of("soffice.bin") + pids_of("Xvfb")
    tasks = {
        "T1_edit_one_cell": [("key", "ctrl+Home"), ("key", "Right"), ("key", "Down"), ("type", "5000"), ("key", "Return")],
        "T2_type_50_values": sum([[("type", str(1000 + i)), ("key", "Return")] for i in range(50)], [("key", "ctrl+Home")] + [("key", "Right")] * 5),
        "T3_open_close_format_dialog": [("key", "ctrl+1"), ("pause", 1.5), ("key", "Escape")],
        "T4_bold_column": [("key", "ctrl+Home"), ("key", "ctrl+space"), ("key", "ctrl+b"), ("key", "ctrl+Home")],
        "T5_sort_like_scroll_1000_rows": [("key", "ctrl+End"), ("key", "ctrl+Home"), ("key", "Page_Down Page_Down Page_Down Page_Down")],
        "T6_save": [("key", "ctrl+s")],
    }
    results = {}
    mtime0 = os.path.getmtime(f"{work}/budget.ods")
    for name, acts in tasks.items():
        sh(f"xdotool windowactivate --sync {wid}; xdotool windowfocus --sync {wid}")
        time.sleep(0.5)
        base = snapshot(pids)
        timing = run_task(pids, acts)
        mem = measure(pids, base)
        results[name] = dict(timing=timing, memory=mem,
                             active_window_after=sh("xdotool getactivewindow getwindowname").stdout.strip())
        print(name, json.dumps(results[name]), flush=True)
        shot(name)
        del base
    time.sleep(2)
    saved = os.path.getmtime(f"{work}/budget.ods") > mtime0
    sh("pkill -f soffice; sleep 2")
    sh(f"cd {work} && rm -f check.csv && soffice --headless --convert-to csv:'Text - txt - csv (StarCalc)':44,34,76 --outdir {work}/chk budget.ods", timeout=180)
    rows = open(f"{work}/chk/budget.csv").read().splitlines() if os.path.exists(f"{work}/chk/budget.csv") else []
    check = dict(saved=saved,
                 B2=(rows[1].split(",")[1] if len(rows) > 1 else None),
                 F2_to_F6=[r.split(",")[5] if len(r.split(",")) > 5 else None for r in rows[1:6]])
    results["verification"] = check
    print("verification", json.dumps(check), flush=True)
    json.dump(results, open(f"{OUT}/results.json", "w"), indent=1)
    sh("pkill -f soffice; pkill -x Xvfb")

if __name__ == "__main__":
    main()
