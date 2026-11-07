"""Exp 8 post-hoc agreement analysis. HYPOTHESIS, not a pre-registered result.

Each attempt is reduced to its content-level diff against the start state: gt_view.view_lines on the start copy and on
the end state, changed lines only. The changed lines are whitespace-collapsed and sorted, so the order of edits does
not matter. Two attempts agree when their signatures are equal and non-empty (a no-change attempt never agrees).

Policies on the primary 72 attempts (18 requests), with the strict auto-save reading as primary (metrics.py):
  C  commit the judge-accepted member of an agreement group (>= 2 attempts with the same signature; their method hints
     differ by construction). Highest judge confidence first, then method order.
  D  C, but the committed member must have a high-confidence judge accept.

Arms A, B and Bs, and the CONFIRM tag, come from metrics.py unchanged, so the numbers are comparable.
Run with the exp8 venv (the inspector needs PIL):
  /home/factory-user/venvs/exp8/bin/python agreement.py
"""
import difflib
import hashlib
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gt_view as gv  # noqa: E402
import metrics as mt  # noqa: E402

PRIVATE_OUT = '/home/factory-user/exp8/agreement'


def changed_lines(before, after):
    """Changed lines only (n=0), with whitespace collapsed, sorted. Diff headers and hunk markers are dropped."""
    out = []
    for line in list(difflib.unified_diff(before, after, lineterm='', n=0))[2:]:
        if not line or line[0] not in '+-' or line.startswith('@@'):
            continue
        out.append(line[0] + ' ' + ' '.join(line[1:].split()))
    return sorted(out)


def anchored_hunks(before, after):
    """Position-aware variant: each hunk keeps one unchanged line of context on each side (n=1), whitespace collapsed.
    Hunks are sorted, so their order does not matter, but a hunk that sits next to a different paragraph differs."""
    hunks, cur = [], None
    for line in list(difflib.unified_diff(before, after, lineterm='', n=1))[2:]:
        if line.startswith('@@'):
            if cur is not None:
                hunks.append(tuple(cur))
            cur = []
            continue
        if cur is None or not line:
            continue
        cur.append(line[0] + ' ' + ' '.join(line[1:].split()))
    if cur:
        hunks.append(tuple(cur))
    return sorted(hunks)


def signature(changed):
    return hashlib.sha256('\n'.join(changed).encode()).hexdigest()[:12] if changed else None


def load_signatures(mode='sorted'):
    """mode 'sorted': changed lines as a sorted set (primary; blind to position).
    mode 'anchored': hunks with one line of context (sensitivity; sees position)."""
    mp = {e['code']: e for e in json.load(open(mt.MAP))}
    before_cache, sigs = {}, {}
    for code, e in mp.items():
        res = json.load(open(os.path.join(mt.EXEC, code, 'result.json')))
        if e['input_path'] not in before_cache:
            before_cache[e['input_path']] = gv.view_lines(e, e['input_path'])
        b, a = before_cache[e['input_path']], gv.view_lines(e, res['end_state'])
        if mode == 'sorted':
            ch = changed_lines(b, a)
            sigs[code] = {'sig': signature(ch), 'changed': ch}
        else:
            hunks = anchored_hunks(b, a)
            sig = hashlib.sha256(repr(hunks).encode()).hexdigest()[:12] if hunks else None
            sigs[code] = {'sig': sig, 'changed': [l for h in hunks for l in h]}
    return sigs


def groups_of(cands, sigs):
    groups = {}
    for a in cands:
        s = sigs[a['code']]['sig']
        if s:
            groups.setdefault(s, []).append(a)
    return {s: m for s, m in groups.items() if len(m) >= 2}


def policy_pick(cands, sigs, policy):
    qual = []
    for members in groups_of(cands, sigs).values():
        assert len({a['method_idx'] for a in members}) == len(members)
        for a in members:
            if a['judge'] != 'accept':
                continue
            if policy == 'D' and a['conf'] < 3:
                continue
            qual.append(a)
    if not qual:
        return None
    return max(qual, key=lambda a: (a['conf'], -a['method_idx']))


def pairwise_report(cands, sigs):
    """Pairwise Jaccard of changed-line sets within one request (min, max), and changed-line count per method."""
    sets = {a['method_idx']: set(sigs[a['code']]['changed']) for a in cands}
    js = []
    for i, a in enumerate(cands):
        for b in cands[i + 1:]:
            x, y = sets[a['method_idx']], sets[b['method_idx']]
            js.append(len(x & y) / len(x | y) if x | y else 0.0)
    counts = ', '.join(f'{m}:{len(s)}' for m, s in sets.items())
    return (round(min(js), 2), round(max(js), 2)) if js else None, counts


def report(primary, picks):
    out = {'requests': 0, 'correct_zero_click': 0, 'wrong_commit': 0, 'confirm': 0,
           'confirm_tags': Counter(), 'wrong_commit_tasks': []}
    for short, cands in mt.group(primary).items():
        out['requests'] += 1
        p = picks[short]
        if p is None:
            out['confirm'] += 1
            out['confirm_tags'][mt.confirm_tag(cands)] += 1
        elif p['gt'] == 'C':
            out['correct_zero_click'] += 1
        else:
            out['wrong_commit'] += 1
            out['wrong_commit_tasks'].append(f"{short}:{p['code']}")
    out['confirm_tags'] = dict(out['confirm_tags'])
    return out


def main(mode='sorted'):
    rows = mt.load_attempts()
    primary = [a for a in rows if a['condition'] in ('none', 'ui')]
    sigs = load_signatures(mode)
    os.makedirs(PRIVATE_OUT, exist_ok=True)
    json.dump({c: {'sig': v['sig'], 'changed': v['changed']} for c, v in sigs.items()},
              open(os.path.join(PRIVATE_OUT, f'signatures_{mode}.json'), 'w'), indent=1, ensure_ascii=False)

    print(f'== signature mode: {mode}')
    print('attempts with no content change:', sum(v['sig'] is None for v in sigs.values()))
    grouped = mt.group(primary)
    n_groups = sum(len(groups_of(c, sigs)) for c in grouped.values())
    agree_req = sum(bool(groups_of(c, sigs)) for c in grouped.values())
    print('agreement groups (>=2 attempts, same signature):', n_groups, 'in', agree_req, 'of 18 requests')
    kinds = Counter()
    for short, cands in grouped.items():
        gtmap = {a['code']: a['gt'] for a in cands}
        for s, members in groups_of(cands, sigs).items():
            labels = ''.join(gtmap[a['code']] for a in members)
            kinds['all C' if set(labels) == {'C'} else 'all W' if set(labels) == {'W'} else 'mixed'] += 1
    print('agreement groups by GT of members:', dict(kinds))

    pick_c = {s: policy_pick(c, sigs, 'C') for s, c in grouped.items()}
    pick_d = {s: policy_pick(c, sigs, 'D') for s, c in grouped.items()}
    arms = {
        'A': {s: mt.arm_pick(c, 'A') for s, c in grouped.items()},
        'B': {s: mt.arm_pick(c, 'B') for s, c in grouped.items()},
        'C': pick_c,
        'D': pick_d,
    }
    for name, picks in arms.items():
        r = report(primary, picks)
        print('POLICY', name, json.dumps(r))
    print()
    print('| task | signature groups (method: GT) | A | B | C | D | CONFIRM tag |')
    print('|---|---|---|---|---|---|---|')
    for short, cands in grouped.items():
        gtmap = {a['code']: a['gt'] for a in cands}
        parts = []
        for s, m in groups_of(cands, sigs).items():
            members = ', '.join(f"{a['method_idx']}:{gtmap[a['code']]}" for a in m)
            parts.append(f"{s[:6]} {{{members}}}")
        desc = '; '.join(parts) or 'none'

        def show(p):
            return 'none' if p is None else f"{p['method_idx']}:{p['gt']}"
        tag = mt.confirm_tag(cands) if pick_d[short] is None else ''
        print(f"| {short} | {desc} | {show(arms['A'][short])} | {show(arms['B'][short])} | "
              f"{show(pick_c[short])} | {show(pick_d[short])} | {tag} |")
    print()
    print('pairwise Jaccard of changed-line sets (min, max) and changed lines per method, per request:')
    for short, cands in grouped.items():
        jac, counts = pairwise_report(cands, sigs)
        print(f'  {short}: jaccard {jac}; changed lines {counts}')


ECC_RENDER = {'476b080a': 'W', 'eeb4b683': 'W', '7b72ebd1': 'W', '02d030c7': 'C'}  # LibreOffice render: only m3 adds a page


def with_gt(rows, overrides):
    out = []
    for a in rows:
        b = dict(a)
        if a['code'] in overrides:
            b['gt'] = overrides[a['code']]
        out.append(b)
    return out


def scenario(rows, sigs, label, overrides):
    rs = with_gt(rows, overrides)
    primary = [a for a in rs if a['condition'] in ('none', 'ui')]
    grouped = mt.group(primary)
    picks = {
        'A': {s: mt.arm_pick(c, 'A') for s, c in grouped.items()},
        'B': {s: mt.arm_pick(c, 'B') for s, c in grouped.items()},
        'Bs': {s: mt.arm_pick(c, 'Bs') for s, c in grouped.items()},
        'C': {s: policy_pick(c, sigs, 'C') for s, c in grouped.items()},
        'D': {s: policy_pick(c, sigs, 'D') for s, c in grouped.items()},
    }
    wrong_all = [a for a in rs if a['gt'] == 'W']
    two_key_pass = [a for a in wrong_all if a['spec'] == 'ACCEPT' and a['judge'] == 'accept']
    print(f'== scenario: {label}')
    print(f'   wrong end states (all 84): {len(wrong_all)}; two-key passes: {len(two_key_pass)}; '
          f'spec ACCEPT on wrong: {sum(a["spec"] == "ACCEPT" for a in wrong_all)}; '
          f'judge accept on wrong: {sum(a["judge"] == "accept" for a in wrong_all)}')
    for name in ('A', 'B', 'Bs', 'C', 'D'):
        r = report(primary, picks[name])
        print(f'   {name:3s} correct {r["correct_zero_click"]:2d}/18  wrong {r["wrong_commit"]}  '
              f'CONFIRM {r["confirm"]:2d} {r["confirm_tags"]}  wrong tasks {r["wrong_commit_tasks"]}')


def per_request(rows, sigs, overrides):
    """Per-request table for one scenario: signature groups, and the commit each policy makes."""
    rs = with_gt(rows, overrides)
    primary = [a for a in rs if a['condition'] in ('none', 'ui')]
    lines = ['| task | signature groups (method: GT) | A | B | C | D | CONFIRM tag (D no-commit) |',
             '|---|---|---|---|---|---|---|']
    for short, cands in mt.group(primary).items():
        gtmap = {a['code']: a['gt'] for a in cands}
        parts = []
        for s, m in groups_of(cands, sigs).items():
            members = ', '.join(f"{a['method_idx']}:{gtmap[a['code']]}" for a in m)
            parts.append(f"{s[:6]} {{{members}}}")
        pa, pb = mt.arm_pick(cands, 'A'), mt.arm_pick(cands, 'B')
        pc, pd = policy_pick(cands, sigs, 'C'), policy_pick(cands, sigs, 'D')

        def show(p):
            return 'none' if p is None else f"{p['method_idx']}:{p['gt']}"
        tag = mt.confirm_tag(cands) if pd is None else ''
        lines.append(f"| {short} | {'; '.join(parts) or 'none'} | {show(pa)} | {show(pb)} | {show(pc)} | {show(pd)} | {tag} |")
    return '\n'.join(lines)


def scenarios():
    for mode in ('sorted', 'anchored'):
        sigs = load_signatures(mode)
        strict = mt.load_attempts()        # PRIMARY: strict auto-save reading (metrics.AUTOSAVE_STRICT_W)
        lenient = mt.load_attempts({})     # GT v3 as adjudicated
        print(f'######## signature mode: {mode}')
        scenario(lenient, sigs, 'sensitivity: GT v3 as adjudicated (auto-save family all C)', {})
        scenario(strict, sigs, 'PRIMARY: auto-save strict reading', {})
        scenario(strict, sigs, 'auto-save strict + ecc2413d render check (sensitivity, not GT)', ECC_RENDER)
        if mode == 'sorted':
            print('PER-REQUEST, PRIMARY SCENARIO (sorted signatures, strict auto-save):')
            print(per_request(strict, sigs, {}))
        print()


if __name__ == '__main__':
    for mode in ('sorted', 'anchored'):
        main(mode)
        print()
    scenarios()
