"""Exp 7 external-reviewer scoring.

Joins the reviewer's verdicts (Grok, blind: request.txt + before/ + after/ only) against the private bundle
manifest, the locked and corrected answer keys, and the Exp 7 deciders: spec c909d02 (primary run), judge
(Sol, primary run), official checker, and the combined policy (spec ACCEPT and judge accept).

Protocol:
- The reviewer adjudicated from the request text and the files only.
- A case the reviewer cannot decide from the files is "not shown": excluded from rates and disagreements.
- Two variants are reported. primary: every reviewer verdict counts as given. cursor_not_shown: the five
  table-insert cases of task 66399b0d are "not shown", because each accept rests on an assumed cursor
  position that no file exposes.
- Rates use a one-sided 95% Clopper-Pearson upper bound (same convention as exp7-results.md).

Inputs are private and not in git: the bundle manifest, the adjudication master tables, the judge verdicts
and the spec decisions. The verdict file is in git at research/exp7-combined/reviewer_verdicts/.

Usage: score_review.py <verdicts.txt> [--out PREFIX]
Writes PREFIX.json (full join, both variants) and PREFIX.md (summary and per-case table).
"""
import argparse, csv, glob, json, os, re
from scipy.stats import beta

ADJ = '/tmp/exp7/adj'
MANIFEST = '/tmp/exp7/reviewer/manifest.json'
SPEC_RUN = '/home/factory-user/repos/outcome-transactions/research/exp6-executed/blind_run_exp7_norm_c909d02/decisions.json'
JUDGE_DIR = '/tmp/exp7/judge_verdicts'
SCORE_FINAL = '/tmp/exp7/score_final.json'
TABLES = {'locked': (f'{ADJ}/master.tsv', 'verdict'), 'corrected': (f'{ADJ}/master_corrected.tsv', 'corrected_verdict')}
CURSOR_TASK = '66399b0d-8fda-4618-95c4-bfc6191617e9'
CURSOR_IDS = ['0f95aea7b07f', '2a89ff362615', '4070883553d8', '6a3c3bd98895', 'be60b04814c8']
POLICIES = [('combined', lambda r: r['combined']),
            ('spec_alone', lambda r: r['spec'] == 'ACCEPT'),
            ('judge_alone', lambda r: r['judge'] == 'accept')]
LEAD = re.compile(r'^(accept|reject|undecided)\b', re.I)
UND = re.compile(r"cannot (decide|determine|verify|tell)|can't (decide|determine|verify|tell)|"
                 r"undecided|undetermined|insufficient|not enough (information|evidence)|unable to (decide|determine)", re.I)
REJ = re.compile(r"\breject|wrong\b|does not satisfy|not satisfied|fails?\b|\bfail(?:ed|ure)?\b|"
                 r"(would|do|could) not accept|not accept\b|incorrect\b", re.I)
ACC = re.compile(r"\baccept|correct\b|satisf(?:ies|ied)\b|\bpass(?:es|ed)?\b|\byes\b", re.I)
CONF = re.compile(r"\b(high|medium|low)\b", re.I)


def cp_ub(k, n):
    """One-sided 95% Clopper-Pearson upper bound."""
    return float(beta.ppf(0.95, k + 1, n - k)) if k < n else 1.0


def parse_verdicts(path, ids):
    """Target format: `<id>: accept|reject, confidence high|low, reason`. The leading word decides; free-form
    phrasings are a fallback. Lines with no id and no verdict are reported as unparsed, not scored."""
    out, unparsed = {}, []
    for ln, line in enumerate(open(path, errors='replace'), 1):
        line = line.strip()
        if not line:
            continue
        rid = next((i for i in ids if re.search(rf'\b{i}\b', line)), None)
        if rid is None:
            try:
                d = json.loads(line)
                for k, v in d.items():
                    if k in ids and isinstance(v, dict):
                        out[k] = {'verdict': str(v.get('verdict', '')).lower(), 'confidence': str(v.get('confidence', '')).lower(),
                                  'reason': str(v.get('reason', '')), 'line': ln}
                continue
            except Exception:
                unparsed.append((ln, line[:120]))
                continue
        rest = line.split(rid, 1)[1].lstrip(' :-\t')
        m = LEAD.match(rest)
        if m:
            v = m.group(1).lower()
        elif UND.search(rest):
            v = 'undecided'
        elif REJ.search(rest):
            v = 'reject'
        elif ACC.search(rest):
            v = 'accept'
        else:
            unparsed.append((ln, line[:120]))
            continue
        c = CONF.search(rest)
        out[rid] = {'verdict': v, 'confidence': c.group(1).lower() if c else '', 'reason': rest, 'line': ln}
    return out, unparsed


def rates(sub, key):
    W = [r for r in sub if r[key] == 'wrong']
    C = [r for r in sub if r[key] == 'correct']
    aw = sum(r['reviewer'] == 'accept' for r in W)
    ac = sum(r['reviewer'] == 'accept' for r in C)
    return {'wrong': len(W), 'accept_on_wrong': aw, 'wa_rate': (aw / len(W)) if W else None,
            'wa_ub95': cp_ub(aw, len(W)) if W else None,
            'correct': len(C), 'accept_on_correct': ac, 'ca_rate': (ac / len(C)) if C else None}


def brief(r):
    return {'rid': r['rid'], 'task': r['task'], 'state': r['state'], 'named': r['named'], 'cursor': r['cursor'],
            'locked': r['locked'], 'corrected': r['corrected'], 'spec': r['spec'], 'judge': f"{r['judge']}/{r['jconf']}",
            'official': r['official'], 'combined_commit': r['combined'], 'reviewer': f"{r['reviewer']}/{r['rconf']}",
            'reason': r['reason']}


def analyse(rows):
    dec = [r for r in rows if r['reviewer'] in ('accept', 'reject')]
    out = {'cases': len(rows), 'decided': len(dec),
           'not_shown': [brief(r) for r in rows if r['reviewer'] not in ('accept', 'reject')]}
    out['by_key'] = {k: {'all': rates(dec, k), 'named': rates([r for r in dec if r['named']], k),
                         'drawn': rates([r for r in dec if not r['named']], k)} for k in ('corrected', 'locked')}
    out['policies'] = {}
    for name, fn in POLICIES:
        dis = [r for r in dec if fn(r) != (r['reviewer'] == 'accept')]
        out['policies'][name] = {'n_decided': len(dec), 'disagreements': len(dis), 'cases': [brief(r) for r in dis]}
    wa = [r for r in rows if r['corrected'] == 'wrong' and r['combined']]
    out['combined_wa'] = {'n': len(wa),
                          'reviewer_reject': sum(r['reviewer'] == 'reject' for r in wa),
                          'reviewer_accept': sum(r['reviewer'] == 'accept' for r in wa),
                          'not_shown': sum(r['reviewer'] not in ('accept', 'reject') for r in wa),
                          'cases': [brief(r) for r in wa]}
    return out


def write_md(res, rows, path, verdicts_name):
    L = [f"Verdict file: `{verdicts_name}`. Cases: {len(rows)}. Decided by the reviewer: {res['primary']['decided']}.\n"]
    for name, title in [('primary', 'Primary: every reviewer verdict counts as given'),
                        ('cursor_not_shown', 'Sensitivity: the five table-insert cases (cursor position) not shown')]:
        a = res[name]
        L.append(f"### {title}\n")
        ns = ', '.join(f"{c['task'][:8]} {c['state']}" for c in a['not_shown']) or 'none'
        L.append(f"Not shown: {len(a['not_shown'])} ({ns}). Decided: {a['decided']}.\n")
        for k in ('corrected', 'locked'):
            b = a['by_key'][k]
            x = b['all']
            L.append(f"- {k} key: reviewer accepted {x['accept_on_wrong']} of {x['wrong']} WRONG states "
                     f"(rate {x['wa_rate']:.3f}, one-sided 95% UB {x['wa_ub95']:.3f}) and {x['accept_on_correct']} of "
                     f"{x['correct']} CORRECT states (rate {x['ca_rate']:.3f}). Named: "
                     f"{b['named']['accept_on_wrong']}/{b['named']['wrong']} WRONG accepted, "
                     f"{b['named']['accept_on_correct']}/{b['named']['correct']} CORRECT accepted. Drawn: "
                     f"{b['drawn']['accept_on_wrong']}/{b['drawn']['wrong']} WRONG accepted, "
                     f"{b['drawn']['accept_on_correct']}/{b['drawn']['correct']} CORRECT accepted.")
        cw = a['combined_wa']
        L.append(f"- Combined-policy wrong accepts (corrected key): {cw['n']}. Reviewer rejects {cw['reviewer_reject']}, "
                 f"accepts {cw['reviewer_accept']}, not shown {cw['not_shown']}.")
        L.append("- Disagreements on decided cases: " +
                 ', '.join(f"{n} {a['policies'][n]['disagreements']} of {a['policies'][n]['n_decided']}"
                           for n in ('combined', 'spec_alone', 'judge_alone')) + '.\n')
    L.append('### Per-case join (primary)\n')
    L.append('| id | task | state | named | cursor | locked | corrected | spec | judge | official | combined | reviewer | reason |')
    L.append('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for r in rows:
        L.append(f"| {r['rid']} | {r['task']} | {r['state']} | {'yes' if r['named'] else ''} | {'yes' if r['cursor'] else ''} | "
                 f"{r['locked'].upper()} | {r['corrected'].upper()} | {r['spec']} | {r['judge']}/{r['jconf']} | "
                 f"{r['official']} | {'COMMIT' if r['combined'] else 'no'} | {r['reviewer']}/{r['rconf']} | {r['reason']} |")
    open(path, 'w').write('\n'.join(L) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('verdicts')
    ap.add_argument('--out', default='/tmp/exp7/reviewer/review_scored')
    a = ap.parse_args()

    man = json.load(open(MANIFEST))['cases']
    ids = set(man)
    rev, unparsed = parse_verdicts(a.verdicts, ids)
    assert not sorted(ids - set(rev)), f'missing verdicts: {sorted(ids - set(rev))}'
    assert not sorted(set(rev) - ids), 'unknown ids in verdict file'
    assert len(rev) == len(ids), 'duplicate ids'
    for c in CURSOR_IDS:
        assert man[c]['task'] == CURSOR_TASK and rev[c]['verdict'] == 'accept', c

    bmap = json.load(open(f'{ADJ}/exp7_blind_map.json'))
    ts2bid = {(v['task'], v['state']): k for k, v in bmap.items()}
    judge = {}
    for f in glob.glob(f'{JUDGE_DIR}/verdicts_*.json'):
        judge.update(json.load(open(f)))
    decisions = {d['blind_id']: d for d in json.load(open(SPEC_RUN))}
    truth = {}
    for name, (path, col) in TABLES.items():
        for r in csv.DictReader(open(path), delimiter='\t'):
            truth.setdefault((r['task'], r['state']), {})[name] = r[col].lower()

    def spec_of(d):
        s = d.get('empty_all_undecided_decision', d['decision'])
        if any(p.get('status') == 'ERROR' for p in d['predicates']):
            s = 'UNDECIDED'
        return s

    # consistency checks against the report
    n_override = sum(spec_of(d) != d.get('empty_all_undecided_decision', d['decision']) for d in decisions.values())
    full_wa = [b for b, m in bmap.items() if b in judge and (m['task'], m['state']) in truth
               and truth[(m['task'], m['state'])]['corrected'] == 'wrong'
               and spec_of(decisions[b]) == 'ACCEPT' and judge[b]['verdict'] == 'accept']
    print(f'check: ERROR->UNDECIDED override changes {n_override} of {len(decisions)} spec decisions')
    print(f'check: full-set corrected combined wrong accepts = {len(full_wa)} (report: 8)')
    sf = json.load(open(SCORE_FINAL))['c909d02|locked']['combined']
    print(f"check: cp_ub(4, 310) = {cp_ub(4, 310):.6f} (report: {sf['ub95']:.6f})")

    rows = []
    for rid, rv in sorted(rev.items(), key=lambda kv: (man[kv[0]]['task'], man[kv[0]]['state'])):
        t, s = man[rid]['task'], man[rid]['state']
        bid = ts2bid[(t, s)]
        j = judge[bid]
        spec = spec_of(decisions[bid])
        rows.append({'rid': rid, 'task': t, 'state': s, 'named': man[rid]['named_wrong_accept_or_chart'],
                     'cursor': rid in CURSOR_IDS,
                     'locked': truth[(t, s)]['locked'], 'corrected': truth[(t, s)]['corrected'],
                     'spec': spec, 'official': decisions[bid].get('official'), 'judge': j['verdict'], 'jconf': j['confidence'],
                     'combined': spec == 'ACCEPT' and j['verdict'] == 'accept',
                     'reviewer': rv['verdict'], 'rconf': rv['confidence'], 'reason': rv['reason']})

    variants = {'primary': rows,
                'cursor_not_shown': [dict(r, reviewer='undecided') if r['cursor'] else r for r in rows]}
    res = {name: analyse(v) for name, v in variants.items()}
    res['unparsed_lines'] = unparsed
    res['checks'] = {'spec_override_changes': n_override, 'full_set_combined_wa_corrected': len(full_wa),
                     'bundle_combined_wa_corrected': res['primary']['combined_wa']['n']}

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump({'summary': res, 'rows': rows}, open(a.out + '.json', 'w'), indent=1)
    write_md(res, rows, a.out + '.md', os.path.basename(a.verdicts))
    print(json.dumps({'unparsed_lines': unparsed, 'checks': res['checks']}, indent=1))
    for name in ('primary', 'cursor_not_shown'):
        s = res[name]
        print(name, 'decided', s['decided'], 'not_shown', len(s['not_shown']),
              'corrected', {k: v for k, v in s['by_key']['corrected']['all'].items() if k.endswith('rate') or k.startswith('accept')},
              'locked', {k: v for k, v in s['by_key']['locked']['all'].items() if k.endswith('rate') or k.startswith('accept')},
              'combined_wa', {k: s['combined_wa'][k] for k in ('n', 'reviewer_reject', 'reviewer_accept', 'not_shown')},
              'disagree', {n: s['policies'][n]['disagreements'] for n in ('combined', 'spec_alone', 'judge_alone')})
    print('wrote', a.out + '.json', 'and', a.out + '.md')


if __name__ == '__main__':
    main()
