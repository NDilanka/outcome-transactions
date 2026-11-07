"""Exp 10 scoring: policies A, R and A AND R on the 18 requests, the gate, the joint table, and the costs.

Rules are the locked ones in exp10-preregistration.md sections 3 to 8. Verdicts are read from verdicts_*.json files
(keyed by blind id, as in Exp 9). A missing, unparseable or unmatched verdict is undecided. Undecided counts as reject
for R and A AND R. The 4 profile attempts have no packet: their render verdict is undecided by rule.

Usage: exp10_score.py --salt-file FILE --verdicts-dir DIR --stats FILE --packets DIR --batches DIR --out FILE
Run only after the verdicts are saved verbatim. The salt is revealed only after this script has run.
"""
import argparse
import glob
import hashlib
import json
import math
import os

EXP8 = '/home/factory-user/exp8'
GT_FILE = os.path.join(EXP8, 'gt', 'final_gt_v4.tsv')
JUDGE_FILE = os.path.join(EXP8, 'judge', 'judge_by_code.tsv')
MAP_FILE = os.path.join(EXP8, 'private', 'map.json')
EXEC = os.path.join(EXP8, 'exec')
STRICT_W = {'083c86e1': 'W', '81a65c80': 'W', 'a9e34228': 'W'}  # primary: strict auto-save reading
SENS_C = {'083c86e1': 'C', '81a65c80': 'C', 'a9e34228': 'C'}     # sensitivity: all four auto-save candidates C
CONF = {'high': 3, 'medium': 2, 'low': 1}
AUTOSAVE = '2cd43775'
# Renderability flags fixed in section 5 of the preregistration (ecc2413d is decided by page counts).
FIXED_NOT_RENDERABLE = {('2cd43775', 1), ('66399b0d', 4), ('d53ff5ee', 2), ('d53ff5ee', 4)}
ECC2413D_RENDERABLE = {('ecc2413d', 1), ('ecc2413d', 2), ('ecc2413d', 4)}


def bid10(salt, code):
    return hashlib.sha256((salt + '|exp10|' + code).encode()).hexdigest()[:12]


def clopper_pearson(k, n, alpha=0.05):
    """Exact two-sided interval for a binomial proportion, by bisection on the binomial tail."""
    def cdf(x, p):  # P(X <= x)
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, x + 1))

    def solve(f, lo, hi):
        for _ in range(200):
            mid = (lo + hi) / 2
            if f(mid):
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2
    lower = 0.0 if k == 0 else solve(lambda p: 1 - cdf(k - 1, p) >= alpha / 2, 0.0, 1.0)
    upper = 1.0 if k == n else solve(lambda p: cdf(k, p) <= alpha / 2, 0.0, 1.0)
    return lower, upper


def rate(k, n):
    lo, hi = clopper_pearson(k, n)
    return {'k': k, 'n': n, 'rate': round(k / n, 4), 'ci95': [round(lo, 4), round(hi, 4)]}


def load_verdicts(verdicts_dir):
    out = {}
    for f in sorted(glob.glob(os.path.join(verdicts_dir, 'verdicts_*.json'))):
        for bid, e in json.load(open(f, encoding='utf-8')).items():
            if bid in out:
                raise SystemExit(f'{bid} has two verdicts')
            out[bid] = e
    return out


def decide(verdicts, bid):
    e = verdicts.get(bid)
    if not isinstance(e, dict) or e.get('verdict') not in ('accept', 'reject'):
        return 'undecided', None
    return e['verdict'], e.get('confidence')


def load_gt():
    gt = {}
    for line in open(GT_FILE, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        code, verdict = line.split('\t')[:2]
        gt[code] = verdict
    return gt


def load_sol():
    out = {}
    with open(JUDGE_FILE, encoding='utf-8') as fh:
        for line in fh:
            code, verdict, conf = line.rstrip('\n').split('\t')[:3]
            if code == 'code':
                continue
            out[code] = (verdict, conf)
    return out


def pick(cands, accepted, rank):
    """cands in method order. accepted(c) -> True if the candidate is accepted. rank(c) -> sort key (higher wins)."""
    ok = [c for c in cands if accepted(c)]
    if not ok:
        return None
    return max(ok, key=lambda c: (rank(c), -c['method']))


def outcome(commit, gt_label):
    if commit is None:
        return 'confirm'
    return 'correct' if gt_label[commit['code']] == 'C' else 'wrong'


def run_policies(attempts, gt_label):
    """attempts: the 72 primary attempts (dicts). Returns per-request outcomes for A, R and A AND R."""
    by_req = {}
    for a in attempts:
        by_req.setdefault(a['short'], []).append(a)
    res = {'A': {}, 'R': {}, 'AND': {}}
    for short, cands in sorted(by_req.items()):
        cands.sort(key=lambda c: c['method'])
        a_pick = pick(cands, lambda c: c['sol'] == 'accept', lambda c: CONF[c['sol_conf']])
        r_pick = pick(cands, lambda c: c['render'] == 'accept', lambda c: CONF[c['render_conf']])
        ar_pick = pick(cands, lambda c: c['sol'] == 'accept' and c['render'] == 'accept',
                       lambda c: (CONF[c['sol_conf']], CONF[c['render_conf']]))
        res['A'][short] = (outcome(a_pick, gt_label), a_pick)
        res['R'][short] = (outcome(r_pick, gt_label), r_pick)
        res['AND'][short] = (outcome(ar_pick, gt_label), ar_pick)
    return res


def tally(res):
    out = {}
    for pol, rows in res.items():
        vals = [o for o, _ in rows.values()]
        out[pol] = {'G0_correct': vals.count('correct'), 'wrong': vals.count('wrong'),
                    'confirm': vals.count('confirm'), 'requests': len(vals)}
    return out


def gate(res, attempts_by_short):
    """Section 7 of the preregistration. Basis 18: all requests. Basis 17: 2cd43775 removed from all policies."""
    def basis(shorts):
        a_wrong = [s for s in shorts if res['A'][s][0] == 'wrong']
        a_correct = [s for s in shorts if res['A'][s][0] == 'correct']
        removed = [s for s in a_wrong if res['AND'][s][0] != 'wrong']
        kept = [s for s in a_correct if res['AND'][s][0] == 'correct']
        # Basis 18 has 3 A wrong commits (at least 2 removed). Basis 17 has 2 (both must go, which 2 removed means).
        return {'A_wrong': a_wrong, 'A_correct': len(a_correct), 'removed': removed, 'kept': len(kept),
                'removes_at_least_2': len(removed) >= 2, 'keeps_at_least_12_of_A_correct': len(kept) >= 12}
    shorts = sorted(attempts_by_short)
    b18 = basis(shorts)
    b18['pass'] = b18['removes_at_least_2'] and b18['keeps_at_least_12_of_A_correct']
    shorts17 = [s for s in shorts if s != AUTOSAVE]
    b17 = basis(shorts17)
    b17['removes_all_A_wrong'] = set(b17['removed']) == set(b17['A_wrong'])
    b17['pass'] = b17['removes_at_least_2'] and b17['keeps_at_least_12_of_A_correct'] and b17['removes_all_A_wrong']
    return {'basis_18': b18, 'basis_17': b17, 'pass': b18['pass'] and b17['pass']}


def pct(xs, q):
    xs = sorted(xs)
    return xs[max(0, math.ceil(q * len(xs)) - 1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salt-file', required=True)
    ap.add_argument('--verdicts-dir', required=True)
    ap.add_argument('--stats', required=True)
    ap.add_argument('--packets', required=True)
    ap.add_argument('--batches', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    salt = open(args.salt_file, encoding='utf-8').read().rstrip('\n')
    if len(salt) != 64 or hashlib.sha256(salt.encode()).hexdigest() != \
            'a3bdd873ee37ff981732b87d04d0a7fd04b6f2a18a04d705fc927744789ec07d':
        raise SystemExit('salt does not match the commitment in the preregistration')
    stats = json.load(open(args.stats, encoding='utf-8'))
    verdicts = load_verdicts(args.verdicts_dir)
    gt = load_gt()
    sol = load_sol()
    gt_sens = dict(gt, **SENS_C)
    gt_strict = dict(gt, **STRICT_W)
    attempts = []
    for e in json.load(open(MAP_FILE, encoding='utf-8')):
        code = e['code']
        bid = bid10(salt, code)
        profile = e['kind'] == 'profile'
        if not profile and bid not in stats:
            raise SystemExit('a rendered attempt has no stats entry')
        if not profile and not os.path.isdir(os.path.join(args.packets, bid)):
            raise SystemExit('a rendered attempt has no packet')
        rv, rc = decide(verdicts, bid) if not profile else ('undecided', None)
        sv, sc = sol[code]
        a = {'code': code, 'short': e['short'], 'method': e['method_idx'], 'condition': e['condition'],
             'kind': e['kind'], 'bid': bid, 'sol': sv, 'sol_conf': sc, 'render': rv, 'render_conf': rc or 'low'}
        attempts.append(a)
    # The output holds attempt codes only in the per-request policy results, so it stays private until unblinding.
    primary = [a for a in attempts if a['condition'] != 'noui']
    res = run_policies(primary, gt_strict)
    res_sens = run_policies(primary, gt_sens)
    by_short = {}
    for a in primary:
        by_short.setdefault(a['short'], []).append(a)
    gate_res = gate(res, by_short)

    # Joint table over the 80 rendered office states (strict GT).
    office = [a for a in attempts if a['kind'] != 'profile']
    joint = {'wrong': {'both_reject': 0, 'render_only': 0, 'sol_only': 0, 'both_accept': 0},
             'correct': {'both_reject': 0, 'render_only': 0, 'sol_only': 0, 'both_accept': 0}}
    for a in office:
        kind = 'wrong' if gt_strict[a['code']] == 'W' else 'correct'
        s_rej = a['sol'] == 'reject'
        r_rej = a['render'] != 'accept'
        cell = ('both_reject' if s_rej and r_rej else 'render_only' if r_rej else 'sol_only' if s_rej
                else 'both_accept')
        joint[kind][cell] += 1
    profile = [{'method': a['method'], 'gt': gt_strict[a['code']], 'sol': a['sol'], 'sol_conf': a['sol_conf']}
               for a in attempts if a['kind'] == 'profile']

    # Section 5: Sol's first-pass wrong accepts and their renderability.
    wrong_accepts = []
    for a in office + [x for x in attempts if x['kind'] == 'profile']:
        if gt_strict[a['code']] == 'W' and a['sol'] == 'accept':
            key = (a['short'], a['method'])
            if key in ECC2413D_RENDERABLE:
                pages = stats[a['bid']]
                renderable = pages['pages_end'] == pages['pages_start']
                pagecount = (pages['pages_start'], pages['pages_end'])
            else:
                renderable = False
                pagecount = None
            wrong_accepts.append({'short': a['short'], 'method': a['method'], 'condition': a['condition'],
                                  'renderable': renderable, 'pages_start_end': pagecount,
                                  'render': a['render'], 'render_conf': a['render_conf'],
                                  'survives_post_hoc_key': a['kind'] != 'profile'})
    renderable_rejected = sum(1 for w in wrong_accepts if w['renderable'] and w['render'] == 'reject')
    other_rejected = sum(1 for w in wrong_accepts if not w['renderable'] and w['render'] == 'reject')

    # False rejects on correct office states, render against Sol.
    correct_office = [a for a in office if gt_strict[a['code']] == 'C']
    r_false = sum(1 for a in correct_office if a['render'] != 'accept')
    s_false = sum(1 for a in correct_office if a['sol'] == 'reject')

    # Costs (section 8).
    secs = [s['seconds'] for s in stats.values()]
    pngs = [s['pngs'] for s in stats.values()]
    batch_files = sorted(glob.glob(os.path.join(args.batches, 'batch_*.txt')))
    batch_pngs, alone = [], 0
    for f in batch_files:
        group = [b.strip() for b in open(f, encoding='utf-8') if b.strip()]
        batch_pngs.append(sum(stats[b]['pngs'] for b in group))
        if len(group) == 1 and stats[group[0]]['pngs'] > 40:
            alone += 1
    largest = max(stats, key=lambda b: stats[b]['seconds'])
    costs = {
        'render_seconds_median': round(pct(secs, 0.5), 2), 'render_seconds_p90': round(pct(secs, 0.9), 2),
        'render_seconds_max': round(max(secs), 2), 'largest_state_bid': largest,
        'pngs_per_state_max': max(pngs), 'pngs_total': sum(pngs), 'pngs_per_batch_max': max(batch_pngs),
        'batches': len(batch_files), 'states_judged_alone': alone,
        'largest_png_bytes': max(s['max_png_bytes'] for s in stats.values()),
        'pages_reencoded': sum(s['pages_reencoded'] for s in stats.values()),
        'pages_tiled': sum(s['pages_tiled'] for s in stats.values()),
        'render_false_reject_on_correct': rate(r_false, len(correct_office)),
        'sol_false_reject_on_correct': rate(s_false, len(correct_office)),
        'undecided_render_verdicts': sum(1 for a in office if a['render'] == 'undecided'),
    }

    out = {
        'policies': tally(res), 'policies_sensitivity_autosave_all_C': tally(res_sens),
        'per_request': {s: {p: res[p][s][0] for p in res} for s in res['A']},
        'gate': gate_res,
        'joint_office_states': joint,
        'profile_states_sol_only': profile,
        'wrong_accepts_sol_first_pass': wrong_accepts,
        'renderable_wrong_accepts_rejected': renderable_rejected,
        'other_wrong_accepts_rejected': other_rejected,
        'costs': costs,
    }
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1)
        fh.write('\n')
    print(json.dumps({k: out[k] for k in ('policies', 'gate', 'joint_office_states',
                                          'renderable_wrong_accepts_rejected', 'other_wrong_accepts_rejected')},
                     indent=1))
    print(json.dumps(costs, indent=1))


if __name__ == '__main__':
    main()
