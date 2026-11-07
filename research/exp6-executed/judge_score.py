"""Scores the baseline LLM judge's verdicts on the Exp 6 blind states, against the spec results and the labels.

The verdicts come from the orchestrator's judge run (branch exp6-judge-verdicts, verdicts_*.json keyed by blind id;
each entry has verdict accept|reject, confidence high|medium|low, reason). Pass the directory that holds them.
Private inputs (gitignored): blind_run/score_rows.json, blind_run/decisions.json, blind_private/adjudication.json,
blind_map.json. The outputs contain aggregates only: no state names, no blind ids, no judge reasons.

Judge ACCEPT is the judge's commit. Spec ACCEPT is the executor's commit. Judge rates are scored on the adjusted labels
(primary), the labels as claimed, and the sensitivity key (a9f325aa formula state wrong).

Usage: judge_score.py <verdicts_dir>
"""
import collections, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blind_results as br  # noqa: E402

OUT = os.path.join(HERE, 'results')
GROUPS = ('all', 'a', 'b')
GROUP_NAME = {'all': 'all families', 'a': '(a) LibreOffice families (readers)', 'b': '(b) no reader'}


def load_verdicts(vdir):
    merged, files = {}, sorted(glob.glob(os.path.join(vdir, 'verdicts_*.json')))
    for f in files:
        for bid, v in json.load(open(f, encoding='utf-8')).items():
            if bid in merged:
                raise SystemExit(f'duplicate verdict for one blind id in {os.path.basename(f)}')
            merged[bid] = v
    return merged, len(files)


def build(vdir):
    fam = br.families()
    rows = br.prep(json.load(open(br.ROWS, encoding='utf-8')), fam)
    dec = {d['blind_id']: d for d in json.load(open(br.DECISIONS, encoding='utf-8'))}
    adj = {a['blind_id']: a for a in json.load(open(br.ADJ, encoding='utf-8'))}
    verdicts, nfiles = load_verdicts(vdir)
    ids = {r['blind_id'] for r in rows}
    if set(verdicts) != ids or len(verdicts) != len(ids):
        raise SystemExit(f'verdicts cover {len(verdicts)} ids; blind set has {len(ids)}; '
                         f'missing {len(ids - set(verdicts))}, extra {len(set(verdicts) - ids)}')
    for v in verdicts.values():
        assert v['verdict'] in ('accept', 'reject'), v['verdict']
        assert v['confidence'] in ('high', 'medium', 'low'), v['confidence']
    recs = []
    for r in rows:
        a = adj.get(r['blind_id'])
        lab_adj = a['adjusted_label'] if a and a['category'] == 'LABEL_ERROR' else r['label']
        lab_sens = 'wrong' if (a and a.get('sensitivity_wrong')) else lab_adj
        v = verdicts[r['blind_id']]
        recs.append({'bid': r['blind_id'], 'group': r['group'], 'family': r['family'], 'task8': r['task8'],
                     'raw': r['label'], 'adj': lab_adj, 'sens': lab_sens, 'spec': r['exec'],
                     'jv': v['verdict'], 'jc': v['confidence'],
                     'spec_official': r['official'], 'spec_pred': dec[r['blind_id']]['predicates']})
    return recs, nfiles, collections.Counter((v['verdict'], v['confidence']) for v in verdicts.values())


def metrics(recs, key, group='all'):
    """Judge and spec rates for one label key and one group. Accept = commit."""
    S = [r for r in recs if group == 'all' or r['group'] == group]
    W = [r for r in S if r[key] == 'wrong']
    C = [r for r in S if r[key] == 'correct']
    m = {'wrong': len(W), 'correct': len(C)}
    m['spec_wrong_accept'] = sum(r['spec'] == 'ACCEPT' for r in W)
    m['judge_wrong_accept'] = sum(r['jv'] == 'accept' for r in W)
    m['judge_wrong_accept_ub'] = round(100 * br.cp_upper(m['judge_wrong_accept'], len(W)), 2) if W else None
    m['judge_wrong_accept_high'] = sum(r['jv'] == 'accept' and r['jc'] == 'high' for r in W)
    m['judge_wrong_states_high'] = sum(r['jc'] == 'high' for r in W)
    m['judge_wrong_accept_medium_or_low'] = sum(r['jv'] == 'accept' and r['jc'] != 'high' for r in W)
    m['spec_accept_on_correct'] = sum(r['spec'] == 'ACCEPT' for r in C)
    m['spec_reject_on_correct'] = sum(r['spec'] == 'REJECT' for r in C)
    m['judge_accept_on_correct'] = sum(r['jv'] == 'accept' for r in C)
    m['judge_wrong_reject'] = sum(r['jv'] == 'reject' for r in C)
    m['judge_wrong_reject_high'] = sum(r['jv'] == 'reject' and r['jc'] == 'high' for r in C)
    m['judge_states_high'] = sum(r['jc'] == 'high' for r in S)
    m['judge_correct_states_high'] = sum(r['jc'] == 'high' for r in C)
    # Combined policy: commit only if the spec accepts and the judge accepts. The high variant also needs judge high confidence.
    comb = [r for r in S if r['spec'] == 'ACCEPT' and r['jv'] == 'accept']
    combh = [r for r in comb if r['jc'] == 'high']
    m['combined_wrong_accept'] = sum(r[key] == 'wrong' for r in comb)
    m['combined_wrong_accept_ub'] = round(100 * br.cp_upper(m['combined_wrong_accept'], len(W)), 2) if W else None
    m['combined_correct_commit'] = sum(r[key] == 'correct' for r in comb)
    m['combined_wrong_accept_high'] = sum(r[key] == 'wrong' for r in combh)
    m['combined_wrong_accept_high_ub'] = round(100 * br.cp_upper(m['combined_wrong_accept_high'], len(W)), 2) if W else None
    m['combined_correct_commit_high'] = sum(r[key] == 'correct' for r in combh)
    m['gate_3x_pass'] = m['judge_wrong_accept'] >= 3 * m['spec_wrong_accept']
    return m


def spec_gap_verdicts(recs, key):
    """Judge verdict on the wrong states the spec accepts (the real spec gaps)."""
    return [{'judge': r['jv'], 'confidence': r['jc']} for r in recs if r[key] == 'wrong' and r['spec'] == 'ACCEPT']


def family_rows(recs, key):
    out = []
    for f in sorted({r['family'] for r in recs}):
        S = [r for r in recs if r['family'] == f]
        W = [r for r in S if r[key] == 'wrong']
        C = [r for r in S if r[key] == 'correct']
        out.append((f, len(S), len(W), sum(r['jv'] == 'accept' for r in W),
                    len(C), sum(r['jv'] == 'accept' for r in C), sum(r['jv'] == 'reject' for r in C),
                    sum(r['jv'] == 'accept' and r['spec'] == 'ACCEPT' for r in W)))
    return out


def pct(a, b):
    return f'{a}/{b} ({round(100 * a / b, 1)}%)' if b else 'n/a'


def main():
    vdir = os.path.abspath(sys.argv[1])
    recs, nfiles, verdict_counts = build(vdir)
    res = {'verdict_files': nfiles, 'verdict_counts': {f'{v}|{c}': n for (v, c), n in verdict_counts.items()},
           'verdict_total': sum(verdict_counts.values()),
           'views': {}}
    for key in ('adj', 'raw', 'sens'):
        res['views'][key] = {g: metrics(recs, key, g) for g in GROUPS}
    res['spec_gap_verdicts'] = spec_gap_verdicts(recs, 'adj')
    res['family_adj'] = family_rows(recs, 'adj')
    res['sum_judge_accept_all'] = sum(r['jv'] == 'accept' for r in recs)

    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, 'judge_results.json'), 'w'), indent=1, ensure_ascii=False)
    write_md(res)
    A = res['views']['adj']
    print(json.dumps({g: {k: A[g][k] for k in ('wrong', 'spec_wrong_accept', 'judge_wrong_accept', 'judge_wrong_reject',
                                              'combined_wrong_accept', 'gate_3x_pass')} for g in GROUPS}, indent=1))


def write_md(res):
    V = res['views']
    A, R, S = V['adj'], V['raw'], V['sens']
    L = ['# Exp 6: baseline LLM judge versus specs\n',
         'Generated by `research/exp6-executed/judge_score.py` from the private run files and the judge verdicts. Aggregates only.\n',
         '## Scope\n',
         f"- Judge verdicts: {res['verdict_total']} states, {res['verdict_files']} files. The judge chose accept or reject, with high, medium or low confidence. It did not see labels or the spec outputs.",
         '- Accept means commit. Spec ACCEPT is the executor\'s commit. Both are scored on the adjusted labels (primary), labels as claimed, and the sensitivity key.',
         '- 3x gate: the specs pass if the judge\'s wrong accepts are at least three times the specs\' wrong accepts.',
         '- The judge\'s verdict file is on branch `exp6-judge-verdicts`, not in this branch.\n']

    L.append('## Headline (adjusted labels)\n')
    L.append('| measure | all families | (a) LibreOffice families | (b) no reader |')
    L.append('|---|---|---|---|')
    def row(name, fn):
        L.append(f"| {name} | " + ' | '.join(fn(A[g]) for g in GROUPS if g in ('all', 'a', 'b')) + ' |')
    row('wrong states', lambda m: str(m['wrong']))
    row('spec wrong accepts', lambda m: pct(m['spec_wrong_accept'], m['wrong']))
    row('judge wrong accepts', lambda m: f"{pct(m['judge_wrong_accept'], m['wrong'])}, 95% UB {m['judge_wrong_accept_ub']}%")
    row('judge wrong accepts, high confidence only', lambda m: f"{m['judge_wrong_accept_high']} of {m['judge_wrong_states_high']} high-confidence wrong verdicts")
    row('3x gate (judge >= 3 x spec)', lambda m: ('PASS' if m['gate_3x_pass'] else 'FAIL') + f" ({m['judge_wrong_accept']} vs {3 * m['spec_wrong_accept']})")
    row('correct states', lambda m: str(m['correct']))
    row('judge wrong-reject on correct', lambda m: pct(m['judge_wrong_reject'], m['correct']))
    row('judge wrong-reject, high confidence', lambda m: f"{m['judge_wrong_reject_high']} of {m['judge_correct_states_high']} high-confidence correct verdicts")
    row('judge accept on correct', lambda m: pct(m['judge_accept_on_correct'], m['correct']))
    row('spec ACCEPT on correct', lambda m: pct(m['spec_accept_on_correct'], m['correct']))
    row('combined: wrong accepts (spec and judge accept)', lambda m: f"{pct(m['combined_wrong_accept'], m['wrong'])}, 95% UB {m['combined_wrong_accept_ub']}%")
    row('combined: correct commit (spec and judge accept)', lambda m: pct(m['combined_correct_commit'], m['correct']))
    row('combined, judge high only: wrong accepts', lambda m: f"{pct(m['combined_wrong_accept_high'], m['wrong'])}, 95% UB {m['combined_wrong_accept_high_ub']}%")
    row('combined, judge high only: correct commit', lambda m: pct(m['combined_correct_commit_high'], m['correct']))
    L.append('')

    L.append('Judge verdicts by confidence (all states):\n')
    L.append('| verdict | confidence | states |')
    L.append('|---|---|---|')
    for k, n in sorted(res['verdict_counts'].items()):
        v, c = k.split('|')
        L.append(f'| {v} | {c} | {n} |')
    L.append('')

    L.append('## Judge versus spec on the two real spec gaps\n')
    gaps = res['spec_gap_verdicts']
    L.append(f"The spec accepts {len(gaps)} wrong states (adjusted labels). Judge verdicts on them: "
             + ', '.join(f"{g['judge']} ({g['confidence']})" for g in gaps) + '.\n')

    L.append('## Labels as claimed and sensitivity key\n')
    L.append('| key | group | wrong | spec wrong accepts | judge wrong accepts | judge wrong-reject on correct | gate 3x |')
    L.append('|---|---|---|---|---|---|---|')
    for name, X in (('as claimed', R), ('sensitivity (a9f325aa wrong)', S)):
        for g in ('all', 'a'):
            m = X[g]
            L.append(f"| {name} | {g} | {m['wrong']} | {m['spec_wrong_accept']} | {m['judge_wrong_accept']} "
                     f"| {pct(m['judge_wrong_reject'], m['correct'])} | {'PASS' if m['gate_3x_pass'] else 'FAIL'} |")
    L.append('')

    L.append('## Judge by family (adjusted labels)\n')
    L.append('| family | states | wrong | judge wrong accepts | correct | judge accept on correct | judge reject on correct | judge wrong accept that spec also accepts |')
    L.append('|---|---|---|---|---|---|---|---|')
    for row_ in res['family_adj']:
        L.append('| ' + ' | '.join(str(x) for x in row_) + ' |')
    L.append('')

    L.append('## Combined policy\n')
    L.append('Commit only if the spec accepts and the judge accepts. Because the spec never accepts in group (b), this policy never commits there, so group (b) correct states can never be committed by it.\n')
    L.append(f"- Group (a) correct commit rate: spec alone {pct(A['a']['spec_accept_on_correct'], A['a']['correct'])}; combined {pct(A['a']['combined_correct_commit'], A['a']['correct'])}; combined with judge high confidence only {pct(A['a']['combined_correct_commit_high'], A['a']['correct'])}.")
    L.append(f"- Wrong accepts under the combined policy: all {pct(A['all']['combined_wrong_accept'], A['all']['wrong'])}; group (a) {pct(A['a']['combined_wrong_accept'], A['a']['wrong'])}.")
    L.append('')
    L.append('## Caveats\n')
    L.append('- Wrong-accept counts are small. Judge rates here use the 173 adjusted wrong states; the 200-state gate is still not met.')
    L.append('- Group (b) judge results are not comparable to spec results: the spec cannot accept there, but the judge can.')
    L.append('- The adjusted labels, the adjudication, and the causes are private. This file gives aggregates only.\n')
    with open(os.path.join(OUT, 'judge_results.md'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L))


if __name__ == '__main__':
    main()
