"""Run each attempt's solve.py on a fresh copy of its starting file, with no network, and measure it.

For each attempt code (from the private map written by make_attempts.py):
  1. check the read-only starting copy is unchanged since generation;
  2. copy the starting copy and solve.py into EXEC/<code>/ (fresh, nothing else from work/);
  3. run `unshare -rn <interp> solve.py <target>` and sample the process tree every 20 ms:
     peak summed RSS, and CPU seconds per pid (last observed value; approximate for short-lived children);
  4. write EXEC/<code>/result.json (exit code, wall seconds, CPU seconds, peak RSS MB, input check, stderr tail).

Also records program generation time: solve.py mtime (last write) minus the wave start time in private/t0/.
Resumable: an attempt with an existing result.json is skipped unless --force.
"""
import glob, json, os, shutil, subprocess, sys, time
import psutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_attempts import sha256, tree_hash  # noqa: E402

PRIV = "/home/factory-user/exp8/private"
EXEC = "/home/factory-user/exp8/exec"
TIMEOUT_S = 300


def load_map():
    return {e["code"]: e for e in json.load(open(os.path.join(PRIV, "map.json")))}


def wave_start(code):
    """Start time of the wave that launched this attempt, from private/t0/waveN.txt (epoch seconds)."""
    for txt in glob.glob(os.path.join(PRIV, "t0", "wave*.txt")):
        if code in open(txt).read().split():
            base = txt[:-4]
            return float(open(base + ".time").read().strip())
    return None


def input_now(e):
    p = e["input_path"]
    return tree_hash(p) if os.path.isdir(p) else sha256(p)


def run_one(e, force=False):
    code = e["code"]
    out = os.path.join(EXEC, code)
    res_path = os.path.join(out, "result.json")
    if os.path.exists(res_path) and not force:
        return json.load(open(res_path))
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, "prog"))
    res = {"code": code, "short": e["short"], "condition": e["condition"], "method_idx": e["method_idx"]}
    solve = os.path.join(e["work"], "solve.py")
    res["has_solve_py"] = os.path.exists(solve)
    res["input_unchanged"] = input_now(e) == e["input_hash"]
    if not res["has_solve_py"]:
        # Not cached: the attempt may still be generating its program, so a later run must retry it.
        shutil.rmtree(out, ignore_errors=True)
        res.update(exit_code=None, status="NO_PROGRAM")
        return res
    t0 = wave_start(code)
    res["program_mtime"] = os.path.getmtime(solve)
    res["generation_s"] = (res["program_mtime"] - t0) if t0 else None
    done = os.path.join(e["work"], "DONE.txt")
    res["done_mtime"] = os.path.getmtime(done) if os.path.exists(done) else None
    shutil.copy2(solve, os.path.join(out, "prog", "solve.py"))
    target_dir = os.path.join(out, "target")
    os.makedirs(target_dir)
    if e["kind"] == "profile":
        target = os.path.join(target_dir, "user")
        shutil.copytree(e["input_path"], target)
    else:
        target = os.path.join(target_dir, e["file"])
        shutil.copy2(e["input_path"], target)
    cmd = ["unshare", "-rn", e["interp"], "solve.py", target]
    t_start = time.perf_counter()
    proc = subprocess.Popen(cmd, cwd=os.path.join(out, "prog"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    root = psutil.Process(proc.pid)
    peak_rss = 0
    cpu_last = {}
    timed_out = False
    while proc.poll() is None:
        try:
            procs = [root] + root.children(recursive=True)
            rss = 0
            for p in procs:
                try:
                    rss += p.memory_info().rss
                    ct = p.cpu_times()
                    cpu_last[p.pid] = ct.user + ct.system
                except psutil.Error:
                    pass
            peak_rss = max(peak_rss, rss)
        except psutil.Error:
            pass
        if time.perf_counter() - t_start > TIMEOUT_S:
            timed_out = True
            proc.kill()
            break
        time.sleep(0.02)
    stdout, stderr = proc.communicate()
    wall = time.perf_counter() - t_start
    # Kill any LibreOffice or helper still alive in this run's session.
    try:
        os.killpg(proc.pid, 9)
    except OSError:
        pass
    res.update(
        exit_code=proc.returncode,
        status="TIMEOUT" if timed_out else ("OK" if proc.returncode == 0 else "ERROR"),
        wall_s=round(wall, 3),
        cpu_s=round(sum(cpu_last.values()), 3),
        peak_rss_mb=round(peak_rss / 2**20, 1),
        stderr_tail=stderr.decode("utf-8", "replace")[-800:],
        stdout_tail=stdout.decode("utf-8", "replace")[-300:],
        end_state=target,
        end_hash=tree_hash(target) if os.path.isdir(target) else sha256(target),
    )
    json.dump(res, open(res_path, "w"), indent=1)
    return res


def main(argv):
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        print("usage: run_attempts.py [CODE ...] [--force]   (no CODE: all attempts in the map)")
        return
    force = "--force" in argv
    codes = [a for a in argv if not a.startswith("--")]
    m = load_map()
    targets = [m[c] for c in codes] if codes else list(m.values())
    for e in targets:
        r = run_one(e, force=force)
        print(r["code"], r.get("status"), "exit", r.get("exit_code"), "wall", r.get("wall_s"),
              "cpu", r.get("cpu_s"), "rssMB", r.get("peak_rss_mb"), "gen_s", r.get("generation_s") and round(r["generation_s"]),
              "input_ok", r.get("input_unchanged"))


if __name__ == "__main__":
    main(sys.argv[1:])
