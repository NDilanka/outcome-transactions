"""Exp 7 judge packets, untruncated (Amendment 3).

Same packet shape as judge_packets.py (request, before-state inspection, after-state inspection, diff, nothing else),
but nothing is clipped: the diff, the per-file inspections and the whole-task inspections are written in full.
Exp 6 packets used CAP_DIFF = 6000 and the inspector caps; this module removes every clip by replacing the
inspector's clip function, so both the diff and the state dumps are complete.

Blind ids use the prefix 'exp7-' so they never collide with Exp 6 ids. The blind map goes to a private file.
Usage: judge_packets_exp7.py <out_dir> <endstates_dir> <map_path> [--exclude <json list of [task, state]>]
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'exp5-grounded'))
import inspect_snapshot as insp  # noqa: E402
import judge_packets as jp  # noqa: E402

# No clipping anywhere in the packet path: the diff, the per-file inspections and the task dump.
insp.clip = lambda s, n: s
jp.clip = insp.clip
SNAPSHOTS = os.path.join(HERE, '..', 'exp5-grounded', 'snapshots')


def blind_id(task, state):
    import hashlib
    return hashlib.sha256(('exp7-' + f'{task}|{state}').encode()).hexdigest()[:12]


def main():
    args = sys.argv[1:]
    exclude = set()
    if '--exclude' in args:
        i = args.index('--exclude')
        exclude = {tuple(x) for x in json.load(open(args[i + 1]))}
        del args[i:i + 2]
    out_dir, endstates, map_path = (os.path.abspath(a) for a in args[:3])
    os.makedirs(out_dir, exist_ok=True)
    requests = jp.load_requests()
    blind_map = {}
    for task in sorted(os.listdir(endstates)):
        before = os.path.join(SNAPSHOTS, task)
        for state in sorted(d for d in os.listdir(os.path.join(endstates, task)) if d.startswith('state_')):
            if (task, state) in exclude:
                continue
            bid = blind_id(task, state)
            after = os.path.join(endstates, task, state)
            packet = {
                'blind_id': bid,
                'request': requests[task[:8]],
                'before_state': jp.dump(before),
                'after_state': jp.dump(after),
                'diff': jp.diff(before, after),
            }
            with open(os.path.join(out_dir, bid + '.json'), 'w') as fh:
                json.dump(packet, fh, indent=1, ensure_ascii=False)
            blind_map[bid] = {'task': task, 'state': state}
    with open(map_path, 'w') as fh:
        json.dump(blind_map, fh, indent=1)
    print(f'packets: {len(blind_map)}')


if __name__ == '__main__':
    main()
