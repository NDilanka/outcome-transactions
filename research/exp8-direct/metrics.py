"""Exp 8 metrics: arms, headline and safety gates, per-request table, speed and resource numbers.

Inputs (private, not committed, except as summarised in exp8-results.md):
  gt:     /home/factory-user/exp8/gt/final_gt_v3.tsv     code, verdict (C/W), ambiguous (Y/N)
  spec:   /home/factory-user/exp8/specs/<code>.json       executor c909d02 decision per attempt
  exec:   /home/factory-user/exp8/exec/<code>/result.json harness: generation_s, wall_s, cpu_s, peak_rss_mb
  map:    /home/factory-user/exp8/private/map.json        attempt -> task (short), method_idx, condition
  judge:  /home/factory-user/exp8/judge/judge_by_code.tsv code, verdict (accept/reject), confidence (low/medium/high)

Primary set: 72 attempts (condition none or ui), 18 requests, 4 methods each.
Ablation: 12 noui attempts for the three tasks that also have a ui condition (compared with their ui attempts).
Arms (one commit per request, method order breaks ties; highest judge confidence first):
  A   judge only: commit the judge accept with the highest confidence
  B   two-key: AUTO iff spec ACCEPT and judge accept
  Bs  spec only: AUTO iff spec ACCEPT (ablation of B without the judge)
A correct zero-click commit: the committed attempt is GT C. A wrong commit: committed attempt is GT W.
No commit is a CONFIRM. CONFIRM tag, in priority order: AMBIGUOUS if any candidate's GT flag is Y; GAP if any candidate's
executor decision is UNDECIDED or the executor and the judge disagree on a candidate; otherwise PLAIN.
"""
import csv, json, math, os, statistics, sys

GT = '/home/factory-user/exp8/gt/final_gt_v3.tsv'
SPEC = '/home/factory-user/exp8/specs'
EXEC = '/home/factory-user/exp8/exec'
MAP = '/home/factory-user/exp8/private/map.json'
JUDGE = '/home/factory-user/exp8/judge/judge_by_code.tsv'
CONF = {'low': 1, 'medium': 2, 'high': 3}
# Judge phase, from commit times on origin: packets 307ced3 at 10:53:04 UTC, verdicts dbc95e0 at 11:14:04 UTC.
# 21 min for 84 packets (six batches of 14, two batches rerun). The per-packet judge time was not measured.
# If the packets were judged one after another, that is 15 s each (JUDGE_EST_S). If the six batches ran in
# parallel, each packet took up to about 90 s (JUDGE_PAR_S). Both are estimates, not measurements.
JUDGE_EST_S = 1260 / 84
JUDGE_PAR_S = 1260 / 14


def load_gt():
    out = {}
    for line in open(GT):
        if line.startswith('#') or not line.strip():
            continue
        c, v, a = line.split('\t')[:3]
        out[c] = (v, a)
    return out


def load_attempts():
    gt = load_gt()
    judge = {r['code']: (r['verdict'], CONF[r['confidence']]) for r in
             csv.DictReader(open(JUDGE), delimiter='\t')}
    rows = []
    for e in json.load(open(MAP)):
        c = e['code']
        spec = json.load(open(os.path.join(SPEC, c + '.json')))
        res = json.load(open(os.path.join(EXEC, c, 'result.json')))
        j = judge.get(c, (None, None))
        rows.append({
            'code': c, 'short': e['short'], 'method_idx': e['method_idx'], 'condition': e['condition'],
            'gt': gt[c][0], 'amb': gt[c][1], 'spec': spec['decision'],
            'judge': j[0], 'conf': j[1] or 0,
            'gen_s': res['generation_s'], 'exec_wall_s': res['wall_s'], 'exec_cpu_s': res['cpu_s'],
            'exec_rss_mb': res['peak_rss_mb'], 'spec_wall_s': spec['proc_wall_s'],
            'spec_cpu_s': spec['proc_cpu_s'], 'spec_rss_mb': spec['proc_peak_rss_mb'],
        })
    return rows


def pct(xs, q):
    xs = sorted(xs)
    return xs[max(0, math.ceil(q * len(xs)) - 1)]


def arm_pick(cands, arm):
    """cands: the attempts of one request, in method order. Returns the committed attempt or None."""
    if arm == 'Bs':
        ok = [a for a in cands if a['spec'] == 'ACCEPT']
    elif arm == 'A':
        ok = [a for a in cands if a['judge'] == 'accept']
    elif arm == 'B':
        ok = [a for a in cands if a['spec'] == 'ACCEPT' and a['judge'] == 'accept']
    else:
        raise ValueError(arm)
    if not ok:
        return None
    if arm == 'Bs':
        return ok[0]
    return max(ok, key=lambda a: (a['conf'], -a['method_idx']))


def confirm_tag(cands):
    if any(a['amb'] == 'Y' for a in cands):
        return 'AMBIGUOUS'
    disagree = any((a['spec'] == 'ACCEPT') != (a['judge'] == 'accept') for a in cands)
    if disagree or any(a['spec'] == 'UNDECIDED' for a in cands):
        return 'GAP'
    return 'PLAIN'


def group(rows):
    by_req = {}
    for a in rows:
        by_req.setdefault(a['short'], []).append(a)
    return {k: sorted(v, key=lambda a: a['method_idx']) for k, v in sorted(by_req.items())}


def arm_report(rows, arm):
    out = {'requests': 0, 'correct_zero_click': 0, 'wrong_commit': 0, 'confirm': 0,
           'confirm_tags': {'AMBIGUOUS': 0, 'GAP': 0, 'PLAIN': 0}, 'wrong_commit_tasks': []}
    for short, cands in group(rows).items():
        out['requests'] += 1
        pick = arm_pick(cands, arm)
        if pick is None:
            out['confirm'] += 1
            out['confirm_tags'][confirm_tag(cands)] += 1
        elif pick['gt'] == 'C':
            out['correct_zero_click'] += 1
        else:
            out['wrong_commit'] += 1
            out['wrong_commit_tasks'].append(f"{short}:{pick['code']}")
    n = out['requests']
    out['G0_correct_zero_click_share'] = round(out['correct_zero_click'] / n, 3)
    out['wrong_commits_per_request'] = round(out['wrong_commit'] / n, 3)
    out['confirm_share'] = round(out['confirm'] / n, 3)
    out['gap_share'] = round(out['confirm_tags']['GAP'] / n, 3)
    return out


def per_request_table(rows):
    lines = ['| task | GT by method (A-D) | spec | judge (conf) | A commit | B commit | Bs commit | CONFIRM tag |',
             '|---|---|---|---|---|---|---|---|']
    for short, cands in group(rows).items():
        gts = ''.join(a['gt'] for a in cands)
        spec = ' '.join(a['spec'][:3] for a in cands)
        judge = ' '.join(f"{'acc' if a['judge'] == 'accept' else 'rej'}({['', 'l', 'm', 'h'][a['conf']]})" for a in cands)

        def show(p):
            return 'none' if p is None else f"{p['method_idx']}:{p['gt']}"
        pa, pb, ps = arm_pick(cands, 'A'), arm_pick(cands, 'B'), arm_pick(cands, 'Bs')
        tag = confirm_tag(cands) if pb is None else ''
        lines.append(f"| {short} | {gts} | {spec} | {judge} | {show(pa)} | {show(pb)} | {show(ps)} | {tag} |")
    return '\n'.join(lines)


def ablation(rows):
    """ui vs noui for the tasks that have both (judge and spec see the same end states; only the UI block differs)."""
    both = {a['short'] for a in rows if a['condition'] == 'noui'}
    out = {}
    for cond in ('ui', 'noui'):
        sub = [a for a in rows if a['short'] in both and a['condition'] == cond]
        out[cond] = {arm: arm_report(sub, arm) for arm in ('A', 'B', 'Bs')}
        out[cond]['gt_C_share'] = round(sum(a['gt'] == 'C' for a in sub) / len(sub), 3)
    return out


def speed(rows):
    tot = [a['gen_s'] + a['exec_wall_s'] + a['spec_wall_s'] + JUDGE_EST_S for a in rows]
    return {'n': len(tot), 'median_s': round(statistics.median(tot), 1), 'p90_s': round(pct(tot, 0.9), 1),
            'max_s': round(max(tot), 1), 'gen_median_s': round(statistics.median(a['gen_s'] for a in rows), 1),
            'exec_median_s': round(statistics.median(a['exec_wall_s'] for a in rows), 3),
            'spec_median_s': round(statistics.median(a['spec_wall_s'] for a in rows), 3),
            'judge_est_s': round(JUDGE_EST_S, 1)}


def resources(rows):
    cpu = [a['exec_cpu_s'] + a['spec_cpu_s'] for a in rows]
    rss = [max(a['exec_rss_mb'], a['spec_rss_mb']) for a in rows]
    return {'cpu_s_median': round(statistics.median(cpu), 2), 'cpu_s_p90': round(pct(cpu, 0.9), 2),
            'cpu_s_max': round(max(cpu), 2), 'peak_rss_mb_median': round(statistics.median(rss), 1),
            'peak_rss_mb_p90': round(pct(rss, 0.9), 1), 'peak_rss_mb_max': round(max(rss), 1)}


def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def bisect(f, lo=0.0, hi=1.0):
    """f is increasing on [lo, hi]; returns x with f(x) = 0 (to 1e-12)."""
    for _ in range(100):
        mid = (lo + hi) / 2
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def cp_interval(k, n, alpha=0.05):
    """Clopper-Pearson interval with two-sided level 1 - alpha. Exact binomial, no scipy."""
    lo = 0.0 if k == 0 else bisect(lambda p: (1 - binom_cdf(k - 1, n, p)) - alpha / 2)
    hi = 1.0 if k == n else bisect(lambda p: alpha / 2 - binom_cdf(k, n, p))
    return round(lo, 3), round(hi, 3)


def cp_upper_one_sided(k, n, conf=0.95):
    """Exact one-sided upper bound on a proportion at confidence conf (the north-star's 95% UB)."""
    return 1.0 if k == n else round(bisect(lambda p: (1 - conf) - binom_cdf(k, n, p)), 3)


def random_tie_expectation(rows, arm):
    """Expected counts when the arm breaks ties uniformly at random instead of by confidence and method order.
    A and B: uniform among the candidates with the highest judge confidence in the arm's set.
    Bs: uniform among all spec ACCEPT candidates."""
    e = {'correct': 0.0, 'wrong': 0.0, 'confirm': 0.0}
    for cands in group(rows).values():
        if arm == 'Bs':
            ok = [a for a in cands if a['spec'] == 'ACCEPT']
        elif arm == 'A':
            ok = [a for a in cands if a['judge'] == 'accept']
        else:
            ok = [a for a in cands if a['spec'] == 'ACCEPT' and a['judge'] == 'accept']
        if ok and arm != 'Bs':
            top = max(a['conf'] for a in ok)
            ok = [a for a in ok if a['conf'] == top]
        if not ok:
            e['confirm'] += 1
            continue
        e['correct'] += sum(a['gt'] == 'C' for a in ok) / len(ok)
        e['wrong'] += sum(a['gt'] == 'W' for a in ok) / len(ok)
    return {k: round(v, 3) for k, v in e.items()}


def timing_per_request(rows):
    """Per request, the four methods run in parallel (assumed); the request waits for the slowest. Two judge
    settings: JUDGE_EST_S (serial estimate) and JUDGE_PAR_S (parallel-batch estimate). Spec-only needs no judge."""
    out = {}
    for name, judge_s in (('no_judge', 0.0), ('judge_serial_est', JUDGE_EST_S), ('judge_parallel_est', JUDGE_PAR_S)):
        per_req = [max(a['gen_s'] + a['exec_wall_s'] + a['spec_wall_s'] + judge_s for a in cands)
                   for cands in group(rows).values()]
        out[name] = {'median_s': round(statistics.median(per_req), 1), 'p90_s': round(pct(per_req, 0.9), 1),
                     'max_s': round(max(per_req), 1)}
    return out


def timing_split(rows):
    """Measured and inferred parts of the per-attempt time, medians over attempts."""
    med = lambda xs: round(statistics.median(xs), 3)
    return {'gen_inferred_median_s': med([a['gen_s'] for a in rows]),
            'gen_inferred_p90_s': round(pct([a['gen_s'] for a in rows], 0.9), 1),
            'exec_wall_median_s': med([a['exec_wall_s'] for a in rows]),
            'spec_wall_median_s': med([a['spec_wall_s'] for a in rows]),
            'exec_cpu_median_s': med([a['exec_cpu_s'] for a in rows]),
            'spec_cpu_median_s': med([a['spec_cpu_s'] for a in rows]),
            'exec_rss_median_mb': med([a['exec_rss_mb'] for a in rows]),
            'spec_rss_median_mb': med([a['spec_rss_mb'] for a in rows])}


def crosstab(rows):
    """Spec decision x judge verdict x GT verdict, for all attempts."""
    keys = {}
    for a in rows:
        k = (a['spec'], a['judge'], a['gt'])
        keys[k] = keys.get(k, 0) + 1
    return keys


if __name__ == '__main__':
    rows = load_attempts()
    primary = [a for a in rows if a['condition'] in ('none', 'ui')]
    wrong = [a for a in rows if a['gt'] == 'W']
    print('attempts', len(rows), 'primary', len(primary), 'ablation', len(rows) - len(primary))
    print('GT C/W (all 84):', sum(a['gt'] == 'C' for a in rows), sum(a['gt'] == 'W' for a in rows),
          'ambiguous Y:', sum(a['amb'] == 'Y' for a in rows))
    print('GT wrong end states (all 84):', len(wrong), 'in primary:', sum(a['condition'] in ('none', 'ui') for a in wrong))
    print('spec ACCEPT on wrong:', sum(a['spec'] == 'ACCEPT' for a in wrong),
          'judge accept on wrong:', sum(a['judge'] == 'accept' for a in wrong),
          'both (two-key passes wrong):', sum(a['spec'] == 'ACCEPT' and a['judge'] == 'accept' for a in wrong))
    print('judge accept: C', sum(a['judge'] == 'accept' and a['gt'] == 'C' for a in rows),
          'W', sum(a['judge'] == 'accept' and a['gt'] == 'W' for a in rows),
          '| judge reject: C', sum(a['judge'] == 'reject' and a['gt'] == 'C' for a in rows),
          'W', sum(a['judge'] == 'reject' and a['gt'] == 'W' for a in rows))
    print('spec decision counts:', {d: sum(a['spec'] == d for a in rows) for d in ('ACCEPT', 'REJECT', 'UNDECIDED')})
    print('crosstab (spec, judge, gt) -> count:', json.dumps({'/'.join(k): v for k, v in sorted(crosstab(rows).items())}))
    print('speed (all 84)', json.dumps(speed(rows)))
    print('speed (primary 72)', json.dumps(speed(primary)))
    print('timing split (all 84)', json.dumps(timing_split(rows)))
    print('timing per request (primary 72, slowest of four, parallel assumed)', json.dumps(timing_per_request(primary)))
    print('resources (all 84)', json.dumps(resources(rows)))
    for arm in ('A', 'B', 'Bs'):
        r = arm_report(primary, arm)
        n, c, w = r['requests'], r['correct_zero_click'], r['wrong_commit']
        print('ARM', arm, json.dumps(r))
        print('  G0 95% CI (Clopper-Pearson):', cp_interval(c, n), '| wrong commits 1-sided 95% UB per request:',
              cp_upper_one_sided(w, n), '| random tie-break expected:', json.dumps(random_tie_expectation(primary, arm)))
    print('ABLATION ui vs noui on 3 tasks:', json.dumps(ablation(rows)))
    n_wrong = len(wrong)
    n_pass = sum(a['spec'] == 'ACCEPT' and a['judge'] == 'accept' for a in wrong)
    print('two-key pass rate on wrong end states', n_pass, 'of', n_wrong, 'CI (Clopper-Pearson 95%):',
          cp_interval(n_pass, n_wrong))
    print('G3 per-attempt, no judge (gen + exec + spec) median s:',
          round(statistics.median(a['gen_s'] + a['exec_wall_s'] + a['spec_wall_s'] for a in rows), 1))
    cpu_req = [sum(a['exec_cpu_s'] + a['spec_cpu_s'] for a in cands) for cands in group(primary).values()]
    rss_req = [max(max(a['exec_rss_mb'], a['spec_rss_mb']) for a in cands) for cands in group(primary).values()]
    print('G7 per request (4 candidates, primary): CPU-s median', round(statistics.median(cpu_req), 2),
          'max', round(max(cpu_req), 2), '| peak RSS median', round(statistics.median(rss_req), 1),
          'max', round(max(rss_req), 1))
    # Sensitivity: auto-save family (2cd43775). The end-state profiles of 083c86e1, 81a65c80 and a9e34228 do not set
    # UserAutoSaveEnabled to true (76604199 does). Count those three as wrong to test the strict reading.
    strict_wrong = {'083c86e1', '81a65c80', 'a9e34228'}
    alt = [dict(a, gt='W') if a['code'] in strict_wrong else a for a in primary]
    for arm in ('A', 'B', 'Bs'):
        r = arm_report(alt, arm)
        print('SENSITIVITY autosave strict', arm, 'correct', r['correct_zero_click'], 'wrong', r['wrong_commit'],
              'confirm', r['confirm'], r['wrong_commit_tasks'])
    print(per_request_table(primary))
