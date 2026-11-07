"""Joins the private generator labels to the blind run decisions. Run only after blind_run.py has written
decisions.json; it does not change any decision.

Usage: blind_score.py <blind_run_dir>
Writes <blind_run_dir>/score_rows.json (one row per state, with label) and prints the disagreement list.
"""
import collections, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLIND_SRC = os.path.join(HERE, 'blind_src', 'research', 'exp6-blind-states')


def load_labels():
    """Generator labels, keyed by (task, state). Read only here, after decisions are fixed."""
    out = {}
    for task in sorted(os.listdir(BLIND_SRC)):
        p = os.path.join(BLIND_SRC, task, 'labels.json')
        if not os.path.isfile(p):
            continue
        for item in json.load(open(p, encoding='utf-8')):
            out[(task, item['state'])] = {'label': item['label'], 'why': item['why']}
    return out


def main():
    run_dir = os.path.abspath(sys.argv[1])
    decisions = json.load(open(os.path.join(run_dir, 'decisions.json')))
    bmap = json.load(open(os.path.join(HERE, 'blind_map.json')))
    labels = load_labels()
    rows = []
    for d in decisions:
        m = bmap[d['blind_id']]
        lab = labels[(m['task'], m['state'])]
        rows.append({'blind_id': d['blind_id'], 'task': m['task'], 'state': m['state'], 'label': lab['label'],
                     'why': lab['why'], 'exec': d['decision'], 'official': d['official']})
    json.dump(rows, open(os.path.join(run_dir, 'score_rows.json'), 'w'), indent=1, ensure_ascii=False)
    c = collections.Counter((r['label'], r['exec']) for r in rows)
    print('label x exec:', dict(c))
    print('label x official:', dict(collections.Counter((r['label'], r['official']) for r in rows)))
    print('wrong states:', sum(r['label'] == 'wrong' for r in rows), 'correct states:',
          sum(r['label'] == 'correct' for r in rows))


if __name__ == '__main__':
    main()
