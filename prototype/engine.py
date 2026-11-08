"""Commit engine: one transaction. Fork the work, verify each fork against the frozen spec, agree on the result,
check the merge against the live resource, commit by transplant, verify what landed, then release the held effects
or put back what landed. Format-free: an adapter does the operations on one kind of state, a verifier judges views,
and hooks name the stages where a scenario may act. Outcomes, levels and the adapter protocol come from contract.

Status: drafted in unit 0.2, not run. The scenario harness does not call it yet."""
import json, threading, time
import contract as C

MAX_REPLAYS = 3  # replays of the winner on a newer state before the commit refuses as busy


class Log:
    """Run log: each entry is printed as a JSON line and kept for the report. Times are from the run's start."""
    def __init__(self):
        self.start = time.monotonic(); self.entries = []

    def __call__(self, msg, **kw):
        e = dict(t=round(time.monotonic() - self.start, 2), msg=msg, **kw)
        self.entries.append(e); print(json.dumps(e), flush=True)

    def elapsed(self):
        return time.monotonic() - self.start


class Txn:
    """What the commit has done. The failure handler reads it to decide what to put back."""
    def __init__(self):
        self.started = False; self.committed = False; self.pre = None; self.moved = []; self.landed = {}

    def start(self, pre, moved, landed):
        self.started = True; self.pre = pre; self.moved = moved; self.landed = landed


# Guards. Each invariant rests on one of these; the invariant tests remove or weaken them to check that the tests fail.

def conflicting_files(base, now):
    """Files that differ from the snapshot. The winner read its whole snapshot, so any such file makes its result stale."""
    return sorted(f for f in set(now) | set(base) if now.get(f) != base.get(f))


def overlapping(user_units, win_units):
    """Units that both the user and the winner changed."""
    return sorted(set(user_units) & set(win_units))


def anchor_moved(base_addr, now_addr):
    """The unit the winner wrote is no longer the unit it was verified against."""
    return now_addr != base_addr


def replay_allowed(replays):
    return replays < MAX_REPLAYS


def unit_changes(adapter, before, after):
    """Units that differ between two roots. An unreadable unit raises: it is never read as unchanged."""
    return adapter.changed_units(before, after)


def write_allowed(owner):
    """With owner detection, a write is allowed only when nothing owns the resource."""
    return owner is None


def effects_to_release(results, winner, committed):
    """Only the winner's held effects, and only once the commit stands."""
    return results[winner]["held_effects"] if committed else []


def exit_code(rep):
    """The process exit status, from the outcome. 0 committed; 2 refused or busy, nothing committed; 3 failed after
    the commit started and every landed unit was put back; 4 a unit needs the user; 5 the commit stands but a release
    or a later step failed; 1 other."""
    o = rep.get("outcome")
    if o == C.COMMITTED: return 0
    if o == C.COMMITTED_RELEASE_FAILED or (o == C.ERROR and rep.get("committed") is True): return 5
    if rep.get("needs_user"): return 4
    if o in C.REFUSALS: return 2
    if o in (C.POST_COMMIT_FAILED, C.ERROR) and rep.get("rolled_back") is True: return 3
    return 1


def restore(adapter, hooks, pre, landed, moved, log):
    """Put back, from the precommit copy, every unit this commit landed. A unit already as it was before the commit
    needs nothing. Returns (the units the user must fix, whether the live resource now matches the precommit copy)."""
    live = adapter.live()
    needs_user = []
    for f in landed:
        if adapter.fingerprint(live, f) == adapter.fingerprint(pre, f): continue
        try:
            hooks.at("rollback", unit=f)
            restored = adapter.revert(f, pre, landed[f])
        except Exception as ex:
            restored = False; log("restore failed", unit=f, error=f"{type(ex).__name__}: {ex}")
        if not restored: needs_user.append(f)
    return needs_user, not needs_user and all(adapter.fingerprint(live, f) == adapter.fingerprint(pre, f) for f in moved)


def state_of(hooks, log):
    """Values of the real resource for the report. A state that cannot be read is reported as missing, not as a crash."""
    try:
        return hooks.state()
    except Exception as ex:
        log("report state unreadable", error=f"{type(ex).__name__}: {ex}")
        return {}


def failure_report(txn, adapter, hooks, log, ex):
    """The report for an unexpected failure. Before the commit starts the real resource is untouched: a refusal.
    After it starts, put back what landed and say what could not be put back."""
    rep = dict(error=f"{type(ex).__name__}: {ex}", committed=txn.committed, commit_started=txn.started,
               released=adapter.released(), log=log.entries)
    if not txn.started:
        rep.update(outcome=C.REFUSED_ERROR, rolled_back=False, needs_user=[])
    elif txn.committed:
        rep.update(outcome=C.ERROR, rolled_back=False, needs_user=[])
    else:
        try:
            needs_user, rolled_back = restore(adapter, hooks, txn.pre, txn.landed, txn.moved, log)
        except Exception as ex2:
            needs_user, rolled_back = sorted(txn.landed), False
            log("restore failed in the error handler", error=f"{type(ex2).__name__}: {ex2}")
        rep.update(outcome=C.ERROR, rolled_back=rolled_back, needs_user=needs_user)
    return rep


def run(adapter, verifier, hooks, log, txn):
    """One transaction. Returns the report. An unexpected exception propagates; the caller builds failure_report from txn."""
    plan = hooks.plan()
    hooks.at("prepare")
    adapter.start_channel()
    snap = adapter.snapshot()
    base_hashes = adapter.hashes(snap)
    log("spec frozen", spec_hash=verifier.spec_hash)
    # The spec's target cell is named by its anchor (identity), not by its address.
    anchor = adapter.anchor(snap, verifier.target)
    target_addr = adapter.resolve(anchor, snap)
    log("target anchored", anchor=anchor, address=target_addr)

    def abort(outcome, level, **kw):
        return dict(outcome=outcome, committed=False, released=[], level=level, rolled_back=False, needs_user=[], log=log.entries, **kw)

    # Mutation-test the spec before any search.
    mt = verifier.self_test(snap, adapter.scratch("mut"))
    log("spec mutation tests", results={k: (v["passed"], v["correct"]) for k, v in mt.items()})
    if not all(v["correct"] for v in mt.values()):
        log("spec rejected: a wrong outcome passed or the positive control failed")
        return abort(C.SPEC_REJECTED, "none", mutation_tests=mt)

    # Search: each fork runs in its own private workspace with its effects held, plus a null control fork.
    t_search = log.elapsed()
    results, control = {}, {}
    ths = [threading.Thread(target=adapter.fork, args=(n, i, m, results)) for i, (n, m) in enumerate(plan["forks"], 1)]
    null = plan["null"]
    if null:
        ths.append(threading.Thread(target=adapter.fork, args=(null["name"], null["num"], null["method"], control, null["env"])))
    for th in ths: th.start()
    hooks.at("fork")
    for th in ths: th.join()
    search_s = log.elapsed() - t_search
    if null:
        nb, na = adapter.hashes(snap), adapter.hashes(adapter.view(null["name"]))
        noise = {k for k in set(nb) | set(na) if nb.get(k) != na.get(k)}
    else:
        noise = set()
    log("null control fork", noise=sorted(noise))

    # Verify each fork against the frozen spec.
    passing, views = [], {}
    for name in sorted(results, key=lambda n: results[n]["finished_at"]):
        hooks.at("verify", fork=name)
        v = views[name] = adapter.view(name)
        ok, reasons, changed = verifier.evaluate(snap, v, noise)
        results[name].update(passed=ok, reasons=reasons[:4], changed=changed, outcome=verifier.summary(snap, v))
        log("verified", fork=name, passed=ok, reasons=reasons[:3])
        if ok: passing.append(name)

    # Agreement between independent passing forks.
    outcomes = {n: json.dumps(results[n]["outcome"], sort_keys=True) for n in passing}
    agree = len(set(outcomes.values())) == 1 and len(passing) >= 2
    level = C.VERIFIED if agree else (C.AMBIGUOUS if len(set(outcomes.values())) > 1 else (C.SINGLE if passing else C.NONE))
    log("agreement", passing=passing, level=level)
    if not passing:
        log("no fork reached the outcome; nothing committed")
        return abort(C.NO_PASSING_FORK, level, forks=results)
    winner = passing[0]

    # Merge check: did the user change anything the winner read, since the snapshot? Each pass copies the live
    # resource first; that copy is the transplant baseline, so the check and the commit see the same state.
    v = views[winner]
    replays = 0
    while True:
        hooks.at("merge")
        pre = adapter.precommit()
        now = adapter.hashes(pre)
        conflicts = conflicting_files(base_hashes, now)
        log("merge check", winner=winner, conflicts=conflicts)
        # The winner wrote the unit its anchor names in its own copy. If the user moved the anchor, the transplant
        # would write a different unit, so refuse.
        base_addr, now_addr = adapter.resolve(anchor, snap), adapter.resolve(anchor, pre)
        if anchor_moved(base_addr, now_addr):
            log("anchor moved: the target row or column changed; nothing committed", anchor=anchor, was=base_addr, now=now_addr)
            return abort(C.ANCHOR_MISMATCH, level, anchor=anchor, base_address=base_addr, now_address=now_addr,
                         **state_of(hooks, log), forks=results)
        if not conflicts: break
        # Semantic merge test: the same file changed on both sides, but did the same units?
        user_units = unit_changes(adapter, snap, pre)
        win_units = unit_changes(adapter, snap, v)
        overlap = overlapping(user_units, win_units)
        log("semantic merge test", user_units=sorted(user_units), winner_units=sorted(win_units), overlap=overlap)
        if overlap:
            log("true conflict: show the user both versions; nothing committed", held_effects_released=0)
            return abort(C.TRUE_CONFLICT, level, overlap=overlap, forks=results)
        if not replay_allowed(replays):
            log("document busy: every replay lost to a newer user edit; nothing committed", replays=replays)
            return abort(C.DOCUMENT_BUSY, level, replays=replays, message="document busy, try again", forks=results,
                         **state_of(hooks, log))
        # Disjoint edits: replay the winning method on a fresh fork of the current state, verify it against the same
        # frozen spec, and commit only if the state did not move again.
        replays += 1
        adapter.release_views()
        adapter.reset_snapshot(pre)
        base_hashes = adapter.hashes(snap)
        name = f"{winner}_replay{replays}"
        adapter.fork(name, 20 + replays, results[winner]["method"], results)
        hooks.at("replay", fork=name)
        v = adapter.view(name)
        ok, reasons, changed = verifier.evaluate(snap, v, noise)
        results[name].update(passed=ok, reasons=reasons[:4], changed=changed)
        log("replay verified", fork=name, passed=ok, reasons=reasons[:3])
        if not ok:
            log("replay failed the frozen spec; nothing committed")
            return abort(C.REPLAY_FAILED, level, forks=results, **state_of(hooks, log))
        winner = name

    # Owner check: where the adapter can see owners, nothing may write behind a live or unknown one.
    if adapter.capabilities.owner_detection == "required" and not write_allowed(adapter.owner(adapter.live())):
        log("the resource has an owner; nothing committed")
        return abort(C.REFUSED_OWNER, level, forks=results)

    # Commit by transplant of the winner's changed units, then verify the live resource.
    hooks.at("before_apply")
    moved = results[winner]["changed"]
    landed, edited = {}, None
    txn.start(pre, moved, landed)  # the failure handler puts back what landed from these
    try:
        for f in moved:
            if not adapter.apply(f, v, adapter.fingerprint(pre, f), landed):
                edited = f; break
            hooks.at("transplant", unit=f)
        hooks.at("post_verify")
        ok, reasons, changed = ((False, [f"user edited {edited} during the transplant"], [])
                                if edited else verifier.evaluate(pre, adapter.live()))
    except Exception as ex:
        ok, reasons, changed = False, [f"{type(ex).__name__}: {ex}"], []
    committed = txn.committed = ok
    log("transplanted", winner=winner, post_commit_verified=ok, reasons=reasons, changed=changed)

    # Release the winner's held effects only if the verify passed; otherwise put back what this commit landed.
    outcome = C.COMMITTED if committed else (C.ABORTED_USER_EDIT if edited else C.POST_COMMIT_FAILED)
    needs_user, rolled_back = [], False
    if not committed:
        hooks.at("before_rollback")
        needs_user, rolled_back = restore(adapter, hooks, pre, landed, moved, log)
    effects = effects_to_release(results, winner, committed)
    try:
        hooks.at("release")
        for e in effects:
            adapter.release(e)
    except Exception as ex:
        outcome = C.COMMITTED_RELEASE_FAILED; log("effect release failed", error=f"{type(ex).__name__}: {ex}")
    discarded = sum(len(r["held_effects"]) for r in results.values()) - len(effects)
    log("effects released", released=adapter.released(), discarded=discarded, rolled_back=rolled_back)
    hooks.at("report")  # outside every try: a failure here comes after the commit has started

    report = dict(spec=verifier.spec, spec_hash=verifier.spec_hash, mutation_tests=mt, forks=results,
                  null_control=dict(control, noise=sorted(noise)), winner=winner, level=level, committed=committed,
                  outcome=outcome, released=adapter.released(), rolled_back=rolled_back, needs_user=needs_user,
                  isolation=adapter.capabilities.isolation, search_seconds=round(search_s, 1),
                  total_seconds=round(log.elapsed(), 1), replays=replays, log=log.entries)
    report.update(state_of(hooks, log))
    return report
