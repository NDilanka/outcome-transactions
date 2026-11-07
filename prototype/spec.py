"""Outcome specifications: must predicates, footprint, and preserve (frame) conditions,
evaluated over a before-state directory and an after-state directory."""
import os, fnmatch
import readers as R

def target(before_file, after_file, ref):
    """Where a spec cell sits in the after-state: the cell with the row label and column header it had before."""
    if not (os.path.exists(before_file) and os.path.exists(after_file)):
        return None
    return R.find_anchor(after_file, R.anchor_of(before_file, ref))

def allowed_cells(before_file, after_file, refs):
    """The after-state addresses of the cells a spec allows to change, found by anchor."""
    return {a for a in (target(before_file, after_file, ref) for ref in refs) if a}

def evaluate(spec, before, after, noise=()):
    """noise: paths that a null control fork (same app, no task) also changed; they are
    app side effects, not outcomes, so they are neither checked nor committed."""
    reasons = []
    for p in spec["must"]:
        kind = p[0]
        if kind == "ods_cell":
            _, f, ref, op, val = p
            fp = os.path.join(after, f)
            addr = target(os.path.join(before, f), fp, ref)
            got = R.ods_cells(fp).get(addr, (None,))[0] if addr else None
            ok = got is not None and float(got) == float(val)
            if not ok: reasons.append(f"must {f}:{ref} == {val}, got {got} (anchored at {addr})")
        elif kind == "exists":
            if not os.path.exists(os.path.join(after, p[1])): reasons.append(f"must exist: {p[1]}")
        elif kind == "pdf_contains":
            fp = os.path.join(after, p[1])
            if not os.path.exists(fp) or p[2] not in R.pdf_text(fp): reasons.append(f"must: {p[1]} contains '{p[2]}'")
    b, a = R.tree_hashes(before), R.tree_hashes(after)
    changed = {k for k in set(b) | set(a) if b.get(k) != a.get(k) and k not in noise}
    for k in sorted(changed):
        if not any(fnmatch.fnmatch(k, pat) for pat in spec["footprint"]):
            reasons.append(f"footprint violation: {k} changed")
    for p in spec.get("preserve", []):
        if p[0] == "ods_cells_except":
            _, f, allowed = p
            fb, fa = os.path.join(before, f), os.path.join(after, f)
            if os.path.exists(fb) and os.path.exists(fa):
                cb, ca = R.ods_cells(fb), R.ods_cells(fa)
                for ref in sorted(R.changed_cells(fb, fa) - allowed_cells(fb, fa, allowed)):
                    reasons.append(f"preserve: {f}:{ref} changed {cb.get(ref)} -> {ca.get(ref)}")
                    if len(reasons) > 12: break
    return (len(reasons) == 0), reasons, sorted(changed)

def semantic_diff(before, after, spec):
    """Outcome-level summary used for agreement between forks."""
    d = {}
    for p in spec["must"]:
        if p[0] == "ods_cell":
            fb, fp = os.path.join(before, p[1]), os.path.join(after, p[1])
            addr = target(fb, fp, p[2])
            d[f"{p[1]}:{p[2]}"] = R.ods_cells(fp).get(addr, (None,))[0] if addr else None
    for p in spec.get("preserve", []):
        if p[0] == "ods_cells_except":
            fb, fa = os.path.join(before, p[1]), os.path.join(after, p[1])
            d["other_cells_changed"] = len(R.changed_cells(fb, fa) - allowed_cells(fb, fa, p[2]))
    return d
