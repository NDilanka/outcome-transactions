"""Outcome specifications: must predicates, footprint, and preserve (frame) conditions,
evaluated over a before-state directory and an after-state directory."""
import os, fnmatch
import readers as R

def evaluate(spec, before, after, noise=()):
    """noise: paths that a null control fork (same app, no task) also changed; they are
    app side effects, not outcomes, so they are neither checked nor committed."""
    reasons = []
    for p in spec["must"]:
        kind = p[0]
        if kind == "ods_cell":
            _, f, ref, op, val = p
            fp = os.path.join(after, f)
            got = R.ods_cells(fp).get(ref, (None,))[0] if os.path.exists(fp) else None
            ok = got is not None and float(got) == float(val)
            if not ok: reasons.append(f"must {f}:{ref} == {val}, got {got}")
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
                for ref in sorted(set(cb) | set(ca)):
                    if ref in allowed: continue
                    if cb.get(ref) != ca.get(ref):
                        reasons.append(f"preserve: {f}:{ref} changed {cb.get(ref)} -> {ca.get(ref)}")
                        if len(reasons) > 12: break
    return (len(reasons) == 0), reasons, sorted(changed)

def semantic_diff(before, after, spec):
    """Outcome-level summary used for agreement between forks."""
    d = {}
    for p in spec["must"]:
        if p[0] == "ods_cell":
            fp = os.path.join(after, p[1])
            d[f"{p[1]}:{p[2]}"] = R.ods_cells(fp).get(p[2], (None,))[0] if os.path.exists(fp) else None
    for p in spec.get("preserve", []):
        if p[0] == "ods_cells_except":
            fb, fa = os.path.join(before, p[1]), os.path.join(after, p[1])
            cb, ca = R.ods_cells(fb), R.ods_cells(fa)
            d["other_cells_changed"] = sum(1 for k in set(cb) | set(ca) if k not in p[2] and cb.get(k) != ca.get(k))
    return d
