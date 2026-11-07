"""Render the Exp 9 states that renderability_checks.py did not render, then cut all 78 into judge batches.

Frozen at the lock commit; see exp9-preregistration.md sections 3 and 6. Renders here: groups B, C and D
(70 states) and the four group A cursor states (no check, judged and reported separately). The four
renderable group A states were rendered by renderability_checks.py, and their packets are reused.
Nothing is written inside the repository.

Batch rule: sort the blind ids, cut them into consecutive groups of 4. If a group's PNG total is over
MAX_PNG_PER_BATCH, split it into consecutive runs, taking states in order while the total stays within the cap.
A state alone over the cap is its own batch. Splits depend only on PNG counts.

Usage: render_all.py --salt-file FILE --sample FILE --states DIR --packets DIR --work DIR --a-result FILE
                     --stats FILE --batches DIR

Amendment 3 (exp9-preregistration.md section 12): the renderability_checks.py states keep their packets, and
their stats gain the Amendment 3 keys, derived from their files (kept_stats).
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_lib as rl  # noqa: E402

MAX_PNG_PER_BATCH = 40
BATCH_SIZE = 4
EXPECTED_STATES = 78


def kept_stats(packet, st):
    """Amendment 3 keys for a state rendered before Amendment 3, by renderability_checks.py.

    That code wrote every page as PyMuPDF wrote it. The files are checked here: one PNG per page, named as
    section 3 says, each at most the read limit. Under section 12 such pages are kept as written.
    """
    names = [os.path.join(side, f) for side in ('start', 'end') for f in sorted(os.listdir(os.path.join(packet, side)))]
    if len(names) != st['pngs'] or st['pages_start'] + st['pages_end'] != st['pngs']:
        raise SystemExit(f"{st['bid']}: packet files do not match the render stats")
    if not all(re.fullmatch(r'f\d{2}_p\d{3}\.png', os.path.basename(n)) for n in names):
        raise SystemExit(f"{st['bid']}: unexpected file name in packet")
    if any(os.path.getsize(os.path.join(packet, n)) > rl.READ_LIMIT_BYTES for n in names):
        raise SystemExit(f"{st['bid']}: a page is over the read limit")
    return dict(st, pages_kept=st['pngs'], pages_reencoded=0, pages_tiled=0, tiles=0)


def make_batches(bids, pngs):
    """Consecutive groups of 4 over sorted bids, split by PNG total. A pure function of bids and counts."""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salt-file', required=True)
    ap.add_argument('--sample', required=True)
    ap.add_argument('--states', required=True)
    ap.add_argument('--packets', required=True)
    ap.add_argument('--work', required=True)
    ap.add_argument('--a-result', required=True)
    ap.add_argument('--stats', required=True)
    ap.add_argument('--batches', required=True)
    args = ap.parse_args()

    salt = open(args.salt_file, encoding='utf-8').read().rstrip('\n')
    sample = json.load(open(args.sample))
    a_rows = json.load(open(args.a_result))
    stats = {}
    for r in a_rows:
        if r['check'] is not None:
            # rendered by renderability_checks.py, packets reused as is (pass or fail)
            stats[r['bid']] = kept_stats(os.path.join(args.packets, r['bid']), r['render'])

    todo = [(r['bid'], r['task'], r['state']) for r in a_rows if r['check'] is None]
    todo += [(rl.bid9(salt, item['task'], item['state']), item['task'], item['state'])
             for group in 'BCD' for item in sample[group]]
    for bid, task, state in todo:
        if bid in stats:
            raise SystemExit(f'state rendered twice: {bid}')
        st, _ = rl.render_state(os.path.join(rl.SNAPSHOTS, task), os.path.join(args.states, task, state),
                                bid, rl.request_for(task), args.packets, args.work)
        stats[bid] = st
        print(bid, st, flush=True)
    if len(stats) != EXPECTED_STATES:
        raise SystemExit(f'{len(stats)} states rendered, expected {EXPECTED_STATES}')

    with open(args.stats, 'w', encoding='utf-8') as fh:
        json.dump(stats, fh, indent=1)
    pngs = {b: stats[b]['pngs'] for b in stats}
    batches = make_batches(list(stats), pngs)
    os.makedirs(args.batches, exist_ok=True)
    for k, group in enumerate(batches, 1):
        with open(os.path.join(args.batches, f'batch_{k:02d}.txt'), 'w') as fh:
            fh.write('\n'.join(group) + '\n')
    print('states:', len(stats), 'batches:', len(batches),
          'max PNG per batch:', max(sum(pngs[b] for b in g) for g in batches))


if __name__ == '__main__':
    main()
