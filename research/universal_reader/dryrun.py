"""Dry run: the Exp 5 must-predicates (specs unchanged) against the Exp 6 blind end states, through the canonical tree.

For every blind-covered task and each of its 7 end states, two executors run the same spec:
  frozen  research/exp6-executed/specexec.py (read-only import; the Exp 6 executor)
  tree    research/universal_reader/evaluate.py (views over canonical trees)
Labels are read only after decisions are computed, to score them. Specs without blind states (32 of 66) are
evaluated on their starting snapshot, to measure must-predicate evaluability only; they get no accept counts.

Usage:
  dryrun.py --blind-src <exp6-blind-states dir> --endstates <dir> [--snapshots <dir>] [--out <dir>]
Writes <out>/dryrun.json. Summary tables are printed.
"""
import argparse
import collections
import glob
import json
import os
import re
import sys
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, 'research', 'exp6-executed'))

import specexec  # noqa: E402  frozen Exp 6 executor, imported read-only
from research.universal_reader import canon, evaluate  # noqa: E402

REASON_CATEGORIES = [
    ('parse:', 'parse (grammar)'),
    ('unknown name', 'unknown name (no reader)'),
    ('no reader', 'no reader (live or external state)'),
    ('live or external', 'no reader (live or external state)'),
    ('held-out', 'unreadable file (held out)'),
    ('unreadable', 'unreadable file'),
    ('unknown value', 'value not on disk'),
    ('derived index', 'derived index'),
    ('has format', 'file format not read by this view'),
    ('no attribute', 'attribute not in reader'),
    ('no key', 'JSON key not present'),
    ('is a directory', 'directory used as file'),
    ('range() with no sheet', 'range() without sheet'),
    ('not a text file', 'not a text file'),
    ('ERROR', 'executor error'),
]


def categorise(status, reason):
    if status == 'PASS' or status == 'FAIL':
        return None
    text = reason or ''
    if status == 'ERROR':
        return 'executor error'
    for needle, cat in REASON_CATEGORIES:
        if needle in text:
            return cat
    return 'other'


def load_specs():
    specs = {}
    for f in sorted(glob.glob(os.path.join(REPO, 'research', 'exp5-grounded', 'specs', 'batch_*.yaml'))):
        d = yaml.safe_load(open(f, encoding='utf-8'))
        items = d if isinstance(d, list) else d.get('tasks', d)
        for t in items:
            specs[str(t['id'])] = t
    return specs


def load_families():
    fam = {}
    for f in sorted(glob.glob(os.path.join(REPO, 'research', 'exp5-grounded', 'batches', 'batch_*.json'))):
        for t in json.load(open(f, encoding='utf-8')):
            fam[str(t['id'])] = t['domain']
    return fam


def load_labels(blind_src, task):
    items = json.load(open(os.path.join(blind_src, task, 'labels.json'), encoding='utf-8'))
    return {it['state']: it['label'] for it in items}


def run_task_states(spec, start_dir, start_tree, end_root, states):
    """Yield one record per state: frozen and tree decisions and per-predicate statuses."""
    for state, label in states:
        end_dir = os.path.join(end_root, state)
        t0 = time.time()
        rec = {'state': state, 'label': label}
        try:
            fr = specexec.run_spec(spec, end_dir, start_dir)
            rec['frozen'] = {'decision': fr['decision'],
                             'statuses': [p['status'] for p in fr['predicates']]}
        except Exception as e:  # executor crash is visible, never a pass
            rec['frozen'] = {'decision': 'ERROR', 'statuses': [], 'error': f'{type(e).__name__}: {e}'[:200]}
        try:
            end_tree = canon.dir_tree(end_dir)
            mine = evaluate.run_spec(spec, end_tree, start_tree, end_dir, start_dir)
            rec['tree'] = {'decision': mine['decision'], 'predicates': mine['predicates'],
                           'empty_all_undecided_decision': mine['empty_all_undecided_decision'],
                           'unreadable_files': sorted(p for p, n in end_tree.items() if n.get('kind') == 'unreadable')}
        except Exception as e:
            rec['tree'] = {'decision': 'ERROR', 'predicates': [], 'error': f'{type(e).__name__}: {e}'[:200]}
        rec['seconds'] = round(time.time() - t0, 2)
        yield rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--blind-src', required=True)
    ap.add_argument('--endstates', required=True)
    ap.add_argument('--snapshots', default=os.path.join(REPO, 'research', 'exp5-grounded', 'snapshots'))
    ap.add_argument('--out', default=os.path.join(HERE, 'results'))
    ap.add_argument('--only', default=None, help='task id prefix (quick runs)')
    args = ap.parse_args(argv)

    specs, fam = load_specs(), load_families()
    os.makedirs(args.out, exist_ok=True)
    blind_tasks = sorted(t for t in os.listdir(args.endstates) if os.path.isdir(os.path.join(args.endstates, t)))
    if args.only:
        blind_tasks = [t for t in blind_tasks if t.startswith(args.only)]

    tasks = []
    for task in blind_tasks:
        spec = specs[task]
        start_dir = os.path.join(args.snapshots, task)
        start_tree = canon.dir_tree(start_dir)
        labels = load_labels(args.blind_src, task)
        states = [(s, labels[s]) for s in sorted(labels)]
        recs = list(run_task_states(spec, start_dir, start_tree, os.path.join(args.endstates, task), states))
        tasks.append({'task': task, 'family': fam[task], 'blind': True, 'states': recs})
        for r in recs:
            print(f"{task[:8]} {r['state'][:34]:34} {r['label']:8} frozen={r['frozen']['decision']:9} "
                  f"tree={r['tree']['decision']:9} {r['seconds']}s", flush=True)

    # Specs without blind states: evaluability on the starting snapshot (no accept counts).
    if not args.only:
        for sid in sorted(specs):
            if sid in blind_tasks:
                continue
            start_dir = os.path.join(args.snapshots, sid)
            if not os.path.isdir(start_dir):
                tasks.append({'task': sid, 'family': fam[sid], 'blind': False, 'snapshot': False, 'predicates': []})
                continue
            start_tree = canon.dir_tree(start_dir)
            mine = evaluate.run_spec(specs[sid], start_tree, start_tree, start_dir, start_dir)
            tasks.append({'task': sid, 'family': fam[sid], 'blind': False, 'snapshot': True,
                          'predicates': mine['predicates']})

    out_path = os.path.join(args.out, 'dryrun.json')
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump({'tasks': tasks, 'frozen_executor': 'research/exp6-executed/specexec.py'}, fh, indent=1,
                  ensure_ascii=False, default=str)
    print('wrote', out_path)
    summarise(tasks)


def summarise(tasks):
    by_fam = collections.OrderedDict()
    for t in tasks:
        if not t.get('blind'):
            continue
        f = by_fam.setdefault(t['family'], collections.Counter())
        for r in t['states']:
            key = 'correct' if r['label'] == 'correct' else 'wrong'
            f[f'{key}_n'] += 1
            f[f'{key}_frozen_accept'] += r['frozen']['decision'] == 'ACCEPT'
            f[f'{key}_tree_accept'] += r['tree']['decision'] == 'ACCEPT'
            f[f'{key}_tree_reject'] += r['tree']['decision'] == 'REJECT'
            f[f'{key}_tree_undecided'] += r['tree']['decision'] == 'UNDECIDED'
            if r['tree']['decision'] == 'ACCEPT' and any(p.get('proxy') for p in r['tree']['predicates']):
                f[f'{key}_tree_accept_via_proxy'] += 1
    print('\n## Correct and wrong blind states by family (blind-covered specs)')
    print('| family | states | correct | correct ACCEPT frozen | correct ACCEPT tree | correct via proxy | '
          'wrong | wrong ACCEPT frozen | wrong ACCEPT tree |')
    print('|---|---|---|---|---|---|---|---|---|')
    tot = collections.Counter()
    for fm, c in by_fam.items():
        print(f"| {fm} | {c['correct_n'] + c['wrong_n']} | {c['correct_n']} | {c['correct_frozen_accept']} | "
              f"{c['correct_tree_accept']} | {c['correct_tree_accept_via_proxy']} | {c['wrong_n']} | "
              f"{c['wrong_frozen_accept']} | {c['wrong_tree_accept']} |")
        tot.update(c)
    print(f"| all | {tot['correct_n'] + tot['wrong_n']} | {tot['correct_n']} | {tot['correct_frozen_accept']} | "
          f"{tot['correct_tree_accept']} | {tot['correct_tree_accept_via_proxy']} | {tot['wrong_n']} | "
          f"{tot['wrong_frozen_accept']} | {tot['wrong_tree_accept']} |")

    print('\n## Must-predicate evaluability through the tree (PASS or FAIL = decided by the reader)')
    ev_fam = collections.OrderedDict()
    gaps = collections.Counter()
    parse_fail = collections.Counter()
    for t in tasks:
        f = ev_fam.setdefault(t['family'], collections.Counter())
        if t.get('blind'):
            pairs = [p for r in t['states'] for p in r['tree']['predicates']]
            # Parse status is per predicate: count each predicate once per task.
            for p in t['states'][0]['tree']['predicates'] if t['states'] else []:
                f['predicates'] += 1
                if p['status'] == 'UNSUPPORTED' and (p.get('reason') or '').startswith('parse:'):
                    f['parse_fail'] += 1
                    parse_fail[t['family']] += 1
            for p in pairs:
                f['pairs'] += 1
                f[p['status']] += 1
                cat = categorise(p['status'], p.get('reason'))
                if cat:
                    gaps[(t['family'], cat)] += 1
        elif t.get('snapshot'):
            for p in t['predicates']:
                f['predicates'] += 1
                f['snapshot_pairs'] += 1
                f[f"snapshot_{p['status']}"] += 1
                if p['status'] == 'UNSUPPORTED' and (p.get('reason') or '').startswith('parse:'):
                    f['parse_fail'] += 1
                    parse_fail[t['family']] += 1
                cat = categorise(p['status'], p.get('reason'))
                if cat:
                    gaps[(t['family'], cat)] += 1
    print('| family | predicates | parse fail | (blind pairs) PASS | FAIL | UNSUPPORTED | ERROR | '
          '(snapshot-only) PASS | FAIL | UNSUPPORTED | ERROR |')
    print('|---|---|---|---|---|---|---|---|---|---|---|')
    for fm, c in ev_fam.items():
        print(f"| {fm} | {c['predicates']} | {c['parse_fail']} | {c['PASS']} | {c['FAIL']} | {c['UNSUPPORTED']} | "
              f"{c['ERROR']} | {c['snapshot_PASS']} | {c['snapshot_FAIL']} | {c['snapshot_UNSUPPORTED']} | "
              f"{c['snapshot_ERROR']} |")
    print('\n## Gap categories (non-decided statuses, all families)')
    for (fm, cat), n in sorted(gaps.items(), key=lambda kv: (kv[0][0], -kv[1])):
        print(f'{fm:22} {n:5}  {cat}')


if __name__ == '__main__':
    main()
