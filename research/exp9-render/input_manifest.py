"""Input manifest for the 78 Exp 9 states: sha256 of every input file, keyed by blind id only.

Frozen at the lock commit. The paths and task or state names stay private (they would reveal group membership
before unblinding). Each side lists the sha256 of its files in sorted relative-path order. The render checks
the same lists before and after rendering. Output: research/exp9-render/input_manifest.json.

Usage: input_manifest.py --salt-file FILE --sample FILE --states DIR --out FILE
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_lib as rl  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salt-file', required=True)
    ap.add_argument('--sample', required=True)
    ap.add_argument('--states', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    salt = open(args.salt_file, encoding='utf-8').read().rstrip('\n')
    sample = json.load(open(args.sample))
    manifest, seen = {}, set()
    for group in 'ABCD':
        for item in sample[group]:
            task, state = item['task'], item['state']
            bid = rl.bid9(salt, task, state)
            if bid in seen:
                raise SystemExit('duplicate blind id ' + bid)
            seen.add(bid)
            before = [h for _, h in rl.tree_hashes(os.path.join(rl.SNAPSHOTS, task))]
            after = [h for _, h in rl.tree_hashes(os.path.join(args.states, task, state))]
            manifest[bid] = {'start': before, 'end': after}
    if len(manifest) != 78:
        raise SystemExit(f'{len(manifest)} states, expected 78')
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(dict(sorted(manifest.items())), fh, indent=1)
        fh.write('\n')
    print('states:', len(manifest), 'files:', sum(len(v['start']) + len(v['end']) for v in manifest.values()))


if __name__ == '__main__':
    main()
