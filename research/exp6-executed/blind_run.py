"""Exp 6 blind run: the spec executor (specs as written) and OSWorld's checker on every blind end state.

Reads the materialized end states (endstates/<task>/<state>/) and the exp5 starting snapshots. It does NOT read
labels: decisions are written keyed by blind id only. The blind map (blind id -> task, state) is written to a
private, gitignored file. Labels are joined later by blind_score.py, after decisions are fixed.

Usage: blind_run.py <out_dir> [endstates_dir]
  (writes <out_dir>/decisions.json and the private blind_map.json; endstates_dir defaults to endstates/)
"""
import hashlib, json, os, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import specexec  # noqa: E402
import official_check  # noqa: E402
import judge_packets  # noqa: E402
from gate_check import load_specs  # noqa: E402

ENDSTATES = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(HERE, 'endstates')
SNAPSHOTS = os.path.join(HERE, '..', 'exp5-grounded', 'snapshots')
BLIND_SRC = os.path.join(HERE, 'blind_src', 'research', 'exp6-blind-states')


def state_names(task):
    """State names are read only to enumerate the 7 end-state folders. The labels are not used here."""
    labels = json.load(open(os.path.join(BLIND_SRC, task, 'labels.json'), encoding='utf-8'))
    return [item['state'] for item in labels]


def main():
    out_dir = os.path.abspath(sys.argv[1])
    os.makedirs(out_dir, exist_ok=True)
    specs = load_specs()
    tasks = sorted(os.listdir(ENDSTATES))
    blind_map, decisions = {}, []
    for task in tasks:
        spec = specs[next(k for k in specs if k.startswith(task[:8]))]
        before = os.path.join(SNAPSHOTS, task)
        for state in state_names(task):
            bid = judge_packets.blind_id(task, state)
            blind_map[bid] = {'task': task, 'state': state}
            after = os.path.join(ENDSTATES, task, state)
            t0 = time.time()
            rec = {'blind_id': bid}
            try:
                res = specexec.run_spec(spec, after, before)
                rec.update(decision=res['decision'], predicates=res['predicates'],
                           empty_all_undecided_decision=res['empty_all_undecided_decision'])
            except Exception as e:  # executor crash is visible as ERROR, never as a pass
                rec.update(decision='ERROR', predicates=[], error=f'{type(e).__name__}: {str(e)[:200]}',
                           trace=traceback.format_exc()[-800:])
            try:
                off = official_check.run_official(task, after)
            except Exception as e:
                off = {'verdict': 'ERROR', 'detail': [f'{type(e).__name__}: {str(e)[:160]}']}
            rec.update(official=off['verdict'], official_detail=off['detail'], seconds=round(time.time() - t0, 2))
            decisions.append(rec)
            print(f"{task[:8]} {bid} exec={rec['decision']:9} official={rec['official']:13} {rec['seconds']}s",
                  flush=True)
    with open(os.path.join(out_dir, 'decisions.json'), 'w', encoding='utf-8') as fh:
        json.dump(decisions, fh, indent=1, ensure_ascii=False, default=str)
    with open(os.path.join(out_dir, 'run_config.json'), 'w', encoding='utf-8') as fh:
        json.dump({'endstates': ENDSTATES, 'executor_sha256': hashlib.sha256(open(specexec.__file__, 'rb').read()).hexdigest()},
                  fh, indent=1)
    with open(os.path.join(HERE, 'blind_map.json'), 'w', encoding='utf-8') as fh:
        json.dump(blind_map, fh, indent=1)
    print(f'done: {len(decisions)} states')


if __name__ == '__main__':
    main()
