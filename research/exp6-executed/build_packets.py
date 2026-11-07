"""Writes the judge packets for the Exp 6 blind run: one JSON per end state, in judge_packets/.

Each packet holds the request, an inspection of the before state, an inspection of the after state, and a diff.
It holds no label, spec, generator rationale, task id, or state name. The blind map (blind id -> task, state) is
read from the private blind_map.json (written by blind_run.py, gitignored). After-states are the normalized copies
in endstates_norm/ (see normalize_states.py). Leak check: run leak_check.py after building.

Usage: build_packets.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import judge_packets  # noqa: E402

SNAPSHOTS = os.path.join(HERE, '..', 'exp5-grounded', 'snapshots')
ENDSTATES = os.path.join(HERE, 'endstates_norm')


def main():
    map_path = os.path.join(HERE, 'blind_map.json')
    bmap = json.load(open(map_path, encoding='utf-8'))
    records = []
    for bid, m in sorted(bmap.items()):
        assert judge_packets.blind_id(m['task'], m['state']) == bid, 'blind id mismatch'
        records.append({'task': m['task'], 'state': m['state'],
                        'before_root': os.path.join(SNAPSHOTS, m['task']),
                        'after_root': os.path.join(ENDSTATES, m['task'], m['state'])})
    judge_packets.build(records, out_dir=os.path.join(HERE, 'judge_packets'), map_path=map_path,
                        requests=judge_packets.load_requests())
    print('packets written:', len(records))


if __name__ == '__main__':
    main()
