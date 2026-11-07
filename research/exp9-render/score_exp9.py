"""Exp 9 scoring: G1, G2 and the reported counts, from the unblinding table and the judge verdicts.

Rules are the locked ones in exp9-preregistration.md sections 5, 6 and 11 (Amendment 2 readings for G1).
A verdict that is missing or not accept/reject is undecided. Undecided counts as a reject for G2 and as a
miss for G1 (section 3).

Usage: score_exp9.py --unblinding FILE --verdicts-dir DIR [--out FILE]
"""
import argparse
import glob
import json
import os

from scipy.stats import beta


def clopper_pearson(k, n, alpha=0.05):
    lo = 0.0 if k == 0 else beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - alpha / 2, k + 1, n - k)
    return float(lo), float(hi)


def load_verdicts(verdicts_dir):
    out = {}
    for f in sorted(glob.glob(os.path.join(verdicts_dir, 'verdicts_*.json'))):
        for bid, e in json.load(open(f, encoding='utf-8')).items():
            out[bid] = e
    return out


def decide(verdicts, bid):
    """Return (state, reason): 'reject', 'accept' or 'undecided'."""
    e = verdicts.get(bid)
    if not isinstance(e, dict) or e.get('verdict') not in ('accept', 'reject'):
        return 'undecided', None
    return e['verdict'], e.get('reason')


def rate(k, n):
    lo, hi = clopper_pearson(k, n)
    return {'k': k, 'n': n, 'rate': round(k / n, 4), 'ci95': [round(lo, 4), round(hi, 4)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--unblinding', required=True)
    ap.add_argument('--verdicts-dir', required=True)
    ap.add_argument('--out')
    args = ap.parse_args()

    entries = json.load(open(args.unblinding, encoding='utf-8'))['entries']
    verdicts = load_verdicts(args.verdicts_dir)
    by_group = {g: [e for e in entries if e['group'] == g] for g in 'ABCD'}
    res = {}

    # Group A: G1 and the states reported separately.
    rows = []
    for e in by_group['A']:
        v, reason = decide(verdicts, e['bid'])
        rows.append({'bid': e['bid'], 'task': e['task'], 'state': e['state'], 'verdict': v, 'reason': reason,
                     'registered_renderable': e['registered_renderable'],
                     'amended_renderable': e['amended_renderable'], 'cursor': e['cursor'],
                     'state_17': e['state_17']})
    res['group_A'] = rows
    reg = [r for r in rows if r['registered_renderable']]
    amd = [r for r in rows if r['amended_renderable']]
    res['G1_registered'] = {'states': [r['state'] for r in reg],
                            'pass': all(r['verdict'] == 'reject' for r in reg) and len(reg) > 0}
    res['G1_amended'] = {'states': [r['state'] for r in amd],
                         'pass': all(r['verdict'] == 'reject' for r in amd) and len(amd) > 0}
    res['G1_headline_pass'] = res['G1_registered']['pass'] and res['G1_amended']['pass']
    res['group_A_not_counted_toward_G1'] = [
        {'state': r['state'], 'task': r['task'], 'verdict': r['verdict'], 'cursor': r['cursor'],
         'state_17': r['state_17']} for r in rows if not r['amended_renderable']]
    res['group_A_rejects'] = sum(1 for r in rows if r['verdict'] == 'reject')

    # Group B and D: G2. Undecided counts as reject. Sol's Exp 7 rejects are taken from the sample file.
    def group_counts(gs):
        states = [e for g in gs for e in by_group[g]]
        rej = sum(1 for e in states if decide(verdicts, e['bid'])[0] != 'accept')
        sol = sum(1 for e in states if e.get('exp7_sol_judge') == 'reject')
        return states, rej, sol

    bd, bd_rej, bd_sol = group_counts('BD')
    b_states, b_rej, b_sol = group_counts('B')
    d_states, d_rej, d_sol = group_counts('D')
    res['G2'] = {'render_BD': rate(bd_rej, len(bd)), 'sol_BD': rate(bd_sol, len(bd)),
                 'pass': bd_rej <= bd_sol,
                 'render_B': rate(b_rej, len(b_states)), 'sol_B': rate(b_sol, len(b_states)),
                 'render_D': rate(d_rej, len(d_states)), 'sol_D': rate(d_sol, len(d_states)),
                 'undecided_BD': sum(1 for e in bd if decide(verdicts, e['bid'])[0] == 'undecided')}
    res['BD_rejected_states'] = [
        {'group': e['group'], 'task': e['task'], 'state': e['state'],
         'verdict': decide(verdicts, e['bid'])[0], 'reason': decide(verdicts, e['bid'])[1]}
        for e in bd if decide(verdicts, e['bid'])[0] != 'accept']

    # Group C: reject count (undecided counted as reject, reported separately as well).
    c = by_group['C']
    c_rej = sum(1 for e in c if decide(verdicts, e['bid'])[0] == 'reject')
    c_und = sum(1 for e in c if decide(verdicts, e['bid'])[0] == 'undecided')
    c_sol = sum(1 for e in c if e.get('exp7_sol_judge') == 'reject')
    res['C'] = {'render_reject': rate(c_rej, len(c)), 'undecided': c_und, 'sol_reject': rate(c_sol, len(c)),
                'rejects': [{'bid': e['bid'], 'task': e['task'], 'state': e['state'],
                             'reason': decide(verdicts, e['bid'])[1]}
                            for e in c if decide(verdicts, e['bid'])[0] == 'reject']}

    res['undecided_total'] = sum(1 for e in entries if decide(verdicts, e['bid'])[0] == 'undecided')
    res['verdict_counts'] = {v: sum(1 for e in entries if decide(verdicts, e['bid'])[0] == v)
                             for v in ('accept', 'reject', 'undecided')}
    text = json.dumps(res, indent=1, ensure_ascii=False)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
