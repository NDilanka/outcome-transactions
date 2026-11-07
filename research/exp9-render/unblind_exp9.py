"""Exp 9 unblinding: map each blind id to its task, state and group, after the judge run.

Run once, after the verdicts are in. It checks the salt against its commitment (exp9-preregistration.md
section 3), recomputes every blind id from the salt, and checks the ids against the verdict files and the
packet directories. Output: exp9-unblinding.json, one entry per state, with no packet content.

Usage: unblind_exp9.py --salt-file FILE --sample FILE --a-result FILE --verdicts-dir DIR --out FILE
"""
import argparse
import glob
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_lib as rl  # noqa: E402

COMMITMENT = '4bd21c633107aafa13ad58023c7bc7c1d9647889c5a7706067825d1195a19e19'
# Group A states with their Exp 7 adjudicated property. Renderable as registered: only 57667013 state_22.
# Renderable under Amendment 2 (section 11): 57667013 state_19, state_20 and state_22.
REGISTERED_RENDERABLE = {('57667013-ea97-417c-9dce-2713091e6e2a', 'state_22')}
AMENDED_RENDERABLE = REGISTERED_RENDERABLE | {('57667013-ea97-417c-9dce-2713091e6e2a', 'state_19'),
                                              ('57667013-ea97-417c-9dce-2713091e6e2a', 'state_20')}


def load_verdict_ids(verdicts_dir):
    ids = set()
    for f in glob.glob(os.path.join(verdicts_dir, 'verdicts_*.json')):
        ids |= set(json.load(open(f, encoding='utf-8')))
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salt-file', required=True)
    ap.add_argument('--sample', required=True)
    ap.add_argument('--a-result', required=True)
    ap.add_argument('--verdicts-dir', required=True)
    ap.add_argument('--packets-dir', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    salt = open(args.salt_file, encoding='utf-8').read().rstrip('\n')
    digest = hashlib.sha256(salt.encode('utf-8')).hexdigest()
    if digest != COMMITMENT:
        raise SystemExit(f'salt does not match the commitment: {digest}')

    sample = json.load(open(args.sample, encoding='utf-8'))
    a_result = {r['bid']: r for r in json.load(open(args.a_result, encoding='utf-8'))}
    entries = []
    for group in 'ABCD':
        for item in sample[group]:
            task, state = item['task'], item['state']
            bid = rl.bid9(salt, task, state)
            e = {'bid': bid, 'group': group, 'task': task, 'state': state,
                 'exp7_label': item.get('label'), 'exp7_corrected': item.get('corrected'),
                 'exp7_spec': item.get('spec'), 'exp7_sol_judge': item.get('judge')}
            if group == 'A':
                key = (task, state)
                e['registered_renderable'] = key in REGISTERED_RENDERABLE
                e['amended_renderable'] = key in AMENDED_RENDERABLE
                e['renderability_check'] = a_result[bid]['check'] if bid in a_result else None
                e['cursor'] = state in ('state_01', 'state_02', 'state_03', 'state_04')
                e['state_17'] = state == 'state_17'
            entries.append(e)

    bids = [e['bid'] for e in entries]
    if len(set(bids)) != len(bids):
        raise SystemExit('duplicate blind ids')
    if len(bids) != 78:
        raise SystemExit(f'{len(bids)} states, expected 78')
    verdict_ids = load_verdict_ids(args.verdicts_dir)
    packet_ids = set(os.listdir(args.packets_dir))
    if set(bids) != verdict_ids or set(bids) != packet_ids:
        raise SystemExit('recomputed blind ids differ from the verdict or packet ids')
    if set(a_result) - set(bids):
        raise SystemExit('a_result ids not in the 78')

    out = {'salt_commitment_checked': True, 'entries': entries}
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write('\n')
    counts = {g: sum(1 for e in entries if e['group'] == g) for g in 'ABCD'}
    print('commitment ok; entries', len(entries), counts)


if __name__ == '__main__':
    main()
