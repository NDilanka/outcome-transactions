"""Run the frozen Exp 6 spec executor (research/exp6-executed/specexec.py, unchanged since c909d02) on each Exp 8 end state.

Each attempt runs in a fresh process so the cost of one spec check (imports included) can be measured with wait4 rusage.
The end state is placed under a machine root at the path the spec names (for example /home/user/Desktop/x.pptx).
The starting copy is placed under a second root and read by before(). Output: one JSON per attempt in
/home/factory-user/exp8/specs/ (private, not committed until results are final).

Usage: run_specs.py            (all 84 attempts)
       run_specs.py <code>     (one attempt, printed)
"""
import json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
EXP6 = os.path.join(REPO, 'research', 'exp6-executed')
SPECS = os.path.join(REPO, 'research', 'exp5-grounded', 'specs')
BLIND = os.path.join(REPO, 'research', 'exp4b', 'blind_tasks.json')
PRIV = '/home/factory-user/exp8/private'
EXEC = '/home/factory-user/exp8/exec'
OUT = '/home/factory-user/exp8/specs'


def load_specs():
    import yaml
    out = {}
    for f in sorted(os.listdir(SPECS)):
        if f.endswith('.yaml'):
            for s in yaml.safe_load(open(os.path.join(SPECS, f))) or []:
                out[s['id']] = s
    return out


def spec_path_for(spec, file_name):
    """The machine path the spec names for this file (the basename must match)."""
    import re
    paths = set(re.findall(r"'(/home/user[^']*)'", ' '.join(spec.get('must', []))))
    hits = sorted(p for p in paths if os.path.basename(p) == file_name)
    return hits[0] if hits else None


def child(code):
    t0 = time.perf_counter()
    sys.path.insert(0, EXP6)
    import specexec as sx
    entries = {e['code']: e for e in json.load(open(os.path.join(PRIV, 'map.json')))}
    e = entries[code]
    full = {t['id'][:8]: t['id'] for t in json.load(open(BLIND))}[e['short']]
    spec = load_specs()[full]
    roots = tempfile.mkdtemp(prefix='exp8_specroot_')
    try:
        if e['kind'] == 'profile':
            end_root = os.path.join(EXEC, code, 'target')
            start_root = os.path.dirname(e['input_path'])
            spec_rel = None
        else:
            spec_rel = spec_path_for(spec, e['file'])
            end_root, start_root = os.path.join(roots, 'end'), os.path.join(roots, 'start')
            for root, src in ((end_root, os.path.join(EXEC, code, 'target', e['file'])),
                              (start_root, e['input_path'])):
                dst = root + spec_rel
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
        t1 = time.perf_counter()
        res = sx.run_spec(spec, end_root, start_root)
        t2 = time.perf_counter()
    finally:
        shutil.rmtree(roots, ignore_errors=True)
    statuses = {}
    for p in res['predicates']:
        statuses[p['status']] = statuses.get(p['status'], 0) + 1
    print(json.dumps({
        'code': code, 'short': e['short'], 'condition': e['condition'], 'method_idx': e['method_idx'],
        'spec_path': spec_rel, 'decision': res['decision'],
        'empty_all_undecided_decision': res['empty_all_undecided_decision'],
        'statuses': statuses, 'predicates': res['predicates'],
        'eval_s': round(t2 - t1, 4), 'setup_s': round(t1 - t0, 4)}, default=str))


def parent(codes):
    os.makedirs(OUT, exist_ok=True)
    summary = []
    for code in codes:
        log = os.path.join(OUT, code + '.stdout')
        errlog = os.path.join(OUT, code + '.stderr')
        t0 = time.perf_counter()
        with open(log, 'w') as so, open(errlog, 'w') as se:
            p = subprocess.Popen([sys.executable, __file__, '--child', code], stdout=so, stderr=se)
            _, status, ru = os.wait4(p.pid, 0)
        wall = time.perf_counter() - t0
        rec = {'code': code, 'exit_status': status, 'proc_wall_s': round(wall, 3),
               'proc_cpu_s': round(ru.ru_utime + ru.ru_stime, 3),
               'proc_peak_rss_mb': round(ru.ru_maxrss / 1024, 1)}
        if status == 0:
            lines = [ln for ln in open(log).read().splitlines() if ln.startswith('{')]
            rec.update(json.loads(lines[-1]))
        else:
            rec['error'] = open(errlog).read()[-400:]
        with open(os.path.join(OUT, code + '.json'), 'w') as fh:
            json.dump(rec, fh, indent=1, default=str)
        os.remove(log)
        os.remove(errlog)
        summary.append(rec)
        print(code, rec.get('short'), rec.get('decision', 'ERROR'), rec.get('empty_all_undecided_decision', ''),
              rec['proc_wall_s'], rec['proc_cpu_s'], rec['proc_peak_rss_mb'], flush=True)
    return summary


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--child':
        child(sys.argv[2])
    elif len(sys.argv) == 2:
        child(sys.argv[1])
    else:
        codes = [e['code'] for e in json.load(open(os.path.join(PRIV, 'map.json')))]
        parent(codes)
