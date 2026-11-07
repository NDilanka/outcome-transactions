"""Generic semantic diff over two directory states, plus save-noise subtraction.

Changes are reported at the finest unit: the leaf path inside a file's canonical tree (a cell's value, a run's
colour, a shape's position, a layer's offsets, a settings key). The unit is the record that holds the leaf.

Verdicts for "nothing else changed" fail closed:
  FAIL        a change outside the allowed scope was found (a proven change)
  UNVERIFIED  no violation was found, but some file in scope could not be read (unreadable or derived)
  PASS        every change is allowed and every file was read
An unreadable file is never reported as unchanged, even when its bytes are identical.
"""
import numpy as np

from . import readers_image


class Change:
    __slots__ = ('path', 'kind', 'before', 'after', 'unit', 'region')

    def __init__(self, path, kind, before, after, region=None):
        self.path = path
        self.kind = kind
        self.before = before
        self.after = after
        self.unit = path[:-1] if len(path) > 1 else path
        self.region = region

    def key(self):
        return self.path

    def __repr__(self):
        return f"Change({'/'.join(self.path)}, {self.kind}, {self.before!r} -> {self.after!r})"


class Diff:
    def __init__(self):
        self.changes = []
        self.unverified = []   # dicts: path, reason, bytes_equal
        self.excluded = []     # derived indexes, listed but not compared


def _short(v, n=120):
    s = repr(v)
    return s if len(s) <= n else s[:n - 3] + '...'


def _walk(b, a, path, out):
    if isinstance(b, dict) and isinstance(a, dict):
        for k in sorted(set(b) | set(a), key=str):
            if k in b and k in a:
                _walk(b[k], a[k], path + (str(k),), out)
            elif k in b:
                out.changes.append(Change(path + (str(k),), 'removed', b[k], None))
            else:
                out.changes.append(Change(path + (str(k),), 'added', None, a[k]))
        return
    if isinstance(b, list) and isinstance(a, list) and len(b) == len(a):
        for i, (x, y) in enumerate(zip(b, a)):
            _walk(x, y, path + (str(i),), out)
        return
    if b != a:
        out.changes.append(Change(path, 'changed', b, a))


def _region_for(roots, rel, fmt, key_path):
    """Changed-pixel bounding box for a raster image or one XCF layer, when both sides are readable.
    The XCF composite is not localised here; its change is reported without a region."""
    try:
        if fmt == 'raster':
            before = readers_image.load_pixels(f"{roots[0]}/{rel}")
            after = readers_image.load_pixels(f"{roots[1]}/{rel}")
        elif fmt == 'xcf' and 'layers' in key_path:
            index = int(key_path[key_path.index('layers') + 1])
            before = readers_image.layer_pixels(f"{roots[0]}/{rel}", _stamp(f"{roots[0]}/{rel}"), index)
            after = readers_image.layer_pixels(f"{roots[1]}/{rel}", _stamp(f"{roots[1]}/{rel}"), index)
        else:
            return None
    except Exception:
        return None
    if before.shape != after.shape:
        return {'size_changed': [list(before.shape[:2]), list(after.shape[:2])]}
    mask = np.any(before[..., :] != after[..., :], axis=-1)
    if not mask.any():
        return None
    ys, xs = np.nonzero(mask)
    return {'bbox': [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
            'changed_pixels': int(mask.sum())}


def _stamp(path):
    import os
    st = os.stat(path)
    return (st.st_mtime_ns, st.st_size)


def diff_states(before, after, roots=None):
    """before, after: dir-state trees from canon.dir_tree. roots: (before_dir, after_dir) for pixel regions."""
    out = Diff()
    for rel in sorted(set(before) | set(after)):
        b, a = before.get(rel), after.get(rel)
        if b is None or a is None:
            present = a if b is None else b
            if present.get('kind') in ('unreadable', 'derived_index'):
                out.unverified.append({'path': rel, 'reason': present.get('reason'), 'bytes_equal': False})
                continue
            out.changes.append(Change((rel,), 'added' if b is None else 'removed', b, a))
            continue
        kinds = (b.get('kind'), a.get('kind'))
        if 'derived_index' in kinds:
            out.excluded.append({'path': rel, 'reason': 'derived index'})
            continue
        if 'unreadable' in kinds:
            same = b.get('sha256') == a.get('sha256') and b.get('sha256') is not None
            reason = (b if kinds[0] == 'unreadable' else a).get('reason')
            out.unverified.append({'path': rel, 'reason': reason, 'bytes_equal': same})
            if not same and kinds[0] != kinds[1]:
                out.changes.append(Change((rel,), 'changed', b.get('kind'), a.get('kind')))
            continue
        if b.get('kind') != a.get('kind'):
            out.changes.append(Change((rel,), 'changed', b.get('kind'), a.get('kind')))
            continue
        if b.get('kind') == 'file':
            if b.get('mode') != a.get('mode'):
                out.changes.append(Change((rel, 'mode'), 'changed', b.get('mode'), a.get('mode')))
            if b.get('format') != a.get('format'):
                out.changes.append(Change((rel, 'format'), 'changed', b.get('format'), a.get('format')))
            before_c, after_c = b.get('content'), a.get('content')
            start = len(out.changes)
            _walk(before_c, after_c, (rel, 'content'), out)
            # A pixel hash that could not be decoded cannot show a change, so the file is unverified, not unchanged.
            reason = readers_image.pixels_unreadable(before_c) or readers_image.pixels_unreadable(after_c)
            if reason:
                out.unverified.append({'path': rel, 'reason': reason, 'bytes_equal': b.get('sha256') == a.get('sha256')})
            if roots is not None:
                for ch in out.changes[start:]:
                    if ch.path[-1] in ('pixels_sha256', 'composite_sha256'):
                        ch.region = _region_for(roots, rel, b.get('format'), ch.path) or {'note': 'region not computed'}
        elif b != a:
            if b.get('mode') != a.get('mode'):
                out.changes.append(Change((rel, 'mode'), 'changed', b.get('mode'), a.get('mode')))
            if b.get('target') != a.get('target'):
                out.changes.append(Change((rel, 'target'), 'changed', b.get('target'), a.get('target')))
    return out


def subtract_noise(diff, noise):
    """Remove changes that the producer's own no-op save also makes, with the same after-value.

    noise: a Diff of (start, producer_resave_of_start). Returns (kept Diff, spurious list of Change)."""
    noise_map = {c.path: c for c in noise.changes}
    kept = Diff()
    kept.unverified = list(diff.unverified)
    kept.excluded = list(diff.excluded)
    spurious = []
    for c in diff.changes:
        n = noise_map.get(c.path)
        if n is not None and _same(n.after, c.after):
            spurious.append(c)
        else:
            kept.changes.append(c)
    return kept, spurious


def _same(x, y):
    if type(x) != type(y):
        return False
    return x == y


def verdict(diff, allowed):
    """allowed: callables path -> bool. Returns (verdict, violations, unverified list)."""
    violations = [c for c in diff.changes if not any(f(c.path) for f in allowed)]
    if violations:
        return 'FAIL', violations, diff.unverified
    if diff.unverified:
        return 'UNVERIFIED', [], diff.unverified
    return 'PASS', [], []


def prefix(*parts):
    """Allow changes at or under a path prefix, for example prefix('home', 'user', 'Desktop', 'x.xlsx')."""
    tgt = tuple(parts)
    return lambda p: p[:len(tgt)] == tgt


def summarize(diff):
    return {'changes': len(diff.changes), 'unverified': len(diff.unverified), 'excluded': len(diff.excluded)}
