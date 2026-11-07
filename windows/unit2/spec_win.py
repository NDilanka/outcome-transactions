"""Outcome specs for xlsx workspaces: must predicates, footprint, and preserve (frame) conditions,
evaluated over a before directory and an after directory. Port of prototype/spec.py with xlsx cells."""
import fnmatch
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "unit1"))
import otx_win  # noqa: E402
from backend import tree_hashes  # noqa: E402

READ_ERRORS = (zipfile.BadZipFile, KeyError, ET.ParseError, ValueError, IndexError, OSError)


def _cells(path):
    """Cells of the first sheet, or None when the file is missing or unreadable as xlsx."""
    if not os.path.exists(path):
        return None
    try:
        return otx_win.xlsx_cells(path)
    except READ_ERRORS:
        return None


def _text(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _must(p, after):
    kind = p[0]
    if kind == "xlsx_cell":
        _, f, ref, _, val = p
        got = (_cells(os.path.join(after, f)) or {}).get(ref)
        if isinstance(got, float) and got == float(val):
            return []
        return [f"must {f}:{ref} == {val}, got {got!r}"]
    if kind == "exists":
        return [] if os.path.exists(os.path.join(after, p[1])) else [f"must exist: {p[1]}"]
    if kind == "file_contains":
        fp = os.path.join(after, p[1])
        if os.path.exists(fp) and p[2] in _text(fp):
            return []
        return [f"must: {p[1]} contains '{p[2]}'"]
    raise ValueError(f"unknown must predicate {kind!r}")


def _preserve(p, before, after):
    if p[0] != "xlsx_cells_except":
        raise ValueError(f"unknown preserve predicate {p[0]!r}")
    _, f, allowed = p
    fb, fa = os.path.join(before, f), os.path.join(after, f)
    if not (os.path.exists(fb) and os.path.exists(fa)):
        return []
    cb, ca = _cells(fb), _cells(fa)
    if cb is None or ca is None:
        return [f"preserve: {f} unreadable"]
    return [f"preserve: {f}:{ref} changed {cb.get(ref)} -> {ca.get(ref)}"
            for ref in sorted(set(cb) | set(ca)) if ref not in allowed and cb.get(ref) != ca.get(ref)]


def _footprint(patterns, changed):
    return [f"footprint violation: {k} changed" for k in sorted(changed)
            if not any(fnmatch.fnmatch(k, pat) for pat in patterns)]


def evaluate(spec, before, after, noise=()):
    """noise: paths that a null control fork also changed. They are app side effects, so they are
    neither checked nor committed."""
    reasons = []
    for p in spec["must"]:
        reasons += _must(p, after)
    b, a = tree_hashes(before), tree_hashes(after)
    changed = {k for k in set(b) | set(a) if b.get(k) != a.get(k) and k not in noise}
    reasons += _footprint(spec["footprint"], changed)
    for p in spec.get("preserve", []):
        reasons += _preserve(p, before, after)
    return not reasons, reasons, sorted(changed)


def semantic_diff(before, after, spec):
    """Outcome-level summary used for agreement between forks."""
    d = {}
    for p in spec["must"]:
        if p[0] == "xlsx_cell":
            d[f"{p[1]}:{p[2]}"] = (_cells(os.path.join(after, p[1])) or {}).get(p[2])
    for p in spec.get("preserve", []):
        if p[0] == "xlsx_cells_except":
            cb = _cells(os.path.join(before, p[1])) or {}
            ca = _cells(os.path.join(after, p[1])) or {}
            d["other_cells_changed"] = sum(1 for k in set(cb) | set(ca) if k not in p[2] and cb.get(k) != ca.get(k))
    return d


def _changed_refs(a, b):
    return {k for k in set(a) | set(b) if a.get(k) != b.get(k)}


def merge_test(base_xlsx, user_xlsx, winner_xlsx):
    """Cell-level overlap between the user's edits and the winner's edits, both measured from the snapshot."""
    base = otx_win.xlsx_cells(base_xlsx)
    user = _changed_refs(base, otx_win.xlsx_cells(user_xlsx))
    win = _changed_refs(base, otx_win.xlsx_cells(winner_xlsx))
    overlap = sorted(user & win)
    return dict(outcome="true_conflict" if overlap else "no_conflict", overlap=overlap,
                user_cells=sorted(user), winner_cells=sorted(win))
