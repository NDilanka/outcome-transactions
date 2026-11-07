"""Runs the spec executor and OSWorld's own checker on a set of end-state roots (gate controls or blind states).

Usage: gate_check.py <roots.json> <out.json>
roots.json: [{"task": full_id, "state": name, "root": path, "kind": "positive|start|..."}]
Each record gets the executor decision, the per-predicate records, and the official verdict.
"""
import glob, json, os, sys, yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import specexec  # noqa: E402
import official_check  # noqa: E402

SPECS_DIR = os.path.join(HERE, '..', 'exp5-grounded', 'specs')
SUBSET = ['1273e544', '42e0a640', '6054afcb', 'a9f325aa', 'f23acfd2', '57667013', '21760ecb', 'd53ff5ee',
          '88fe4b2d', '936321ce', 'ecc2413d', '4d117223']


def load_specs():
    out = {}
    for f in sorted(glob.glob(os.path.join(SPECS_DIR, 'batch_*.yaml'))):
        d = yaml.safe_load(open(f))
        items = d if isinstance(d, list) else d.get('tasks', d)
        for t in items:
            out[str(t['id'])] = t
    return out


def run_one(spec, task, root, start_root):
    res = specexec.run_spec(spec, root, start_root)
    try:
        off = official_check.run_official(task, root)
    except Exception as e:  # official runner problem: visible, never silent
        off = {'verdict': 'ERROR', 'detail': [f'{type(e).__name__}: {str(e)[:160]}']}
    return {'decision': res['decision'], 'predicates': res['predicates'], 'official': off['verdict'],
            'official_detail': off['detail']}


def main():
    roots = json.load(open(sys.argv[1]))
    specs = load_specs()
    out = []
    for r in roots:
        task = r['task']
        spec = specs[next(k for k in specs if k.startswith(task[:8]))]
        start_root = r.get('start_root', r['root'])
        rec = dict(r)
        rec.update(run_one(spec, task, r['root'], start_root))
        out.append(rec)
        print(f"{task[:8]:9} {r['state']:12} exec={rec['decision']:9} official={rec['official']}", flush=True)
        for p in rec['predicates']:
            if p['status'] != 'PASS':
                print(f"    {p['status']:11} {p['pred'][:110]}  :: {p['reason'][:110]}", flush=True)
    json.dump(out, open(sys.argv[2], 'w'), indent=1, ensure_ascii=False, default=str)


if __name__ == '__main__':
    main()
