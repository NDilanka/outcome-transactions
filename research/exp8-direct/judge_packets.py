"""Judge packets for Exp 8. One packet per end state: the request, an inspection of the before state, an inspection
of the after state, and a diff. Nothing else: no label, spec, generator rationale, task id, or state name.
The blind map (blind_id -> task, state) is written to a private file that is not committed.

Copy of research/exp6-executed/judge_packets.py with the truncation removed (orchestrator decision for Exp 8). The exp6
file is unchanged."""
import difflib, hashlib, json, os, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'exp5-grounded'))
import inspect_snapshot as insp  # same inspector the exp5 spec writers used

# Exp 8: no clipping anywhere in a judge packet. The inspector's clip() becomes the identity, so inspection text,
# state dumps and the diff are never cut. build_judge_packets.py asserts that no packet contains a truncation marker.
insp.clip = lambda s, n=None: s
CAP_DIFF = None

# The inspector also lists only the first 10 rows of each docx table, with no marker. Eight Exp 8 end states contain an
# 11-row table, so every row is appended after the capped lines (the capped lines stay unchanged).
_inspect_docx_capped = insp.docx_report


def _docx_report_all_rows(path):
    import docx
    d = docx.Document(path)
    full = [f"table{ti} all {len(t.rows)} rows: " + json.dumps([[c.text for c in r.cells] for r in t.rows])
            for ti, t in enumerate(d.tables) if len(t.rows) > 10]
    return "\n".join([_inspect_docx_capped(path)] + full)


insp.docx_report = _docx_report_all_rows


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


def scrubbed(root, p):
    """Inspector text for one file with the absolute root removed. Inspector errors embed the full path, which
    carries the task id and state name, so the root must not reach the packet."""
    return insp.inspect_file(p).replace(os.path.abspath(root), '')


def dump(root):
    """Inspector text per file, same format as research/exp5-grounded/inspections/*.md."""
    parts = []
    for vp, p in sorted(files_under(root).items()):
        parts.append(f"\n## FILE {vp} ({os.path.getsize(p)} bytes)\n" + insp.clip(scrubbed(root, p), insp.CAP_FILE))
    return insp.clip(''.join(parts), insp.CAP_TASK)


def diff(before_root, after_root):
    b, a = files_under(before_root), files_under(after_root)
    lines = []
    for vp in sorted(set(b) | set(a)):
        if vp not in a: lines.append(f"REMOVED {vp}"); continue
        if vp not in b: lines.append(f"ADDED {vp} ({os.path.getsize(a[vp])} bytes)"); continue
        if sha(b[vp]) == sha(a[vp]): continue
        lines.append(f"CHANGED {vp} ({os.path.getsize(b[vp])} -> {os.path.getsize(a[vp])} bytes)")
        d = difflib.unified_diff(scrubbed(before_root, b[vp]).splitlines(), scrubbed(after_root, a[vp]).splitlines(),
                                 'before', 'after', lineterm='', n=2)
        text = '\n'.join(d)
        if text: lines.append(insp.clip(text, CAP_DIFF))
    return '\n'.join(lines) if lines else 'NO FILE CHANGED'


def blind_id(task, state):
    """Stable opaque id for one end state. Carries no task or state name."""
    return hashlib.sha256(('exp6-' + f"{task}|{state}").encode()).hexdigest()[:12]


def build(records, out_dir, map_path, requests):
    """records: [{'task': full_id, 'state': name, 'before_root': path, 'after_root': path}]
    requests: {task_prefix8: request text}. Returns the blind map."""
    os.makedirs(out_dir, exist_ok=True)
    blind_map = {}
    for r in records:
        bid = blind_id(r['task'], r['state'])
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
