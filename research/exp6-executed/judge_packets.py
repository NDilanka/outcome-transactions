"""Judge packets for Exp 6. One packet per end state: the request, an inspection of the before state, an inspection
of the after state, and a diff. Nothing else: no label, spec, generator rationale, task id, or state name.
The blind map (blind_id -> task, state) is written to a private file that is not committed."""
import difflib, hashlib, json, os, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'exp5-grounded'))
import inspect_snapshot as insp  # same inspector the exp5 spec writers used

CAP_DIFF = 6000


def files_under(root):
    out = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f)
            out['/' + os.path.relpath(p, root).replace(os.sep, '/')] = p
    return out


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


def dump(root):
    """Inspector text per file, same format as research/exp5-grounded/inspections/*.md."""
    parts = []
    for vp, p in sorted(files_under(root).items()):
        parts.append(f"\n## FILE {vp} ({os.path.getsize(p)} bytes)\n" + insp.clip(insp.inspect_file(p), insp.CAP_FILE))
    return insp.clip(''.join(parts), insp.CAP_TASK)


def diff(before_root, after_root):
    b, a = files_under(before_root), files_under(after_root)
    lines = []
    for vp in sorted(set(b) | set(a)):
        if vp not in a: lines.append(f"REMOVED {vp}"); continue
        if vp not in b: lines.append(f"ADDED {vp} ({os.path.getsize(a[vp])} bytes)"); continue
        if sha(b[vp]) == sha(a[vp]): continue
        lines.append(f"CHANGED {vp} ({os.path.getsize(b[vp])} -> {os.path.getsize(a[vp])} bytes)")
        d = difflib.unified_diff(insp.inspect_file(b[vp]).splitlines(), insp.inspect_file(a[vp]).splitlines(),
                                 'before', 'after', lineterm='', n=2)
        text = '\n'.join(d)
        if text: lines.append(insp.clip(text, CAP_DIFF))
    return '\n'.join(lines) if lines else 'NO FILE CHANGED'


def build(records, out_dir, map_path, requests):
    """records: [{'task': full_id, 'state': name, 'before_root': path, 'after_root': path}]
    requests: {task_prefix8: request text}. Returns the blind map."""
    os.makedirs(out_dir, exist_ok=True)
    blind_map = {}
    for r in records:
        key = f"{r['task']}|{r['state']}"
        bid = hashlib.sha256(('exp6-' + key).encode()).hexdigest()[:12]
        req = requests[r['task'][:8]]
        packet = {
            'blind_id': bid,
            'request': req,
            'before_state': dump(r['before_root']),
            'after_state': dump(r['after_root']),
            'diff': diff(r['before_root'], r['after_root']),
        }
        with open(os.path.join(out_dir, bid + '.json'), 'w') as fh:
            json.dump(packet, fh, indent=1, ensure_ascii=False)
        blind_map[bid] = {'task': r['task'], 'state': r['state']}
    with open(map_path, 'w') as fh:
        json.dump(blind_map, fh, indent=1)
    return blind_map


def load_requests():
    ts = json.load(open(os.path.join(HERE, '..', 'exp4b', 'blind_tasks.json')))
    return {t['id'][:8]: t['instruction'] for t in ts}
