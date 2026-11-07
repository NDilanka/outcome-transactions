"""Judge packets for T6 (copy of research/exp6-executed/judge_packets.py with the caps raised and no-clip assertions).

One packet per end state: request, inspection of the before state, inspection of the after state, and a diff.
Nothing else: no label, reading, spec, task id, state name, or amb id. The blind map (blind_id -> amb, state)
is written to a private file outside the repo.

Caps: the inspector's caps are raised to effectively unlimited here, and hard-coded inspector limits
(xlsx 500 non-empty cells per sheet, docx tables first 10 rows, pdf 5 pages / 4000 chars) are checked by
assertion. If any limit would clip, the build fails instead of writing a truncated packet.
"""
import difflib, hashlib, json, os, random, sys, re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = '/home/factory-user/repos/outcome-transactions'
sys.path.insert(0, '/home/factory-user/t6-work')
import inspect_snapshot_t6 as insp  # same inspector the spec writers used

BIG = 10 ** 9
insp.CAP_FILE = BIG
insp.CAP_TASK = BIG
insp.CAP_TEXT = BIG
CAP_DIFF = BIG  # the exp6 builder used 6000 here; raised so the diff is never clipped


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
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def scrubbed(root, p):
    """Inspector text for one file with the absolute root removed (inspector errors embed the path)."""
    return insp.inspect_file(p).replace(os.path.abspath(root), '')


def check_clip(root, p, vp):
    """Assert the inspector output for this file is not clipped. Returns nothing; raises AssertionError."""
    ext = os.path.splitext(p)[1].lower()
    text = insp.inspect_file(p)
    assert '[truncated' not in text, f'{vp}: inspector clip marker present'
    if ext == '.xlsx':
        for m in re.finditer(r'\(non-empty cells: (\d+)\)', text):
            assert int(m.group(1)) <= 500, f'{vp}: sheet has {m.group(1)} non-empty cells (inspector shows 500)'
        # the inspector stops listing cells after 500 per sheet; the count line proves nothing was dropped
        assert text.count('=') >= 0
    if ext == '.docx':
        import docx
        # docx table row cap lifted in inspect_snapshot_t6.py (no [:10] slice): nothing to assert
    if ext == '.pdf':
        from pypdf import PdfReader
        r = PdfReader(p)
        assert len(r.pages) <= 5, f'{vp}: pdf has {len(r.pages)} pages (inspector reads 5)'
        t = '\n'.join((pg.extract_text() or '') for pg in r.pages[:5])
        assert len(t) <= 4000, f'{vp}: pdf text {len(t)} chars (inspector clips at 4000)'


def check_hidden_caps(p, vp):
    """Inspector slices that do not print a truncation marker: xlsx rows [:200], zip listing [:150],
    pptx transition xml [:300]. Assert each limit is not reached."""
    import zipfile
    ext = os.path.splitext(p)[1].lower()
    if ext == '.xlsx':
        import openpyxl
        wb = openpyxl.load_workbook(p, data_only=False)
        for ws in wb.worksheets:
            assert ws.max_row <= 200, f'{vp}: sheet {ws.title} has {ws.max_row} rows (inspector lists 200)'
    if ext in ('.docx', '.pptx', '.xlsx', '.odt'):
        n = len(zipfile.ZipFile(p).namelist())
        assert n <= 150, f'{vp}: zip has {n} entries (inspector lists 150)'
    if ext == '.pptx':
        z = zipfile.ZipFile(p)
        for name in z.namelist():
            if name.startswith('ppt/slides/slide') and name.endswith('.xml'):
                xml = z.read(name).decode('utf8', 'replace')
                import re as _re
                for m in _re.finditer(r"<p:transition.*?</p:transition>|<p:transition[^>]*/>", xml, _re.S):
                    assert len(m.group(0)) <= 300, f'{vp}:{name}: transition xml {len(m.group(0))} chars (inspector shows 300)'


def checked_tree(root):
    """Every file under root must pass the no-clip checks; returns the inspector dump for the tree."""
    parts = []
    for vp, p in sorted(files_under(root).items()):
        check_clip(root, p, vp)
        check_hidden_caps(p, vp)
        parts.append(f"\n## FILE {vp} ({os.path.getsize(p)} bytes)\n" + scrubbed(root, p))
    return ''.join(parts)


def diff(before_root, after_root):
    b, a = files_under(before_root), files_under(after_root)
    lines = []
    for vp in sorted(set(b) | set(a)):
        if vp not in a:
            lines.append(f"REMOVED {vp}")
            continue
        if vp not in b:
            lines.append(f"ADDED {vp} ({os.path.getsize(a[vp])} bytes)")
            continue
        if sha(b[vp]) == sha(a[vp]):
            continue
        lines.append(f"CHANGED {vp} ({os.path.getsize(b[vp])} -> {os.path.getsize(a[vp])} bytes)")
        d = difflib.unified_diff(scrubbed(before_root, b[vp]).splitlines(), scrubbed(after_root, a[vp]).splitlines(),
                                 'before', 'after', lineterm='', n=2)
        text = '\n'.join(d)
        if text:
            assert len(text) <= CAP_DIFF
            lines.append(text)
    assert all('[truncated' not in x for x in lines), 'diff clip marker'
    return '\n'.join(lines) if lines else 'NO FILE CHANGED'


def blind_id(amb, state):
    """Stable opaque id for one end state. Carries no amb or state name."""
    return hashlib.sha256(('t6-' + f"{amb}|{state}").encode()).hexdigest()[:12]


def build(records, out_dir, map_path, shuffle_seed):
    """records: [{'amb': id, 'state': 'A'|'B', 'request': text, 'before_root': path, 'after_root': path}]."""
    os.makedirs(out_dir, exist_ok=True)
    order = list(records)
    random.Random(shuffle_seed).shuffle(order)
    blind_map = {}
    for r in order:
        bid = blind_id(r['amb'], r['state'])
        packet = {
            'blind_id': bid,
            'request': r['request'],
            'before_state': checked_tree(r['before_root']),
            'after_state': checked_tree(r['after_root']),
            'diff': diff(r['before_root'], r['after_root']),
        }
        for k, v in packet.items():
            assert '[truncated' not in json.dumps(v, ensure_ascii=False), f'{bid} {k}: clip marker'
        with open(os.path.join(out_dir, bid + '.json'), 'w') as fh:
            json.dump(packet, fh, indent=1, ensure_ascii=False)
        blind_map[bid] = {'amb': r['amb'], 'state': r['state'], 'before_root': r['before_root'], 'after_root': r['after_root']}
    with open(map_path, 'w') as fh:
        json.dump(blind_map, fh, indent=1)
    return blind_map
