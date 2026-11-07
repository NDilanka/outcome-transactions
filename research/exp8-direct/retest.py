"""Exp 8: judge self-consistency key (second independent pass). POST-HOC, not pre-registered.

Key: a judge accept counts only if the second pass also accepts. Two confidence rules for a kept accept:
  first  the first-pass confidence (the rule in the report)
  min    the lower of the two passes' confidence labels (sensitivity)
Both passes are read from origin/exp8-judge-verdicts (commit 29fc5bd): first pass judge_verdicts/, second pass
judge_retest/. The first-pass TSV used by metrics.py is checked against the first-pass files.

Run with the exp8 venv (the agreement module needs PIL):
  /home/factory-user/venvs/exp8/bin/python retest.py > retest_output.txt
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import metrics as mt  # noqa: E402
import agreement as ag  # noqa: E402

REF = 'origin/exp8-judge-verdicts'
FIRST = 'research/exp8-direct/judge_verdicts'
SECOND = 'research/exp8-direct/judge_retest'
BLIND_MAP = '/home/factory-user/exp8/private/judge_blind_map.json'
CONF = {'low': 1, 'medium': 2, 'high': 3}
LABEL = {v: k for k, v in CONF.items()}
# Flips the orchestrator reported. Checked against the files in verify().
REPORTED_FLIPS = {'3511fd7a3d42', '8ee85506bb17', 'b449eafdbc3c', 'b6350f5f647e'}


def read_pass(prefix):
    out = {}
    for i in range(6):
        raw = subprocess.check_output(['git', '-C', REPO, 'show', f'{REF}:{prefix}/verdicts_{i}.json'])
        for k, v in json.loads(raw).items():
            assert k not in out, k
            out[k] = v
    return out


def verify(first, second, bm):
    """Checks on the two passes. Prints the numbers the report quotes."""
    code_of = bm
    assert set(first) == set(second) == set(code_of), 'blind id sets differ'
    print(f'packets: first {len(first)}, second {len(second)}, blind map {len(code_of)}')
    flips = sorted(b for b in first if first[b]['verdict'] != second[b]['verdict'])
    directions = {f"{first[b]['verdict']}->{second[b]['verdict']}" for b in flips}
    print(f'flips: {len(flips)} ({", ".join(sorted(directions)) or "none"})')
    for b in flips:
        print(f'  {code_of[b]} first {first[b]["verdict"]} {first[b]["confidence"]}, second {second[b]["verdict"]} '
              f'{second[b]["confidence"]}')
    print(f'flip list matches report: {set(flips) == REPORTED_FLIPS}')
    print(f'second pass alone: accept {sum(v["verdict"] == "accept" for v in second.values())}, '
          f'reject {sum(v["verdict"] == "reject" for v in second.values())}')
    same_conf = sum(first[b]['confidence'] == second[b]['confidence'] for b in first)
    print(f'confidence labels matched: {same_conf} of {len(first)}')
    print('first-pass confidence of flipped packets:', {c: sum(first[b]['confidence'] == c for b in flips)
                                                       for c in ('high', 'medium', 'low')})
    print('first-pass confidence of all packets:', {c: sum(first[b]['confidence'] == c for b in first)
                                                   for c in ('high', 'medium', 'low')})
    both_high = [b for b in first if first[b]['confidence'] == 'high' and second[b]['confidence'] == 'high']
    print(f'rated high in both passes: {len(both_high)}, of which flipped: '
          f'{sum(b in set(flips) for b in both_high)}')
    print()
    return flips


def check_first_tsv(first, bm):
    """The first-pass TSV that metrics.py reads must equal the first-pass files on the branch."""
    tsv = {}
    for line in open(mt.JUDGE):
        r = line.rstrip('\n').split('\t')
        if r[0] == 'code':
            continue
        tsv[r[0]] = (r[1], r[2])
    bad = [b for b in first if tsv.get(bm[b]) != (first[b]['verdict'], first[b]['confidence'])]
    print(f'first-pass TSV (metrics.py input) vs first-pass files: {len(first) - len(bad)} of {len(first)} match')
    print()


def key_rows(rows, second, bm, rule):
    code_to_blind = {v: k for k, v in bm.items()}
    out = []
    for a in rows:
        b = dict(a)
        s = second[code_to_blind[a['code']]]
        if a['judge'] == 'accept' and s['verdict'] == 'accept':
            b['judge'] = 'accept'
            if rule == 'min':
                b['conf'] = min(a['conf'], CONF[s['confidence']])
        else:
            b['judge'] = 'reject'
        out.append(b)
    return out


def picks_for(rows, sigs):
    primary = [a for a in rows if a['condition'] in ('none', 'ui')]
    grouped = mt.group(primary)
    picks = {arm: {s: mt.arm_pick(c, arm) for s, c in grouped.items()} for arm in ('A', 'B', 'Bs')}
    picks['C'] = {s: ag.policy_pick(c, sigs, 'C') for s, c in grouped.items()}
    picks['D'] = {s: ag.policy_pick(c, sigs, 'D') for s, c in grouped.items()}
    return primary, grouped, picks


def show(p):
    return 'none' if p is None else f"{p['method_idx']}:{p['gt']}({p['code']})"


def main():
    bm = json.load(open(BLIND_MAP))
    code_to_blind = {v: k for k, v in bm.items()}
    first = read_pass(FIRST)
    second = read_pass(SECOND)
    print('== verification (branch files at ' + REF + ')')
    check_first_tsv(first, bm)
    flips = verify(first, second, bm)

    sigs = ag.load_signatures('sorted')
    rows = mt.load_attempts()
    flipped_codes = {bm[b] for b in flips}

    print('== the flipped packets (first-pass GT, strict reading)')
    print('| code | task | method | condition | GT | ambiguous | spec | first judge | second judge |')
    print('|---|---|---|---|---|---|---|---|---|')
    for a in sorted((r for r in rows if r['code'] in flipped_codes), key=lambda r: r['code']):
        b = code_to_blind[a['code']]
        print(f"| {a['code']} | {a['short']} | {a['method_idx']} | {a['condition']} | {a['gt']} | {a['amb']} | "
              f"{a['spec']} | {first[b]['verdict']} {first[b]['confidence']} | {second[b]['verdict']} "
              f"{second[b]['confidence']} |")
    print(f"GT of flipped: C {sum(a['gt'] == 'C' for a in rows if a['code'] in flipped_codes)}, "
          f"W {sum(a['gt'] == 'W' for a in rows if a['code'] in flipped_codes)}")
    print()

    acc = {'first': [a for a in rows if a['judge'] == 'accept']}
    keyed = {rule: key_rows(rows, second, bm, rule) for rule in ('first', 'min')}
    for name, rs in (('first', acc['first']), ('key (first conf)', [a for a in keyed['first'] if a['judge'] == 'accept']),
                     ('key (min conf)', [a for a in keyed['min'] if a['judge'] == 'accept'])):
        c = sum(a['gt'] == 'C' for a in rs)
        w = sum(a['gt'] == 'W' for a in rs)
        print(f'judge accepts, {name}: {len(rs)} (C {c}, W {w}); precision {c / len(rs):.3f}')
    print('wrong accepts after key (first conf): ' + ', '.join(
        f"{a['code']} ({a['short']} m{a['method_idx']}, {LABEL[a['conf']]})"
        for a in keyed['first'] if a['judge'] == 'accept' and a['gt'] == 'W'))
    n_c = sum(a['gt'] == 'C' for a in rows)
    for name, rs in (('first', rows), ('key', keyed['first'])):
        acc_c = sum(a['gt'] == 'C' and a['judge'] == 'accept' for a in rs)
        print(f'recall on correct end states, {name}: {acc_c} of {n_c}')
    print()

    p1, g1, picks1 = picks_for(rows, sigs)
    print('== arms, primary 72 attempts, strict GT')
    print('| arm | first: correct / wrong / CONFIRM | key (first conf): correct / wrong / CONFIRM | '
          'key (min conf): correct / wrong / CONFIRM | key wrong commits (first conf) |')
    print('|---|---|---|---|---|')
    results = {}
    for rule in ('first', 'min'):
        p2, g2, picks2 = picks_for(keyed[rule], sigs)
        results[rule] = (p2, g2, picks2)
    for arm in ('A', 'B', 'Bs', 'C', 'D'):
        r1 = ag.report(p1, picks1[arm])
        r2 = ag.report(results['first'][0], results['first'][2][arm])
        r3 = ag.report(results['min'][0], results['min'][2][arm])
        print(f"| {arm} | {r1['correct_zero_click']} / {r1['wrong_commit']} / {r1['confirm']} | "
              f"{r2['correct_zero_click']} / {r2['wrong_commit']} / {r2['confirm']} | "
              f"{r3['correct_zero_click']} / {r3['wrong_commit']} / {r3['confirm']} | "
              f"{', '.join(r2['wrong_commit_tasks']) or '-'} |")
    print()

    for rule in ('first', 'min'):
        _, g2, picks2 = results[rule]
        print(f'== per request: commits that change under the key ({rule} confidence rule)')
        changed = 0
        for short in g1:
            row = []
            for arm in ('A', 'B', 'Bs', 'C', 'D'):
                before, after = picks1[arm][short], picks2[arm][short]
                if (before and before['code']) != (after and after['code']):
                    row.append(f"{arm}: {show(before)} -> {show(after)}")
            if row:
                changed += 1
                print(f"  {short}: " + '; '.join(row))
        print(f'  requests with any commit change: {changed}')
        print()

    print('== confidence rule check: requests whose pick differs between the first and min rules')
    for arm in ('A', 'B', 'Bs', 'C', 'D'):
        diff = [s for s in g1 if (results['first'][2][arm][s] or {}).get('code')
                != (results['min'][2][arm][s] or {}).get('code')]
        print(f'  {arm}: {len(diff)} {diff}')
    print()

    print('== CONFIRM tags, key (first conf): tag counts per arm')
    for arm in ('A', 'B', 'Bs', 'C', 'D'):
        r = ag.report(results['first'][0], results['first'][2][arm])
        print(f'  {arm}: {r["confirm_tags"]}')
    print()

    print('== commits decided by method-order tie-break (same top confidence as another eligible candidate)')
    _, g2, picks2 = results['first']
    for arm in ('A', 'B', 'C', 'D'):
        n = 0
        for short, cands in g2.items():
            p = picks2[arm][short]
            if p is None:
                continue
            if arm == 'A':
                pool = [a for a in cands if a['judge'] == 'accept']
            elif arm == 'B':
                pool = [a for a in cands if a['spec'] == 'ACCEPT' and a['judge'] == 'accept']
            else:
                members = [m for g in ag.groups_of(cands, sigs).values() for m in g]
                pool = [a for a in members if a['judge'] == 'accept' and (arm == 'C' or a['conf'] == 3)]
            if any(a['code'] != p['code'] and a['conf'] == p['conf'] for a in pool):
                n += 1
        print(f'  {arm}: {n} committed requests tie on confidence')


if __name__ == '__main__':
    main()
