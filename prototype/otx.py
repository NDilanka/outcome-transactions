#!/usr/bin/env python3
"""Outcome-transaction prototype: freeze a spec, mutation-test it, fork the workspace,
search in parallel forks behind an effect firewall, verify, check agreement, merge-check, commit."""
import os, sys, json, time, shutil, subprocess, threading, http.server, hashlib, traceback, urllib.request

CODE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CODE)
import readers as R, spec as SP

H = "/root/otx"
REAL, SNAP = f"{H}/real", f"{H}/snap"
LOG = []
TXN = {"committed": False}
MODE = sys.argv[2] if len(sys.argv) > 2 else "normal"
CONFLICT = MODE in ("conflict", "same_cell")
CLEAR = MODE == "clear_cell"
INSERT = MODE in ("insert_row", "insert_row_same_b2")
FAULT = MODE in ("fault_postcommit", "race_rollback")
RACE = MODE in ("race_commit", "race_rollback", "race_window")
WINDOW = MODE == "race_window"
READ_SET = MODE in ("read_set", "read_set_busy")
MAX_REPLAYS = 3  # replays of the winner on a newer state before the commit refuses as busy
T0 = time.monotonic()
def log(msg, **kw):
    e = dict(t=round(time.monotonic() - T0, 2), msg=msg, **kw); LOG.append(e); print(json.dumps(e), flush=True)

def run(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)

TARGET = "Q3!B2"  # the sheet and cell the spec is about
SPEC = {
    "request": "Q3 budget exported as PDF to out/q3.pdf, with B2 = 5000",
    "must": [("ods_cell", "budget.ods", TARGET, "==", 5000), ("exists", "out/q3.pdf"), ("pdf_contains", "out/q3.pdf", "5000")],
    "footprint": ["budget.ods", "out/q3.pdf"],
    "preserve": [("ods_cells_except", "budget.ods", [TARGET])],
}
EXPECT = {
    "normal": dict(committed=True, level="verified"),
    "conflict": dict(committed=True, level="verified"),
    "same_cell": dict(outcome="true_conflict", committed=False),
    "clear_cell": dict(outcome="true_conflict", committed=False),
    "fault_postcommit": dict(outcome="post_commit_failed", committed=False, released=[], rolled_back=True),
    "race_commit": dict(outcome="aborted_user_edit", committed=False, released=[], needs_user=[], user_c3_kept=True),
    "race_rollback": dict(outcome="post_commit_failed", committed=False, released=[], needs_user=["budget.ods"], user_c3_kept=True, rolled_back=False),
    "insert_row": dict(outcome="anchor_mismatch", committed=False, real_b2=None),
    "insert_row_same_b2": dict(outcome="anchor_mismatch", committed=False, real_b2="3"),
    "dup_label": dict(outcome="anchor_mismatch", committed=False, real_b2="3"),
    "race_window": dict(outcome="aborted_user_edit", committed=False, released=[], user_c3_kept=True),
    "dup_cached": dict(outcome="anchor_mismatch", committed=False, real_b2="3"),
    "dup_comment": dict(outcome="anchor_mismatch", committed=False, real_b2="3"),
    "dup_space": dict(outcome="anchor_mismatch", committed=False, real_b2="3"),
    "dup_spaces": dict(outcome="anchor_mismatch", committed=False, real_b2="3"),
    "list_label": dict(outcome="anchor_mismatch", committed=False, real_b2="3"),
    "merge_header": dict(outcome="anchor_mismatch", committed=False, real_b2="3"),
    "dup_sheet": dict(outcome="committed", committed=True, real_b2="5000", real_b2_by_sheet={"Q3": "5000", "Q3 copy": "3"}),
    "dup_sheet_renamed": dict(outcome="anchor_mismatch", committed=False, real_b2=None, real_b2_by_sheet={"FY2026": "3"}),
    "read_set": dict(committed=False, real_b2="3"),
    "read_set_busy": dict(outcome="document_busy", committed=False, real_b2="3", replays=3),
}

def sheet_b2s():
    """B2 of every sheet in the real workbook, by sheet name."""
    p = f"{REAL}/budget.ods"
    return {n: R.ods_cells(p, n).get("B2", (None,))[0] for n in R.sheet_names(p)}

def write_report(rep):
    rep["mismatches"] = {k: [v, rep.get(k)] for k, v in EXPECT.get(MODE, {}).items() if rep.get(k) != v}
    rep["shown_conversions"] = [dict(c, start=round(c["start"] - T0, 2)) for c in R.CONVERSIONS]
    json.dump(rep, open(sys.argv[1], "w"), indent=1, default=str)
    run(f"umount {H}/views/*")
    if rep["mismatches"]:
        print("expectation failed", json.dumps(rep["mismatches"]), flush=True); sys.exit(1)

def abort(outcome, level, **kw):
    write_report(dict(mode=MODE, outcome=outcome, committed=False, released=[], level=level, rolled_back=False, needs_user=[], log=LOG, **kw))

def fsha(p):
    return R.sha(p) if os.path.exists(p) else None

def sync_file(f, src_root, expect, landed, mutate=None, between=None):
    """Make REAL's copy of f match src_root's copy, or remove it if src_root has none. REAL is replaced only
    while it still holds sha `expect` (None: absent); landed[f] records the sha now in REAL (None if removed).
    The check and the replace are two steps: a user write in that window is overwritten. Returns False and
    leaves REAL alone when the check fails."""
    src, dst = f"{src_root}/{f}", f"{REAL}/{f}"
    tmp = dst + ".otx"
    try:
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, tmp)
            if mutate: mutate(tmp)
        if fsha(dst) != expect: return False
        if between: between()
        sha = fsha(tmp) if os.path.exists(src) else None
        if os.path.exists(src): os.replace(tmp, dst)
        elif os.path.exists(dst): os.remove(dst)
        landed[f] = sha
        return True
    finally:
        if os.path.exists(tmp): os.remove(tmp)

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
    if MODE == "dup_space":
        R.ods_replace_cell(f"{REAL}/budget.ods", "A2", '<table:table-cell office:value-type="string"><text:p>item 0</text:p></table:table-cell>')
        log("frozen target row relabelled 'item 0' before the fork")
    if READ_SET:
        open(f"{REAL}/notes.txt", "w").write("target 5000\n"); log("real notes.txt says target 5000 before the fork")
    sink = http.server.ThreadingHTTPServer(("127.0.0.1", 9900), Sink)
    threading.Thread(target=sink.serve_forever, daemon=True).start()

    # 1. Fork base: snapshot the live workspace, so the real one stays free to change.
    shutil.copytree(REAL, SNAP)
    base_hashes = R.tree_hashes(SNAP)
    spec_hash = hashlib.sha256(json.dumps(SPEC, sort_keys=True).encode()).hexdigest()[:12]
    log("spec frozen", spec_hash=spec_hash)
    # The spec's target cell, named by its row label and column header rather than by its address.
    anchor = R.anchor_of(f"{SNAP}/budget.ods", TARGET)
    target_addr = R.find_anchor(f"{SNAP}/budget.ods", anchor)
    log("target anchored", anchor=anchor, address=target_addr)

    # 2. Mutation-test the spec before any search.
    mt = mutation_test()
    log("spec mutation tests", results={k: (v["passed"], v["correct"]) for k, v in mt.items()})
    if not all(v["correct"] for v in mt.values()):
        log("spec rejected: a wrong outcome passed or the positive control failed")
        abort("spec_rejected", "none", mutation_tests=mt); return

    # 3. Search: parallel forks, each behind its own effect firewall (no network, held outbox).
    t_search = time.monotonic()
    methods = [("f1_gui", "gui"), ("f2_direct", "direct"), ("f3_roundtrip", "roundtrip"), ("f4_wrong", "wrong")]
    if READ_SET: methods = [("f2_derive", "derive"), ("f3_derive", "derive")]
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
    if MODE == "read_set":
        txt = open(f"{REAL}/notes.txt").read(); open(f"{REAL}/notes.txt", "w").write(txt.replace("target 5000", "target 4000", 1))
        log("user changed the target in real notes.txt from 5000 to 4000 during search; the fork read 5000 from its snapshot")
    if MODE == "read_set_busy":
        def typist():
            while True:
                time.sleep(0.5); open(f"{REAL}/notes.txt", "a").write("user typed this\n")
        threading.Thread(target=typist, daemon=True).start()
        log("user types into real notes.txt every 0.5 s from now on; no change to the target")
    if CONFLICT:
        cell = "B2" if MODE == "same_cell" else "C3"
        R.ods_set_cell(f"{REAL}/budget.ods", cell, 77)
        log(f"user edited real budget.ods {cell} during search (same file as the task)")
    if CLEAR:
        R.ods_set_cell(f"{REAL}/budget.ods", "B2", None)
        log("user cleared real budget.ods B2 during search (same file as the task)")
    if INSERT:
        R.ods_insert_row(f"{REAL}/budget.ods", 1); log("user inserted a row above row 2 in real budget.ods during search")
        if MODE == "insert_row_same_b2":
            R.ods_set_cell(f"{REAL}/budget.ods", "B2", 3); log("user typed 3 into the new B2")
    if MODE == "dup_label":
        R.ods_append_block(f"{REAL}/budget.ods", "item0", 1001); log("user pasted 1001 identical rows labelled item0 below the data during search")
    if MODE == "dup_cached":
        R.ods_append_rows(f"{REAL}/budget.ods", '<table:table-row table:number-rows-repeated="1001"><table:table-cell office:value-type="string" office:string-value="item0"/></table:table-row>')
        log("user pasted 1001 identical rows labelled item0 with cached string values and no text, during search")
    if MODE == "dup_comment":
        R.ods_append_rows(f"{REAL}/budget.ods", '<table:table-row><table:table-cell office:value-type="string"><office:annotation><text:p>note</text:p></office:annotation><text:p>item0</text:p></table:table-cell></table:table-row>')
        log("user pasted a row labelled item0 whose label cell carries a comment, during search")
    if MODE == "dup_space":
        R.ods_append_rows(f"{REAL}/budget.ods", '<table:table-row><table:table-cell office:value-type="string"><text:p>item<text:s/>0</text:p></table:table-cell></table:table-row>')
        log("user pasted a row labelled 'item 0' with a text:s space, during search")
    if MODE == "dup_sheet":
        R.ods_copy_sheet_first(f"{REAL}/budget.ods", "Q3 copy"); log("user copied sheet Q3 and moved the copy ahead of it, during search")
    if MODE == "dup_sheet_renamed":
        R.ods_rename_sheet(f"{REAL}/budget.ods", "Q3", "FY2026"); log("user renamed sheet Q3 to FY2026 during search")
    if MODE == "dup_spaces":
        R.ods_append_rows(f"{REAL}/budget.ods", '<table:table-row><table:table-cell office:value-type="string"><text:p> item0 </text:p></table:table-cell></table:table-row>')
        log("user pasted a row labelled ' item0 ' with spaces around the text, during search")
    if MODE == "list_label":
        R.ods_replace_cell(f"{REAL}/budget.ods", "A2", '<table:table-cell office:value-type="string"><text:list text:style-name="L"><text:list-item><text:p>item0</text:p></text:list-item></text:list></table:table-cell>')
        log("user turned the target row label 'item0' into a list item during search")
    if MODE == "merge_header":
        R.ods_replace_cell(f"{REAL}/budget.ods", "B1", '<table:table-cell table:number-columns-spanned="2" office:value-type="string"><text:p>Q1</text:p></table:table-cell>')
        R.ods_replace_cell(f"{REAL}/budget.ods", "C1", '<table:covered-table-cell/>')
        log("user merged the header cells B1 and C1 in real budget.ods during search")
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
    # Each pass copies the real state first. That copy is the transplant baseline, so the check and the commit see the same state.
    v = f"{H}/views/{winner}"
    replays = 0
    while True:
        pre = f"{H}/precommit"; shutil.rmtree(pre, ignore_errors=True); shutil.copytree(REAL, pre)
        now = R.tree_hashes(pre)
        # The winner read its whole snapshot, not only the files it wrote (a derived method reads notes.txt and
        # writes budget.ods), so any user change since the snapshot makes its result stale. It replays on the current state.
        conflicts = sorted(f for f in set(now) | set(base_hashes) if now.get(f) != base_hashes.get(f))
        log("merge check", winner=winner, conflicts=conflicts)
        # The winner wrote the cell its row label and column header name in its own copy. If the user moved
        # either one, the transplant would write a different cell, so refuse.
        base_addr, now_addr = R.find_anchor(f"{SNAP}/budget.ods", anchor), R.find_anchor(f"{pre}/budget.ods", anchor)
        if now_addr != base_addr:
            log("anchor moved: the target row or column changed; nothing committed", anchor=anchor, was=base_addr, now=now_addr)
            abort("anchor_mismatch", level, anchor=anchor, base_address=base_addr, now_address=now_addr,
                  real_b2=R.all_cells(f"{REAL}/budget.ods").get(target_addr, (None,))[0], real_b2_by_sheet=sheet_b2s(), forks=results)
            return
        if not conflicts: break
        # Semantic merge test: the same file changed on both sides, but did the same cells?
        user_cells = R.changed_cells(f"{SNAP}/budget.ods", f"{pre}/budget.ods")
        win_cells = R.changed_cells(f"{SNAP}/budget.ods", f"{v}/budget.ods")
        overlap = sorted(user_cells & win_cells)
        log("semantic merge test", user_cells=sorted(user_cells), winner_cells=sorted(win_cells), overlap=overlap)
        if overlap:
            log("true conflict: show the user both versions; nothing committed",
                real_B2=R.all_cells(f"{REAL}/budget.ods").get(target_addr), held_effects_released=0)
            abort("true_conflict", level, overlap=overlap, forks=results)
            return
        if replays >= MAX_REPLAYS:
            log("document busy: every replay lost to a newer user edit; nothing committed", replays=replays)
            abort("document_busy", level, replays=replays, message="document busy, try again", forks=results,
                  real_b2=R.all_cells(f"{REAL}/budget.ods").get(target_addr, (None,))[0])
            return
        # Disjoint edits: replay the winning method on a fresh fork of the current real state,
        # verify against the same frozen spec, and commit only if the real state did not move again.
        replays += 1
        run(f"umount {H}/views/*")
        shutil.rmtree(SNAP); shutil.copytree(pre, SNAP); base_hashes = R.tree_hashes(SNAP)
        name = f"{winner}_replay{replays}"
        fork_and_run(name, 20 + replays, results[winner]["method"], results)
        v = view_of(name)
        ok, reasons, changed = SP.evaluate(SPEC, SNAP, v, noise)
        results[name].update(passed=ok, reasons=reasons[:4], changed=changed)
        log("replay verified", fork=name, passed=ok, reasons=reasons[:3])
        if not ok:
            log("replay failed the frozen spec; nothing committed")
            abort("replay_failed", level, forks=results, real_b2=R.all_cells(f"{REAL}/budget.ods").get(target_addr, (None,))[0]); return
        winner = name

    # 7. Commit by result transplant, then re-verify on the real workspace.
    if MODE == "race_commit":
        R.ods_set_cell(f"{REAL}/budget.ods", "C3", 77); log("user edited real budget.ods C3 after the precommit copy")
    def user_in_window():
        R.ods_set_cell(f"{REAL}/budget.ods", "C3", 77); log("user edited real budget.ods C3 between the check and the replace")
    moved = results[winner]["changed"]
    mutate = {"budget.ods": lambda p: R.ods_set_cell(p, "B2", 4999)} if FAULT else {}
    landed, edited = {}, None
    try:
        for f in moved:
            if not sync_file(f, v, fsha(f"{pre}/{f}"), landed, mutate.get(f), between=user_in_window if WINDOW and f == "budget.ods" else None):
                edited = f; break
        ok, reasons, changed = (False, [f"user edited {edited} during the transplant"], []) if edited else SP.evaluate(SPEC, pre, REAL)
    except Exception as ex:
        ok, reasons, changed = False, [f"{type(ex).__name__}: {ex}"], []
    committed = TXN["committed"] = ok
    log("transplanted", winner=winner, post_commit_verified=ok, reasons=reasons, changed=changed)

    # 8. Release the winner's held effects only if the re-verify passed; otherwise put back the files this commit landed.
    outcome = "committed" if committed else ("aborted_user_edit" if edited else "post_commit_failed")
    needs_user, rolled_back = [], False
    if not committed:
        if MODE == "race_rollback":
            R.ods_set_cell(f"{REAL}/budget.ods", "C3", 77); log("user edited real budget.ods C3 before the rollback")
        for f in landed:
            try:
                restored = sync_file(f, pre, landed[f], {})
            except Exception as ex:
                restored = False; log("restore failed", file=f, error=f"{type(ex).__name__}: {ex}")
            if not restored: needs_user.append(f)
        rolled_back = not needs_user and all(fsha(f"{REAL}/{f}") == fsha(f"{pre}/{f}") for f in moved)
    effects = results[winner]["held_effects"] if committed else []
    try:
        for e in effects:
            urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:9900/release", data=e["body"].encode(), method="POST"))
    except Exception as ex:
        outcome = "committed_release_failed"; log("effect release failed", error=f"{type(ex).__name__}: {ex}")
    discarded = sum(len(r["held_effects"]) for r in results.values()) - len(effects)
    log("effects released", released=list(Sink.received), discarded=discarded, rolled_back=rolled_back)

    report = dict(spec=SPEC, spec_hash=spec_hash, mutation_tests=mt, forks=results, null_control=dict(control, noise=sorted(noise)), winner=winner, level=level,
                  committed=committed, outcome=outcome, released=list(Sink.received), rolled_back=rolled_back, needs_user=needs_user,
                  search_seconds=round(search_s, 1), total_seconds=round(time.monotonic() - T0, 1), replays=replays, log=LOG)
    try:
        report.update(real_notes_preserved="user typed this" in open(f"{REAL}/notes.txt").read(),
                      user_c3_kept=(R.all_cells(f"{REAL}/budget.ods").get("Q3!C3", (None,))[0] in ("77", 77, "77.0")) if CONFLICT or RACE else None,
                      real_b2=R.all_cells(f"{REAL}/budget.ods").get(target_addr, (None,))[0], real_b2_by_sheet=sheet_b2s())
    except Exception as ex:
        log("report state unreadable", error=f"{type(ex).__name__}: {ex}")
    write_report(report)
    sink.shutdown()

if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        traceback.print_exc()
        write_report(dict(mode=MODE, outcome="error", error=f"{type(ex).__name__}: {ex}", committed=TXN["committed"], released=list(Sink.received), rolled_back=False, needs_user=[], log=LOG))
        sys.exit(1)
