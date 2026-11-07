"""Exp 7 blind run: the spec executor and OSWorld's checker on every Exp 7 end state.

Reads the materialised end states (<endstates>/<task>/state_NN/) and the exp5 starting snapshots. It reads no
label file and no state description. Decisions are keyed by blind id only. The blind map (blind id -> task, state)
is written to a private, gitignored file given on the command line. Labels are joined later, after decisions are
fixed. Exp 7 blind ids use their own prefix so they never collide with Exp 6 ids.

Usage: blind_run_exp7.py <out_dir> <endstates_dir> <map_path> [--exclude <json list of [task, state]>] [--no-official]
  (writes <out_dir>/decisions.json and <out_dir>/run_config.json)
"""
import hashlib, json, os, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import specexec  # noqa: E402
import official_check  # noqa: E402
from gate_check import load_specs  # noqa: E402

SNAPSHOTS = os.path.join(HERE, '..', 'exp5-grounded', 'snapshots')


def blind_id(task, state):
    return hashlib.sha256(('exp7-' + f'{task}|{state}').encode()).hexdigest()[:12]


def main():
    args = sys.argv[1:]
    no_official = '--no-official' in args
    if no_official:
        args.remove('--no-official')
    exclude = set()
    if '--exclude' in args:
        i = args.index('--exclude')
        exclude = {tuple(x) for x in json.load(open(args[i + 1]))}
        del args[i:i + 2]
    out_dir, endstates, map_path = (os.path.abspath(a) for a in args[:3])
    os.makedirs(out_dir, exist_ok=True)
    specs = load_specs()
    blind_map, decisions = {}, []
    for task in sorted(os.listdir(endstates)):
        spec = specs[next(k for k in specs if k.startswith(task[:8]))]
        before = os.path.join(SNAPSHOTS, task)
        for state in sorted(d for d in os.listdir(os.path.join(endstates, task)) if d.startswith('state_')):
            if (task, state) in exclude:
                continue
            bid = blind_id(task, state)
            blind_map[bid] = {'task': task, 'state': state}
            after = os.path.join(endstates, task, state)
            t0 = time.time()
            rec = {'blind_id': bid}
            try:
                res = specexec.run_spec(spec, after, before)
                rec.update(decision=res['decision'], predicates=res['predicates'])
                if 'empty_all_undecided_decision' in res:
                    rec['empty_all_undecided_decision'] = res['empty_all_undecided_decision']
            except Exception as e:  # executor crash is visible as ERROR, never as a pass
                rec.update(decision='ERROR', predicates=[], error=f'{type(e).__name__}: {str(e)[:200]}',
                           trace=traceback.format_exc()[-800:])
            if no_official:
                rec.update(official='SKIPPED', official_detail=[])
            else:
                try:
                    off = official_check.run_official(task, after)
                except Exception as e:
                    off = {'verdict': 'ERROR', 'detail': [f'{type(e).__name__}: {str(e)[:160]}']}
                rec.update(official=off['verdict'], official_detail=off['detail'])
            rec['seconds'] = round(time.time() - t0, 2)
            decisions.append(rec)
            print(f"{task[:8]} {bid} exec={rec['decision']:9} official={rec['official']:13} {rec['seconds']}s",
                  flush=True)
    with open(os.path.join(out_dir, 'decisions.json'), 'w', encoding='utf-8') as fh:
        json.dump(decisions, fh, indent=1, ensure_ascii=False, default=str)
    with open(os.path.join(out_dir, 'run_config.json'), 'w', encoding='utf-8') as fh:
        json.dump({'endstates': endstates, 'no_official': no_official, 'excluded': sorted(map(list, exclude)),
                   'executor_sha256': hashlib.sha256(open(specexec.__file__, 'rb').read()).hexdigest()},
                  fh, indent=1)
    os.makedirs(os.path.dirname(map_path), exist_ok=True)
    with open(map_path, 'w', encoding='utf-8') as fh:
        json.dump(blind_map, fh, indent=1)
    print(f'done: {len(decisions)} states')


if __name__ == '__main__':
    main()
