#!/usr/bin/env python3
"""Outcome-transaction prototype: freeze a spec, mutation-test it, fork the workspace,
search in parallel forks behind an effect firewall, verify, check agreement, merge-check, commit."""
import os, sys, json, time, shutil, subprocess, threading, http.server, hashlib, urllib.request

CODE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CODE)
import readers as R, spec as SP

H = "/root/otx"
REAL, SNAP = f"{H}/real", f"{H}/snap"
LOG = []
MODE = sys.argv[2] if len(sys.argv) > 2 else "normal"
CONFLICT = MODE in ("conflict", "same_cell")
CLEAR = MODE == "clear_cell"
FAULT = MODE == "fault_postcommit"
T0 = time.monotonic()
def log(msg, **kw):
    e = dict(t=round(time.monotonic() - T0, 2), msg=msg, **kw); LOG.append(e); print(json.dumps(e), flush=True)

def run(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)

SPEC = {
    "request": "Q3 budget exported as PDF to out/q3.pdf, with B2 = 5000",
    "must": [("ods_cell", "budget.ods", "B2", "==", 5000), ("exists", "out/q3.pdf"), ("pdf_contains", "out/q3.pdf", "5000")],
    "footprint": ["budget.ods", "out/q3.pdf"],
    "preserve": [("ods_cells_except", "budget.ods", ["B2"])],
}
EXPECT = {
    "normal": dict(committed=True, level="verified"),
    "conflict": dict(committed=True, level="verified"),
    "same_cell": dict(outcome="true_conflict", committed=False),
    "clear_cell": dict(outcome="true_conflict", committed=False),
    "fault_postcommit": dict(committed=False, released=[], rolled_back=True),
}

def write_report(rep):
    rep["mismatches"] = {k: [v, rep.get(k)] for k, v in EXPECT.get(MODE, {}).items() if rep.get(k) != v}
    json.dump(rep, open(sys.argv[1], "w"), indent=1, default=str)
    run(f"umount {H}/views/*")
    if rep["mismatches"]:
        print("expectation failed", json.dumps(rep["mismatches"]), flush=True); sys.exit(1)

def abort(outcome, level, **kw):
    write_report(dict(mode=MODE, outcome=outcome, committed=False, released=[], level=level, rolled_back=False, log=LOG, **kw))

def sync_file(f, src_root):
    """Make REAL's copy of f match src_root's copy, or remove it if src_root has none."""
    src, dst = f"{src_root}/{f}", f"{REAL}/{f}"
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".otx"
        try:
            shutil.copy2(src, tmp); os.replace(tmp, dst)
        finally:
            if os.path.exists(tmp): os.remove(tmp)
    elif os.path.exists(dst):
        os.remove(dst)

def pdf_of(ws):
    prof = f"file:///tmp/lo_mut_{hashlib.md5(ws.encode()).hexdigest()[:8]}"
    run(f"cd {ws} && soffice -env:UserInstallation={prof} --headless --convert-to pdf --outdir out budget.ods && mv out/budget.pdf out/q3.pdf")

def mutation_test():
    """Negative tests: deliberately wrong outcomes in disposable copies must all be rejected;
    the positive control must pass. The spec is only trusted if every case behaves."""
    base = f"{H}/mut"; shutil.rmtree(base, ignore_errors=True); os.makedirs(base)
    cases = {}
    def mk(name, fn, expect):
        d = f"{base}/{name}"; shutil.copytree(SNAP, d); fn(d); cases[name] = (d, expect)
    mk("start_state", lambda d: None, False)
    mk("wrong_value", lambda d: (R.ods_set_cell(f"{d}/budget.ods", "B2", 500), pdf_of(d)), False)
    mk("no_pdf", lambda d: R.ods_set_cell(f"{d}/budget.ods", "B2", 5000), False)
    mk("collateral_cell", lambda d: (R.ods_set_cell(f"{d}/budget.ods", "B2", 5000), R.ods_set_cell(f"{d}/budget.ods", "C5", 1), pdf_of(d)), False)
    mk("outside_footprint", lambda d: (R.ods_set_cell(f"{d}/budget.ods", "B2", 5000), pdf_of(d), open(f"{d}/notes.txt", "a").write("x")), False)
    mk("positive_control", lambda d: (R.ods_set_cell(f"{d}/budget.ods", "B2", 5000), pdf_of(d)), True)
    results = {}
    for name, (d, expect) in cases.items():
        ok, reasons, _ = SP.evaluate(SPEC, SNAP, d)
        results[name] = dict(expected_pass=expect, passed=ok, correct=(ok == expect), reasons=reasons[:3])
    return results

class Sink(http.server.BaseHTTPRequestHandler):
    received = []
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        Sink.received.append(self.rfile.read(n).decode()); self.send_response(200); self.send_header("Content-Length", "0"); self.end_headers()
    def log_message(self, *a): pass

def fork_and_run(name, num, method, results, env=""):
    fd = f"{H}/forks/{name}"; os.makedirs(f"{fd}/upper"); os.makedirs(f"{fd}/work")
    outbox = f"{fd}/outbox.jsonl"; open(outbox, "w").close()
    inner = (f"mount -t overlay overlay -o lowerdir={SNAP},upperdir={fd}/upper,workdir={fd}/work {SNAP} && "
             f"mount -t tmpfs tmpfs /tmp && ip link set lo up && (python3 {CODE}/outbox.py {outbox} >/dev/null 2>&1 &) ; sleep 0.5; cd {SNAP} && "
             f"{env} FORK_ID={name} FORK_NUM={num} OTX_HOME={CODE} timeout 240 bash {CODE}/methods/{method}.sh")
    t = time.monotonic()
    # A PID namespace makes every process the fork started (proxy, X server, app) die with it,
    # so no straggler keeps the output pipes open.
    try:
        p = subprocess.run(["unshare", "--mount", "--net", "--pid", "--fork", "--kill-child", "bash", "-c", inner],
                           capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as e:
        p = subprocess.CompletedProcess(e.cmd, -9, "", "fork timed out")
    dur = time.monotonic() - t
    size = int(run(f"du -sb {fd}/upper | cut -f1").stdout or 0)
    held = [json.loads(l) for l in open(outbox) if l.strip()]
    results[name] = dict(method=method, rc=p.returncode, seconds=round(dur, 1), finished_at=round(time.monotonic() - T0, 2),
                         divergence_bytes=size, held_effects=held, stderr=p.stderr[-300:])
    log("fork finished", fork=name, method=method, seconds=round(dur, 1), divergence_bytes=size, held_effects=len(held))

def view_of(name):
    v = f"{H}/views/{name}"; os.makedirs(v, exist_ok=True)
    r = run(f"mount -t overlay overlay -o lowerdir={H}/forks/{name}/upper:{SNAP} {v}")
    if r.returncode: raise RuntimeError(r.stderr)
    return v

def main():
    run(f"umount {H}/views/* 2>/dev/null; pkill -x Xvfb; pkill -x soffice.bin; rm -rf {H}; mkdir -p {H}/forks {H}/views")
    run(f"python3 {CODE}/make_workspace.py {REAL}", check=True)
    log("workspace ready", files=sorted(R.tree_hashes(REAL)))
    sink = http.server.ThreadingHTTPServer(("127.0.0.1", 9900), Sink)
    threading.Thread(target=sink.serve_forever, daemon=True).start()

    # 1. Fork base: snapshot the live workspace, so the real one stays free to change.
    shutil.copytree(REAL, SNAP)
    base_hashes = R.tree_hashes(SNAP)
    spec_hash = hashlib.sha256(json.dumps(SPEC, sort_keys=True).encode()).hexdigest()[:12]
    log("spec frozen", spec_hash=spec_hash)

    # 2. Mutation-test the spec before any search.
    mt = mutation_test()
    log("spec mutation tests", results={k: (v["passed"], v["correct"]) for k, v in mt.items()})
    if not all(v["correct"] for v in mt.values()):
        log("spec rejected: a wrong outcome passed or the positive control failed")
        abort("spec_rejected", "none", mutation_tests=mt); return

    # 3. Search: parallel forks, each behind its own effect firewall (no network, held outbox).
    t_search = time.monotonic()
    methods = [("f1_gui", "gui"), ("f2_direct", "direct"), ("f3_roundtrip", "roundtrip"), ("f4_wrong", "wrong")]
    results = {}
    ths = [threading.Thread(target=fork_and_run, args=(n, i, m, results)) for i, (n, m) in enumerate(methods, 1)]
    # Null control fork: the same app opened and closed with no task. Whatever it changes
    # (lock files, caches, recent-file lists) is app noise, learned per run, not per app.
    control = {}
    ths.append(threading.Thread(target=fork_and_run, args=("f0_null", 9, "gui", control, "OTX_NULL=1")))
    for th in ths: th.start()
    # The user keeps working on the real machine during the search.
    time.sleep(3); open(f"{REAL}/notes.txt", "a").write("user typed this during the search\n")
    log("user edited real notes.txt during search")
    if CONFLICT:
        cell = "B2" if MODE == "same_cell" else "C3"
        R.ods_set_cell(f"{REAL}/budget.ods", cell, 77)
        log(f"user edited real budget.ods {cell} during search (same file as the task)")
    if CLEAR:
        R.ods_set_cell(f"{REAL}/budget.ods", "B2", None)
        log("user cleared real budget.ods B2 during search (same file as the task)")
    for th in ths: th.join()
    search_s = time.monotonic() - t_search
    nv = view_of("f0_null")
    nb, na = R.tree_hashes(SNAP), R.tree_hashes(nv)
    noise = {k for k in set(nb) | set(na) if nb.get(k) != na.get(k)}
    log("null control fork", noise=sorted(noise))

    # 4. Verify each fork against the frozen spec.
    passing = []
    for name in sorted(results, key=lambda n: results[n]["finished_at"]):
        v = view_of(name)
        ok, reasons, changed = SP.evaluate(SPEC, SNAP, v, noise)
        results[name].update(passed=ok, reasons=reasons[:4], changed=changed,
                             outcome=SP.semantic_diff(SNAP, v, SPEC) if os.path.exists(f"{v}/budget.ods") else None)
        log("verified", fork=name, passed=ok, reasons=reasons[:3])
        if ok: passing.append(name)

    # 5. Agreement between independent passing forks.
    outcomes = {n: json.dumps(results[n]["outcome"], sort_keys=True) for n in passing}
    agree = len(set(outcomes.values())) == 1 and len(passing) >= 2
    level = "verified" if agree else ("ambiguous" if len(set(outcomes.values())) > 1 else ("single" if passing else "none"))
    log("agreement", passing=passing, level=level)
    if not passing:
        log("no fork reached the outcome; nothing committed")
        abort("no_passing_fork", level, forks=results); return
    winner = passing[0]

    # 6. Merge check: did the user change anything inside the winner's footprint since the fork?
    now = R.tree_hashes(REAL)
    conflicts = [f for f in results[winner]["changed"] if now.get(f) != base_hashes.get(f)]
    log("merge check", winner=winner, conflicts=conflicts,
        user_changes_since_fork=[f for f in now if now.get(f) != base_hashes.get(f)])
    v = f"{H}/views/{winner}"
    replays = 0
    while conflicts:
        # Semantic merge test: the same file changed on both sides, but did the same cells?
        user_cells = R.changed_cells(f"{SNAP}/budget.ods", f"{REAL}/budget.ods")
        win_cells = R.changed_cells(f"{SNAP}/budget.ods", f"{v}/budget.ods")
        overlap = sorted(user_cells & win_cells)
        log("semantic merge test", user_cells=sorted(user_cells), winner_cells=sorted(win_cells), overlap=overlap)
        if overlap or replays >= 3:
            log("true conflict: show the user both versions; nothing committed",
                real_B2=R.ods_cells(f"{REAL}/budget.ods").get("B2"), held_effects_released=0)
            abort("true_conflict", level, overlap=overlap, forks=results)
            return
        # Disjoint edits: replay the winning method on a fresh fork of the current real state,
        # verify against the same frozen spec, and commit only if the real state did not move again.
        replays += 1
        run(f"umount {H}/views/*")
        shutil.rmtree(SNAP); shutil.copytree(REAL, SNAP); base_hashes = R.tree_hashes(SNAP)
        name = f"{winner}_replay{replays}"
        fork_and_run(name, 20 + replays, results[winner]["method"], results)
        v = view_of(name)
        ok, reasons, changed = SP.evaluate(SPEC, SNAP, v, noise)
        results[name].update(passed=ok, reasons=reasons[:4], changed=changed)
        log("replay verified", fork=name, passed=ok, reasons=reasons[:3])
        if not ok:
            log("replay failed the frozen spec; nothing committed")
            abort("replay_failed", level, forks=results); return
        winner = name
        now = R.tree_hashes(REAL)
        conflicts = [f for f in changed if now.get(f) != base_hashes.get(f)]

    # 7. Commit by result transplant, then re-verify on the real workspace.
    pre = f"{H}/precommit"; shutil.copytree(REAL, pre)
    moved = results[winner]["changed"]
    try:
        for f in moved: sync_file(f, v)
        if FAULT: R.ods_set_cell(f"{REAL}/budget.ods", "B2", 4999)
        ok, reasons, changed = SP.evaluate(SPEC, pre, REAL)
    except Exception as ex:
        ok, reasons, changed = False, [f"{type(ex).__name__}: {ex}"], []
    log("transplanted", winner=winner, post_commit_verified=ok, reasons=reasons, changed=changed)

    # 8. Release the winner's held effects only if the re-verify passed; otherwise restore the moved files and discard all.
    committed, rolled_back = ok, False
    if not committed:
        for f in moved: sync_file(f, pre)
        now, before = R.tree_hashes(REAL), R.tree_hashes(pre)
        rolled_back = all(now.get(f) == before.get(f) for f in moved)
    effects = results[winner]["held_effects"] if committed else []
    for e in effects:
        urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:9900/release", data=e["body"].encode(), method="POST"))
    discarded = sum(len(r["held_effects"]) for r in results.values()) - len(effects)
    log("effects released", released=list(Sink.received), discarded=discarded, rolled_back=rolled_back)

    report = dict(spec=SPEC, spec_hash=spec_hash, mutation_tests=mt, forks=results, null_control=dict(control, noise=sorted(noise)), winner=winner, level=level,
                  committed=committed, outcome="committed" if committed else "post_commit_failed", released=list(Sink.received), rolled_back=rolled_back,
                  search_seconds=round(search_s, 1), total_seconds=round(time.monotonic() - T0, 1),
                  real_notes_preserved="user typed this" in open(f"{REAL}/notes.txt").read(),
                  real_user_cell_preserved=(R.ods_cells(f"{REAL}/budget.ods").get("C3", (None,))[0] in ("77", 77, "77.0")) if CONFLICT else None,
                  replays=replays, log=LOG)
    write_report(report)
    sink.shutdown()

if __name__ == "__main__":
    main()
