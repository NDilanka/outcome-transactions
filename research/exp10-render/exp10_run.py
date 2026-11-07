"""Exp 10 render: the 80 office attempts of Exp 8, each end state against its input, through render_lib.py at 4bc82d0.

Frozen at the lock commit; see exp10-preregistration.md. The 84 Exp 8 attempts are read from the private map and exec
results, outside the repository. The 4 profile attempts (the auto-save request 2cd43775) are LibreOffice user profile
folders, not office files, so they are not rendered and get no packet. Nothing is written inside the repository.

Output (paths given on the command line): packets/<bid>/request.txt, start/, end/ (PNG pages); batches/batch_NN.txt;
stats.json (per blind id: page and PNG counts, timings, Amendment 3 actions); input_manifest.json (sha256 of every
input file per blind id, no names).

Usage: exp10_run.py --salt-file FILE --packets DIR --work DIR --stats FILE --batches DIR --manifest FILE
"""
import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_lib as rl  # noqa: E402

EXP8_MAP = '/home/factory-user/exp8/private/map.json'
EXP8_EXEC = '/home/factory-user/exp8/exec'
EXP8_PACKETS = os.path.join(HERE, '..', 'exp8-direct', 'judge_packets')  # the Exp 8 packets, for the UI block text
MAX_PNG_PER_BATCH = 40
BATCH_SIZE = 4
EXPECTED_OFFICE = 80
EXPECTED_PROFILE = 4
LEAK_NEEDLES = ['solve.py', 'exp4b', 'exp8', 'exp10', 'osworld', '/home/factory-user', 'exp5', 'exp6', 'exp7', 'exp9',
                'specexec']
WORD_NEEDLES = re.compile(r'\b(spec|specs|judge|judges|executor|checker|checkers)\b', re.I)


def bid10(salt, code):
    """Fresh salted blind id: sha256(SALT + "|exp10|" + attempt code)[:12]. salt is the SALT text, no final newline."""
    return hashlib.sha256((salt + '|exp10|' + code).encode()).hexdigest()[:12]


def legacy_bid(code):
    """The Exp 8 packet id (unsalted). Used only to read the UI block text the Exp 8 judge saw."""
    return hashlib.sha256(('exp8|' + code).encode()).hexdigest()[:12]


def ui_text(code):
    with open(os.path.join(EXP8_PACKETS, legacy_bid(code) + '.json'), encoding='utf-8') as fh:
        return json.load(fh)['ui_state']


def make_batches(bids, pngs):
    """Copied from render_all.py at 4bc82d0. Consecutive groups of 4 over sorted bids, split by PNG total."""
    batches = []
    ordered = sorted(bids)
    for i in range(0, len(ordered), BATCH_SIZE):
        group = ordered[i:i + BATCH_SIZE]
        if sum(pngs[b] for b in group) <= MAX_PNG_PER_BATCH:
            batches.append(group)
            continue
        cur = []
        for b in group:
            if cur and sum(pngs[x] for x in cur) + pngs[b] > MAX_PNG_PER_BATCH:
                batches.append(cur)
                cur = []
            cur.append(b)
        if cur:
            batches.append(cur)
    return batches


def leak_check(packets, codes, shorts):
    """Fail on any task id, attempt code, run path or judge/spec word in a request.txt, and on any unexpected file."""
    bad = []
    ids = set(codes) | set(shorts)
    for bid in sorted(os.listdir(packets)):
        d = os.path.join(packets, bid)
        if sorted(os.listdir(d)) != ['end', 'request.txt', 'start']:
            bad.append((bid, 'unexpected entries'))
        text = open(os.path.join(d, 'request.txt'), encoding='utf-8').read()
        bad += [(bid, n) for n in LEAK_NEEDLES + sorted(ids) if n in text]
        bad += [(bid, m.lower()) for m in set(WORD_NEEDLES.findall(text))]
    print('leak check:', 'PASS' if not bad else f'FAIL {len(bad)} hits {bad[:5]}', flush=True)
    return not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salt-file', required=True)
    ap.add_argument('--packets', required=True)
    ap.add_argument('--work', required=True)
    ap.add_argument('--stats', required=True)
    ap.add_argument('--batches', required=True)
    ap.add_argument('--manifest', required=True)
    args = ap.parse_args()

    salt = open(args.salt_file, encoding='utf-8').read().rstrip('\n')
    if len(salt) != 64:
        raise SystemExit('salt must be 64 hex characters')
    entries = json.load(open(EXP8_MAP))
    office = [e for e in entries if e['kind'] != 'profile']
    profile = [e for e in entries if e['kind'] == 'profile']
    if len(office) != EXPECTED_OFFICE or len(profile) != EXPECTED_PROFILE:
        raise SystemExit(f'{len(office)} office and {len(profile)} profile attempts; expected {EXPECTED_OFFICE} and '
                         f'{EXPECTED_PROFILE}')
    if os.path.exists(args.packets) and os.listdir(args.packets):
        raise SystemExit(f'{args.packets} is not empty')

    jobs = sorted(((bid10(salt, e['code']), e) for e in office), key=lambda x: x[0])
    if len({b for b, _ in jobs}) != len(jobs):
        raise SystemExit('blind id collision')
    stats, manifest = {}, {}
    os.makedirs(args.packets)
    for bid, e in jobs:
        res = json.load(open(os.path.join(EXP8_EXEC, e['code'], 'result.json'), encoding='utf-8'))
        if not res.get('end_state'):
            raise SystemExit(f'{bid}: attempt has no end state')
        before = os.path.dirname(e['input_path'])
        after = os.path.dirname(res['end_state'])
        request = rl.request_for(e['full_id'])
        if e['condition'] == 'ui':
            request = request.rstrip('\n') + '\n\nLive UI state:\n' + ui_text(e['code']).rstrip('\n')
        manifest[bid] = {'start': [h for _, h in rl.tree_hashes(before)],
                         'end': [h for _, h in rl.tree_hashes(after)]}
        st, _ = rl.render_state(before, after, bid, request, args.packets, args.work)
        stats[bid] = st
        print(bid, 'pngs', st['pngs'], 'pages', st['pages_start'], st['pages_end'], 'seconds', st['seconds'],
              flush=True)

    if len(stats) != EXPECTED_OFFICE:
        raise SystemExit(f'{len(stats)} states rendered, expected {EXPECTED_OFFICE}')
    with open(args.stats, 'w', encoding='utf-8') as fh:
        json.dump(stats, fh, indent=1)
        fh.write('\n')
    with open(args.manifest, 'w', encoding='utf-8') as fh:
        json.dump(dict(sorted(manifest.items())), fh, indent=1)
        fh.write('\n')

    pngs = {b: stats[b]['pngs'] for b in stats}
    batches = make_batches(list(stats), pngs)
    os.makedirs(args.batches)
    for k, group in enumerate(batches, 1):
        with open(os.path.join(args.batches, f'batch_{k:02d}.txt'), 'w') as fh:
            fh.write('\n'.join(group) + '\n')
    print('states:', len(stats), 'batches:', len(batches),
          'max PNG per batch:', max(sum(pngs[b] for b in g) for g in batches), flush=True)
    codes = [e['code'] for e in entries]
    shorts = sorted({e['short'] for e in entries})
    ok = leak_check(args.packets, codes, shorts)
    if not ok:
        raise SystemExit('leak check failed; do not publish these packets')


if __name__ == '__main__':
    main()
