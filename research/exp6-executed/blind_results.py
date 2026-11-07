"""Aggregates the Exp 6 blind run into results/blind_results.md and results/blind_results.json.

Inputs are private and gitignored:
- blind_run/score_rows.json and blind_run/decisions.json: the primary (frozen) run, joined to labels by blind_score.py
- blind_run_raw/score_rows.json: the unnormalized run
- blind_run_fixed_rows/: the separate rerun with the table(n).rows fix (EXP6_FIXES=table_rows)
- blind_private/adjudication.json (blind_private/adjudicate.py) and blind_private/causes.json (blind_private/causes.py)
- blind_src/: the blind state README (family of each task)
The outputs contain aggregates only: no state names, no per-state labels, no blind ids.

Usage: blind_results.py
"""
import collections, json, os, re, sys

from scipy.stats import beta

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = os.path.join(HERE, 'blind_run', 'score_rows.json')
DECISIONS = os.path.join(HERE, 'blind_run', 'decisions.json')
RAW_ROWS = os.path.join(HERE, 'blind_run_raw', 'score_rows.json')
RERUN_ROWS = os.path.join(HERE, 'blind_run_fixed_rows', 'score_rows.json')
RERUN_DECISIONS = os.path.join(HERE, 'blind_run_fixed_rows', 'decisions.json')
ADJ = os.path.join(HERE, 'blind_private', 'adjudication.json')
CAUSES = os.path.join(HERE, 'blind_private', 'causes.json')
README = os.path.join(HERE, 'blind_src', 'research', 'exp6-blind-states', 'README.md')
OUT = os.path.join(HERE, 'results')
# Specs that pass the mutation gate (exp6-gate.md). Intersected with the blind set below.
GATE_PASS = {'6054afcb', '21760ecb', 'd53ff5ee', 'ecc2413d', '4d117223'}
# Group (a): the executor has readers for these families. Group (b): it has none, so it cannot accept there.
FILE_FAMS = {'libreoffice_calc', 'libreoffice_impress', 'libreoffice_writer'}
CAUSE_ORDER = ['executor defect', 'prose/grammar', 'contradiction', 'spec over-pin', 'renderer']
CAUSE_TEXT = {
    'executor defect': 'the executor has a bug or lacks a reader attribute the spec uses',
    'prose/grammar': 'a clause is written in prose, or in a form the spec grammar does not parse',
    'contradiction': 'two predicates of the same spec disagree about one state',
    'spec over-pin': 'the spec demands more than the request asks for (the request is ambiguous)',
    'renderer': 'the page count depends on the renderer (LibreOffice here; Word was not available)',
}


def cp_upper(x, n, conf=0.95):
    """Two-sided Clopper-Pearson upper bound for x successes in n trials."""
    if n == 0:
        return float('nan')
    if x >= n:
        return 1.0
    return float(beta.ppf(1 - (1 - conf) / 2, x + 1, n - x))


def families():
    fam = {}
    for line in open(README, encoding='utf-8'):
        m = re.match(r'- `([a-z_]+)`: (.*)', line)
        if m:
            for tid in re.findall(r'`([0-9a-f\-]{36})`', m.group(2)):
                fam[tid[:8]] = m.group(1)
    return fam


def prep(rows, fam):
    for r in rows:
        r['task8'] = r['task'][:8]
        r['family'] = fam[r['task8']]
        r['group'] = 'a' if r['family'] in FILE_FAMS else 'b'
    return rows


def view(rows, adj, mode):
    """mode: 'raw' (labels as claimed), 'adjusted' (label errors corrected), 'sens' (also a9f325aa formula state wrong)."""
    out = []
    for r in rows:
        lab = r['label']
        a = adj.get(r['blind_id'])
        if mode in ('adjusted', 'sens') and a and a['category'] == 'LABEL_ERROR':
            lab = a['adjusted_label']
        if mode == 'sens' and a and a['sensitivity_wrong']:
            lab = 'wrong'
        out.append({**r, 'lab': lab})
    return out


def summarize(vs):
    W = [v for v in vs if v['lab'] == 'wrong']
    C = [v for v in vs if v['lab'] == 'correct']
    wa = sum(v['exec'] == 'ACCEPT' for v in W)
    ce = collections.Counter(v['exec'] for v in C)
    we = collections.Counter(v['exec'] for v in W)
    return {
        'states': len(vs), 'wrong': len(W), 'correct': len(C),
        'wrong_exec': dict(we), 'correct_exec': dict(ce),
        'wrong_accept': wa,
        'wrong_accept_pct': round(100 * wa / len(W), 2) if W else None,
        'wrong_accept_ub95_pct': round(100 * cp_upper(wa, len(W)), 2) if W else None,
        'correct_accept_pct': round(100 * ce.get('ACCEPT', 0) / len(C), 1) if C else None,
        'correct_reject_pct': round(100 * ce.get('REJECT', 0) / len(C), 1) if C else None,
        'correct_undecided_pct': round(100 * ce.get('UNDECIDED', 0) / len(C), 1) if C else None,
        'correct_not_accepted_pct': round(100 * (len(C) - ce.get('ACCEPT', 0)) / len(C), 1) if C else None,
        'wrong_official': dict(collections.Counter(v['official'] for v in W)),
        'correct_official': dict(collections.Counter(v['official'] for v in C)),
    }


def by_group(vs):
    return {'a': summarize([v for v in vs if v['group'] == 'a']),
            'b': summarize([v for v in vs if v['group'] == 'b']),
            'all': summarize(vs)}


def coverage(vs, dec):
    """Group (b): can the executor accept a state at all? It cannot if a predicate is unsupported or unknown."""
    out = collections.Counter()
    for v in vs:
        if v['group'] != 'b':
            continue
        preds = dec[v['blind_id']]['predicates']
        unsup = any(p['status'] in ('UNSUPPORTED', 'ERROR') for p in preds)
        unknown = any('unknown name' in p.get('reason', '') for p in preds)
        key = 'correct' if v['lab'] == 'correct' else 'wrong'
        out[f'{key}_states'] += 1
        out[f'{key}_with_unsupported_or_error'] += unsup
        out[f'{key}_with_unknown_app_root'] += unknown
    return dict(out)


def main():
    fam = families()
    rows = prep(json.load(open(ROWS, encoding='utf-8')), fam)
    raw_rows = prep(json.load(open(RAW_ROWS, encoding='utf-8')), fam)
    rerun = prep(json.load(open(RERUN_ROWS, encoding='utf-8')), fam)
    adj_list = json.load(open(ADJ, encoding='utf-8'))
    adj = {a['blind_id']: a for a in adj_list}
    causes = json.load(open(CAUSES, encoding='utf-8'))
    dec = {d['blind_id']: d for d in json.load(open(DECISIONS, encoding='utf-8'))}
    rdec = {d['blind_id']: d for d in json.load(open(RERUN_DECISIONS, encoding='utf-8'))}

    adjv = view(rows, adj, 'adjusted')
    rerv = view(rerun, adj, 'adjusted')
    prim_exec = {r['blind_id']: r['exec'] for r in rows}
    trans = collections.Counter()
    for r in rerv:
        if prim_exec[r['blind_id']] != r['exec']:
            trans[(r['group'], r['lab'], prim_exec[r['blind_id']], r['exec'])] += 1
    pred_changed = sum(dec[b]['predicates'] != rdec[b]['predicates'] for b in dec)
    decision_changed = sum(dec[b]['decision'] != rdec[b]['decision'] for b in dec)
    official_changed = sum(dec[b]['official'] != rdec[b]['official'] for b in dec)
    tasks_changed = sorted({r['task8'] for r in rerv if prim_exec[r['blind_id']] != r['exec']})

    gp = [v for v in adjv if v['task8'] in GATE_PASS]
    gf = [v for v in adjv if v['task8'] not in GATE_PASS]
    A, B, S = summarize(view(rows, adj, 'raw')), summarize(adjv), summarize(view(rows, adj, 'sens'))
    res = {
        'n_states': len(rows), 'n_tasks': len({r['task8'] for r in rows}),
        'raw_run_no_normalization': summarize(view(raw_rows, {}, 'raw')),
        'as_labelled': A, 'adjusted': B, 'sensitivity': S,
        'groups': by_group(adjv),
        'coverage_group_b': coverage(adjv, dec),
        'rerun_groups': by_group(rerv),
        'rerun_transitions': [{'group': g, 'label': lab, 'primary': p, 'rerun': q, 'states': n}
                              for (g, lab, p, q), n in sorted(trans.items())],
        'rerun_checks': {'decision_changed': decision_changed, 'predicate_records_changed': pred_changed,
                         'official_changed': official_changed, 'tasks_changed': tasks_changed},
        'categories': dict(collections.Counter(a['category'] for a in adj_list)),
        'label_changes': dict(collections.Counter(
            f"{a['label']} -> {a['adjusted_label']}" for a in adj_list if a['category'] == 'LABEL_ERROR')),
        'causes': {c: {'states': sum(x['cause'] == c for x in causes),
                       'reject': sum(x['cause'] == c and x['exec'] == 'REJECT' for x in causes),
                       'undecided': sum(x['cause'] == c and x['exec'] == 'UNDECIDED' for x in causes),
                       'tasks': sorted({x['task8'] for x in causes if x['cause'] == c})} for c in CAUSE_ORDER},
        'ablation': {'gate_pass': summarize(gp), 'gate_fail': summarize(gf),
                     'gate_pass_tasks_in_blind_set': sorted({v['task8'] for v in gp})},
        'families': [],
        'tasks': [],
    }
    for f in sorted({r['family'] for r in rows}):
        sub = [v for v in adjv if v['family'] == f]
        s = summarize(sub)
        res['families'].append((f, len({v['task8'] for v in sub}), s['states'], s['wrong'], s['correct'],
                                s['wrong_accept'], s['correct_exec'].get('REJECT', 0),
                                s['correct_exec'].get('UNDECIDED', 0), s['correct_exec'].get('ACCEPT', 0),
                                sum(v['official'] == 'NOT_RUNNABLE' for v in sub)))
    for t in sorted({v['task8'] for v in adjv}):
        sub = [v for v in adjv if v['task8'] == t]
        s = summarize(sub)
        res['tasks'].append((t, sub[0]['family'], s['wrong'], s['correct'], s['wrong_accept'],
                             s['correct_exec'].get('REJECT', 0), s['correct_exec'].get('UNDECIDED', 0),
                             s['correct_exec'].get('ACCEPT', 0), sum(v['official'] == 'NOT_RUNNABLE' for v in sub)))

    # The no-reader claim in the text is only true if every group (b) state has an unevaluable predicate.
    cb = res['coverage_group_b']
    assert cb.get('wrong_with_unsupported_or_error', 0) + cb.get('correct_with_unsupported_or_error', 0) == \
        cb.get('wrong_states', 0) + cb.get('correct_states', 0), 'a group (b) state has only evaluable predicates'
    assert res['groups']['b']['correct_exec'].get('ACCEPT', 0) == 0 and res['groups']['b']['wrong_accept'] == 0
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, 'blind_results.json'), 'w'), indent=1, ensure_ascii=False, default=str)
    write_md(res)
    print(json.dumps({k: res[k] for k in ('groups', 'rerun_checks')}, indent=1, default=str)[:3000])


def pct(a, b):
    return f'{a}/{b} ({round(100 * a / b, 1)}%)' if b else 'n/a'


def split_line(name, s, accept_possible=True):
    ce = s['correct_exec']
    C, W = s['correct'], s['wrong']
    if accept_possible:
        wa, ub = f"{s['wrong_accept']}/{W}", f"{s['wrong_accept_ub95_pct']}%"
    else:
        wa, ub = f"0/{W} (ACCEPT ruled out)", 'n/a'
    return (f"| {name} | {s['states']} | {W} | {wa} | {ub} | {C} | {pct(ce.get('ACCEPT', 0), C)} | "
            f"{pct(ce.get('REJECT', 0), C)} | {pct(ce.get('UNDECIDED', 0), C)} |")


SPLIT_HEAD = ['| group | states | wrong | wrong accepts | 95% upper bound | correct | correct ACCEPT | correct REJECT | correct UNDECIDED |',
              '|---|---|---|---|---|---|---|---|---|']
GROUP_NAME = {'a': '(a) LibreOffice families with readers', 'b': '(b) families with no reader', 'all': 'all families'}


def write_md(res):
    A, B, S = res['as_labelled'], res['adjusted'], res['sensitivity']
    G, RG = res['groups'], res['rerun_groups']
    cov = res['coverage_group_b']
    L = []
    L.append('# Exp 6 blind run: results\n')
    L.append('Generated by `research/exp6-executed/blind_results.py` from the private run files. Aggregates only.\n')
    L.append('## Scope\n')
    L.append(f"- {res['n_states']} blind end states from {res['n_tasks']} tasks (generator labels: "
             f"{A['wrong']} wrong, {A['correct']} correct). Labels below are the adjusted labels unless noted.")
    L.append('- Specs run as written (`specexec.py`). OSWorld checker run where its functions read a file.')
    L.append('- End states are the normalized copies: 15 workbooks were re-saved and recalculated by LibreOffice '
             'because the generator dropped cached formula values (`normalize_states.py`, checks in '
             '`normalize_report.json`). The unnormalized run is shown below for comparison.')
    L.append('- The primary result is the frozen run. A separate rerun with one executor fix is reported at the end and is not the primary result.')
    L.append('- The sample is below the 200-wrong-state gate (see Gates).\n')

    L.append('## Headline (primary run)\n')
    L.append(f"- Wrong accepts, all families: {pct(B['wrong_accept'], B['wrong'])}, after label corrections; 95% upper bound "
             f"{B['wrong_accept_ub95_pct']}%. Labels as claimed: {pct(A['wrong_accept'], A['wrong'])}. "
             f"If the a9f325aa formula state counts as wrong: {pct(S['wrong_accept'], S['wrong'])}.")
    L.append(f"- Commit rate on correct states in the LibreOffice families (group a): ACCEPT "
             f"{pct(G['a']['correct_exec'].get('ACCEPT', 0), G['a']['correct'])}. "
             f"REJECT {pct(G['a']['correct_exec'].get('REJECT', 0), G['a']['correct'])}. "
             f"UNDECIDED {pct(G['a']['correct_exec'].get('UNDECIDED', 0), G['a']['correct'])}.")
    L.append(f"- Wrong accepts in the LibreOffice families (group a): {pct(G['a']['wrong_accept'], G['a']['wrong'])}; "
             f"95% upper bound {G['a']['wrong_accept_ub95_pct']}%.")
    L.append(f"- No-reader families (group b): ACCEPT is ruled out for all {cov.get('wrong_states', 0) + cov.get('correct_states', 0)} "
             f"states, because each has a predicate the executor cannot evaluate. Their 0 wrong accepts is not evidence about the specs.\n")

    L.append('## Reader coverage split (primary run, adjusted labels)\n')
    L.append('Group (a) is the three LibreOffice families, where the executor has readers. Group (b) is gimp, multi_apps, '
             'thunderbird, vlc, vs_code and os, where it has none. The 95% upper bound is Clopper-Pearson.\n')
    L += SPLIT_HEAD
    for g in ('a', 'b', 'all'):
        L.append(split_line(GROUP_NAME[g], G[g], accept_possible=(g != 'b')))
    L.append('')
    L.append('Official checker, same split (labels adjusted):\n')
    L.append('| group | wrong: PASS | wrong: FAIL | wrong: NOT_RUNNABLE | correct: PASS | correct: FAIL | correct: NOT_RUNNABLE |')
    L.append('|---|---|---|---|---|---|---|')
    for g in ('a', 'b', 'all'):
        w, c = G[g]['wrong_official'], G[g]['correct_official']
        L.append(f"| {GROUP_NAME[g]} | {w.get('PASS', 0)} | {w.get('FAIL', 0)} | {w.get('NOT_RUNNABLE', 0)} | "
                 f"{c.get('PASS', 0)} | {c.get('FAIL', 0)} | {c.get('NOT_RUNNABLE', 0)} |")
    L.append('')
    L.append(f"Group (b) coverage: {cov.get('correct_states', 0)} correct states, of which "
             f"{cov.get('correct_with_unknown_app_root', 0)} name an app the executor has no reader for; the others "
             f"use syntax the parser does not accept. Wrong states in group (b): {cov.get('wrong_states', 0)}, of which "
             f"{cov.get('wrong_with_unknown_app_root', 0)} name an app with no reader. Group (b) rates say nothing about the specs.\n")

    L.append('## Cause of each non-accepted correct state in group (a)\n')
    L.append(f"{G['a']['correct'] - G['a']['correct_exec'].get('ACCEPT', 0)} of {G['a']['correct']} correct group (a) states "
             'are not accepted. Each has one primary cause, assigned by reading the failing predicates and the request '
             '(`blind_private/causes.py`, private).\n')
    L.append('| cause | states | REJECT | UNDECIDED | tasks | meaning |')
    L.append('|---|---|---|---|---|---|')
    for c in CAUSE_ORDER:
        x = res['causes'][c]
        if x['states']:
            L.append(f"| {c} | {x['states']} | {x['reject']} | {x['undecided']} | {', '.join(x['tasks'])} | {CAUSE_TEXT[c]} |")
    L.append(f"| total | {sum(res['causes'][c]['states'] for c in CAUSE_ORDER)} | "
             f"{sum(res['causes'][c]['reject'] for c in CAUSE_ORDER)} | "
             f"{sum(res['causes'][c]['undecided'] for c in CAUSE_ORDER)} | | |\n")
    L.append('Known executor defects, none fixed in the primary run:\n')
    L.append('- `table(n).rows` compared with an integer is tested row by row instead of counted. For a non-empty table, `rows == n` always fails and `rows != n` always passes. Fixed only in the rerun below.')
    L.append('- `.odt` files are opened with the .docx reader, which raises an error. The affected predicates stay UNDECIDED.')
    L.append('- Missing reader attributes: `CalcFile.charts`, `ShapeObj.height_cm` and `width_cm`, `TableObj.columns`, `DocxFile.body_order`.')
    L.append('- Grammar: quantifier forms such as `all x in ... where ...` and `all x in ...:`, `exists ... in ...:`, and clauses written as prose.\n')

    L.append('## Gates\n')
    L.append('| gate | result | status |')
    L.append('|---|---|---|')
    L.append(f"| wrong accepts <= 2% of >= 200 wrong states | all: {B['wrong_accept']}/{B['wrong']}, sample {B['wrong']} < 200, "
             f"upper bound {B['wrong_accept_ub95_pct']}%; group (a): {G['a']['wrong_accept']}/{G['a']['wrong']} | not met (sample size and bound) |")
    L.append(f"| wrong rejects <= 10% of correct states | all: REJECT {pct(B['correct_exec'].get('REJECT', 0), B['correct'])}; "
             f"group (a): REJECT {pct(G['a']['correct_exec'].get('REJECT', 0), G['a']['correct'])}, UNDECIDED "
             f"{pct(G['a']['correct_exec'].get('UNDECIDED', 0), G['a']['correct'])} | "
             f"met only when group (b) is included; group (a) fails. UNDECIDED is not counted as a reject |")
    L.append('| judge wrong accepts >= 3x specs | judge not run by this agent | pending (orchestrator) |\n')

    L.append('## Label x executor (labels as claimed, normalized states)\n')
    L.append('| label | ACCEPT | REJECT | UNDECIDED | total |')
    L.append('|---|---|---|---|---|')
    for lab, key in (('correct', 'correct_exec'), ('wrong', 'wrong_exec')):
        d = A[key]
        tot = A['correct'] if lab == 'correct' else A['wrong']
        L.append(f"| {lab} | {d.get('ACCEPT', 0)} | {d.get('REJECT', 0)} | {d.get('UNDECIDED', 0)} | {tot} |")
    L.append('')
    R = res['raw_run_no_normalization']
    L.append(f"Unnormalized run (no LibreOffice recalculation): correct ACCEPT {R['correct_exec'].get('ACCEPT', 0)}, "
             f"REJECT {R['correct_exec'].get('REJECT', 0)}, UNDECIDED {R['correct_exec'].get('UNDECIDED', 0)}; wrong ACCEPT "
             f"{R['wrong_exec'].get('ACCEPT', 0)}, REJECT {R['wrong_exec'].get('REJECT', 0)}, UNDECIDED "
             f"{R['wrong_exec'].get('UNDECIDED', 0)}. Normalization moved 7 states.\n")

    L.append('## Official checker (labels as claimed)\n')
    L.append(f"- Wrong states: {A['wrong_official']}")
    L.append(f"- Correct states: {A['correct_official']}\n")

    L.append('## Adjudication\n')
    L.append('Every state where the label disagrees with the executor or the official checker was read against the request and the state files. '
             f"{sum(res['categories'].values())} states were adjudicated.\n")
    L.append('| category | states | meaning |')
    L.append('|---|---|---|')
    meaning = {
        'LABEL_ERROR': 'label contradicts the request or the state; label changed',
        'SPEC_GAP': 'state is wrong and the spec accepts it (real wrong accept)',
        'SPEC_ERROR': 'state is correct and the spec contradicts itself',
        'EXECUTOR_DEFECT': 'state is correct and the executor rejects it because of a bug in the executor (not patched)',
        'OFFICIAL_FALSE_ACCEPT': 'state is wrong and the OSWorld checker passes it',
        'OFFICIAL_OVER_STRICT': 'state is correct and the OSWorld checker fails it',
        'AMBIGUOUS_LABEL': 'request supports two readings; label kept',
        'RENDERER': 'page count depends on the renderer; label kept',
    }
    for k in meaning:
        L.append(f"| {k} | {res['categories'].get(k, 0)} | {meaning[k]} |")
    L.append('')
    L.append(f"Label changes: {res['label_changes']}. Per-state evidence is in the private adjudication file, not in this repository.\n")

    L.append('## Ablation: gate-pass versus gate-fail specs (adjusted labels)\n')
    g, f = res['ablation']['gate_pass'], res['ablation']['gate_fail']
    L.append('| group | tasks | wrong states | wrong accepts | rate | 95% upper bound |')
    L.append('|---|---|---|---|---|---|')
    L.append(f"| gate-pass | {len(res['ablation']['gate_pass_tasks_in_blind_set'])} | {g['wrong']} | {g['wrong_accept']} | "
             f"{g['wrong_accept_pct']}% | {g['wrong_accept_ub95_pct']}% |")
    L.append(f"| gate-fail | {res['n_tasks'] - len(res['ablation']['gate_pass_tasks_in_blind_set'])} | {f['wrong']} | {f['wrong_accept']} | "
             f"{f['wrong_accept_pct']}% | {f['wrong_accept_ub95_pct']}% |\n")

    L.append('## Coverage by family (adjusted labels)\n')
    L.append('Executor UNDECIDED counts are states the executor could not decide. OSWorld NOT_RUNNABLE counts are states whose checker reads VM output or is unsupported.\n')
    L.append('| family | tasks | states | wrong | correct | wrong accepts | correct REJECT | correct UNDECIDED | correct ACCEPT | official NOT_RUNNABLE |')
    L.append('|---|---|---|---|---|---|---|---|---|---|')
    for row in res['families']:
        L.append('| ' + ' | '.join(str(x) for x in row) + ' |')
    L.append('')

    L.append('## Per task (adjusted labels)\n')
    L.append('| task | family | wrong | correct | wrong accepts | correct REJECT | correct UNDECIDED | correct ACCEPT | official NOT_RUNNABLE |')
    L.append('|---|---|---|---|---|---|---|---|---|')
    for row in res['tasks']:
        L.append('| ' + ' | '.join(str(x) for x in row) + ' |')
    L.append('')

    C = res['rerun_checks']
    L.append('## Separate rerun: `table(n).rows` fix (not the primary result)\n')
    L.append('The same end states and specs, with `EXP6_FIXES=table_rows`. The fix counts `table(n).rows` when it is compared with an integer. Nothing else changes. '
             f"Decisions changed for {C['decision_changed']} states, all in {'task' if len(C['tasks_changed']) == 1 else 'tasks'} {', '.join(C['tasks_changed']) or 'none'}. "
             f"Predicate records changed for {C['predicate_records_changed']} states. Official verdicts changed for {C['official_changed']} states.\n")
    L.append('Transitions (adjusted labels; changed states only):\n')
    L.append('| group | label | primary decision | rerun decision | states |')
    L.append('|---|---|---|---|---|')
    for t in res['rerun_transitions']:
        L.append(f"| {t['group']} | {t['label']} | {t['primary']} | {t['rerun']} | {t['states']} |")
    if not res['rerun_transitions']:
        L.append('| none | | | | 0 |')
    L.append('')
    L.append('Rerun reading (labels adjusted, same split):\n')
    L += SPLIT_HEAD
    for g in ('a', 'b', 'all'):
        L.append(split_line(GROUP_NAME[g], RG[g], accept_possible=(g != 'b')))
    L.append('')
    L.append('The two fixed states still do not accept. Their spec also uses `.columns` and `body_order`, which the executor does not read, so they move from REJECT to UNDECIDED.\n')

    L.append('## Not done\n')
    L.append('- Judge wrong accepts (orchestrator-run judge on the packets in `judge_packets/`).')
    L.append('- Wrong-accept sample is below 200 wrong states. More blind states are needed to meet that gate.')
    L.append('- Not fixed in either run: `.odt` reader, `.columns`, `body_order`, `charts`, `height_cm`/`width_cm`, and the grammar forms listed above.')
    L.append('- Word rendering was not available, so the renderer question is open.\n')
    with open(os.path.join(OUT, 'blind_results.md'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L))


if __name__ == '__main__':
    main()
