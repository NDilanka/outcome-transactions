"""Exp 8: second judge (Gemini 4 Argon) and the policies E, E2, E3. POST HOC, not pre-registered.

Policies, on the 72 primary attempts (18 requests), strict auto-save GT v4:
  A   Sol accept (first pass). Reference, as in metrics.py.
  B   spec ACCEPT and Sol accept (first pass). Reference, as in metrics.py.
  G   Gemini accept only (reference for the second lab alone).
  E   Sol accept (first pass) AND Gemini accept.
  E2  E with the Sol self-consistency key: Sol accept in both passes AND Gemini accept.
  E3  spec ACCEPT AND Sol accept (first pass) AND Gemini accept.
Pick rule: highest Sol first-pass confidence, then the lower method index (as arm A). For G, Gemini's confidence.
Sensitivity pick rule: lowest confidence label over the verdicts the policy uses, then method index.
CONFIRM tags use metrics.confirm_tag (unchanged). Judge splits are counted separately.

Data: origin/exp8-judge-verdicts (99f06b3 for Gemini). Sol passes as in retest.py. Output codes only.
Run with a Python that has PIL, numpy, lxml, python-pptx, python-docx, openpyxl (retest.py imports agreement.py):
  python3 gemini_policies.py > gemini_policies_output.txt
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import metrics as mt  # noqa: E402
import retest as rt  # noqa: E402

GEM = 'research/exp8-direct/judge_gemini'
CONF = mt.CONF
LABEL = {v: k for k, v in CONF.items()}
PRIMARY_CONDITIONS = ('none', 'ui')


def load_all():
    bm = json.load(open(rt.BLIND_MAP))
    code_to_blind = {v: k for k, v in bm.items()}
    first = rt.read_pass(rt.FIRST)
    second = rt.read_pass(rt.SECOND)
    gem = rt.read_pass(GEM)
    assert set(first) == set(second) == set(gem) == set(bm), 'packet sets differ'
    rows = mt.load_attempts()
    for a in rows:
        b = code_to_blind[a['code']]
        assert a['judge'] == first[b]['verdict'] and a['conf'] == CONF[first[b]['confidence']], a['code']
        a['sol2'] = second[b]['verdict']
        a['sol2_conf'] = CONF[second[b]['confidence']]
        a['gem'] = gem[b]['verdict']
        a['gem_conf'] = CONF[gem[b]['confidence']]
        a['gem_reason'] = gem[b]['reason']
    return rows


def verification(rows):
    print('== verification (Gemini at ' + rt.REF + ')')
    print(f'Gemini verdicts: {len(rows)} packets; accept {sum(a["gem"] == "accept" for a in rows)}, '
          f'reject {sum(a["gem"] == "reject" for a in rows)}')
    print('Gemini confidence:', {c: sum(LABEL[a['gem_conf']] == c for a in rows) for c in ('high', 'medium', 'low')})
    m = {}
    for a in rows:
        m[(a['judge'], a['gem'])] = m.get((a['judge'], a['gem']), 0) + 1
    print('Sol first pass x Gemini (count):', {f'{k[0]}/{k[1]}': v for k, v in sorted(m.items())})
    dis = [a for a in rows if a['judge'] != a['gem']]
    print(f'disagreements: {len(dis)} (Sol reject, Gemini accept: '
          f'{sum(a["judge"] == "reject" and a["gem"] == "accept" for a in rows)}; Sol accept, Gemini reject: '
          f'{sum(a["judge"] == "accept" and a["gem"] == "reject" for a in rows)})')
    for s, g in (('reject', 'accept'), ('accept', 'reject')):
        sub = [a for a in rows if a['judge'] == s and a['gem'] == g]
        print(f'  Sol {s}, Gemini {g}: GT C {sum(a["gt"] == "C" for a in sub)}, GT W {sum(a["gt"] == "W" for a in sub)}; '
              f'wrong: {sorted(a["code"] for a in sub if a["gt"] == "W")}')
    print('Gemini on all 84, strict GT v4: accept C', sum(a['gem'] == 'accept' and a['gt'] == 'C' for a in rows),
          'accept W', sum(a['gem'] == 'accept' and a['gt'] == 'W' for a in rows),
          '| reject C', sum(a['gem'] == 'reject' and a['gt'] == 'C' for a in rows),
          '| reject W', sum(a['gem'] == 'reject' and a['gt'] == 'W' for a in rows))
    print()


def policies():
    return {
        'A': (lambda a: a['judge'] == 'accept', lambda a: [a['conf']]),
        'B': (lambda a: a['spec'] == 'ACCEPT' and a['judge'] == 'accept', lambda a: [a['conf']]),
        'G': (lambda a: a['gem'] == 'accept', lambda a: [a['gem_conf']]),
        'E': (lambda a: a['judge'] == 'accept' and a['gem'] == 'accept', lambda a: [a['conf'], a['gem_conf']]),
        'E2': (lambda a: a['judge'] == 'accept' and a['sol2'] == 'accept' and a['gem'] == 'accept',
               lambda a: [a['conf'], a['sol2_conf'], a['gem_conf']]),
        'E3': (lambda a: a['spec'] == 'ACCEPT' and a['judge'] == 'accept' and a['gem'] == 'accept',
               lambda a: [a['conf'], a['gem_conf']]),
    }


def pick(cands, ok, used, sens=False):
    """Primary: highest of the policy's first confidence label, ties to the lower method index.
    Sensitivity: the lowest label over the verdicts the policy uses."""
    pool = [a for a in cands if ok(a)]
    if not pool:
        return None
    key = (lambda a: (min(used(a)), -a['method_idx'])) if sens else (lambda a: (used(a)[0], -a['method_idx']))
    return max(pool, key=key)


def report(rows, pol, sens=False):
    out = {'correct': 0, 'wrong': 0, 'confirm': 0, 'tags': {'AMBIGUOUS': 0, 'GAP': 0, 'PLAIN': 0},
           'wrong_tasks': [], 'confirm_split': 0}
    grouped = mt.group(rows)
    for short, cands in grouped.items():
        ok, used = pol
        p = pick(cands, ok, used, sens)
        if p is None:
            out['confirm'] += 1
            out['tags'][mt.confirm_tag(cands)] += 1
            if any(a['judge'] != a['gem'] for a in cands):
                out['confirm_split'] += 1
        elif p['gt'] == 'C':
            out['correct'] += 1
        else:
            out['wrong'] += 1
            out['wrong_tasks'].append(f"{short}:{p['code']}")
    return out


def pool_stats(rows, ok):
    pool = [a for a in rows if ok(a)]
    c = [a['code'] for a in pool if a['gt'] == 'C']
    w = [a['code'] for a in pool if a['gt'] == 'W']
    return len(pool), len(c), len(w), w


def main():
    rows_all = load_all()
    verification(rows_all)
    rows = [a for a in rows_all if a['condition'] in PRIMARY_CONDITIONS]
    n_c = sum(a['gt'] == 'C' for a in rows)
    n_w = sum(a['gt'] == 'W' for a in rows)
    print(f'== primary: {len(rows)} attempts, {len(mt.group(rows))} requests; GT C {n_c}, W {n_w}')
    print()

    pols = policies()
    print('== pool level (all 72 primary candidates; accepted by the policy before the pick)')
    print('| policy | accepted | correct | wrong | wrong states accepted |')
    print('|---|---|---|---|---|')
    for name, (ok, used) in pols.items():
        n, c, w, wl = pool_stats(rows, ok)
        print(f'| {name} | {n} | {c} | {w} | {", ".join(wl) or "-"} |')
    print(f'recall on correct states: ' + ', '.join(
        f'{name} {sum(1 for a in rows if ok(a) and a["gt"] == "C")} of {n_c}' for name, (ok, _) in pols.items()))
    print()

    print('== arms (primary 72, 18 requests): first pass pick, and sensitivity (lowest label over the used verdicts)')
    print('| policy | correct zero-click | wrong commits | CONFIRM | tags (AMBIGUOUS / GAP / PLAIN) | '
          'CONFIRM with a Sol/Gemini split | wrong commit tasks | sensitivity: correct / wrong |')
    print('|---|---|---|---|---|---|---|---|')
    for name, pol in pols.items():
        r = report(rows, pol)
        s = report(rows, pol, sens=True)
        t = r['tags']
        print(f"| {name} | {r['correct']} of 18 | {r['wrong']} | {r['confirm']} | "
              f"{t['AMBIGUOUS']} / {t['GAP']} / {t['PLAIN']} | {r['confirm_split']} | "
              f"{', '.join(r['wrong_tasks']) or '-'} | {s['correct']} / {s['wrong']} |")
    print()
    print('G0 share (correct zero-click over 18): ' + ', '.join(
        f'{name} {report(rows, pol)["correct"] / 18 * 100:.1f}%' for name, pol in pols.items()))
    print('CONFIRM share over 18: ' + ', '.join(
        f'{name} {report(rows, pol)["confirm"] / 18 * 100:.1f}%' for name, pol in pols.items()))
    print()

    print('== per request commits (code, GT)')
    print('| task | A | B | G | E | E2 | E3 | GT by method (A-D) |')
    print('|---|---|---|---|---|---|---|---|')
    grouped = mt.group(rows)
    for short, cands in grouped.items():
        gts = ''.join(a['gt'] for a in cands)
        cells = []
        for name, (ok, used) in pols.items():
            p = pick(cands, ok, used)
            cells.append('none' if p is None else f"{p['method_idx']}:{p['gt']}({p['code']})")
        print(f"| {short} | " + ' | '.join(cells) + f' | {gts} |')
    print()

    print('== wrong states (all 14 strict W, incl. ablation): Sol first, Sol second, Gemini')
    print('| code | task | method | condition | Sol first | Sol second | Gemini (conf) | spec | in primary |')
    print('|---|---|---|---|---|---|---|---|---|')
    for a in sorted((a for a in rows_all if a['gt'] == 'W'), key=lambda a: a['code']):
        print(f"| {a['code']} | {a['short']} | {a['method_idx']} | {a['condition']} | {a['judge']} ({LABEL[a['conf']]}) | "
              f"{a['sol2']} ({LABEL[a['sol2_conf']]}) | {a['gem']} ({LABEL[a['gem_conf']]}) | {a['spec']} | "
              f"{'yes' if a['condition'] in PRIMARY_CONDITIONS else 'no (ablation)'} |")
    print()

    print('== Sol key survivors (judge accept in both Sol passes, GT W): Gemini verdict and reason')
    survivors = [a for a in rows_all if a['gt'] == 'W' and a['judge'] == 'accept' and a['sol2'] == 'accept']
    for a in sorted(survivors, key=lambda a: a['code']):
        print(f"- {a['code']} ({a['short']} m{a['method_idx']}, {a['condition']}): Sol first {LABEL[a['conf']]}, "
              f"Sol second {LABEL[a['sol2_conf']]}; Gemini {a['gem']} ({LABEL[a['gem_conf']]}). Gemini reason: "
              f"{a['gem_reason']}")
    print()

    print('== the same for the v3 label of 02d030c7 (W in v3, C in v4), for reference')
    for a in rows_all:
        if a['code'] == '02d030c7':
            print(f"- 02d030c7 (ecc2413d m{a['method_idx']}): GT v4 {a['gt']}; Sol first {a['judge']} "
                  f"({LABEL[a['conf']]}), Sol second {a['sol2']}; Gemini {a['gem']} ({LABEL[a['gem_conf']]}). "
                  f"Gemini reason: {a['gem_reason']}")


if __name__ == '__main__':
    main()
