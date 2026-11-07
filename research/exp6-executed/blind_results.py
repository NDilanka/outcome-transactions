"""Aggregates the Exp 6 blind run into results/blind_results.md and results/blind_results.json.

Inputs are private and gitignored: blind_run/score_rows.json (decisions joined to generator labels, written by
blind_score.py) and blind_private/adjudication.json (written by blind_private/adjudicate.py). The outputs contain
aggregates only: no state names, no per-state labels, no blind ids.

Usage: blind_results.py
"""
import collections, json, os, re, sys

from scipy.stats import beta

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = os.path.join(HERE, 'blind_run', 'score_rows.json')
RAW_ROWS = os.path.join(HERE, 'blind_run_raw', 'score_rows.json')
ADJ = os.path.join(HERE, 'blind_private', 'adjudication.json')
README = os.path.join(HERE, 'blind_src', 'research', 'exp6-blind-states', 'README.md')
OUT = os.path.join(HERE, 'results')
# Specs that pass the mutation gate (exp6-gate.md). Intersected with the blind set below.
GATE_PASS = {'6054afcb', '21760ecb', 'd53ff5ee', 'ecc2413d', '4d117223'}


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
        'correct_reject_pct': round(100 * ce.get('REJECT', 0) / len(C), 1) if C else None,
        'correct_undecided_pct': round(100 * ce.get('UNDECIDED', 0) / len(C), 1) if C else None,
        'correct_not_accepted_pct': round(100 * (len(C) - ce.get('ACCEPT', 0)) / len(C), 1) if C else None,
        'wrong_official': dict(collections.Counter(v['official'] for v in W)),
        'correct_official': dict(collections.Counter(v['official'] for v in C)),
    }


def main():
    rows = json.load(open(ROWS, encoding='utf-8'))
    raw_rows = json.load(open(RAW_ROWS, encoding='utf-8'))
    adj_list = json.load(open(ADJ, encoding='utf-8'))
    adj = {a['blind_id']: a for a in adj_list}
    fam = families()
    for r in rows:
        r['family'] = fam[r['task'][:8]]
        r['task8'] = r['task'][:8]
    res = {'n_states': len(rows), 'n_tasks': len({r['task8'] for r in rows}),
           'raw_run_no_normalization': summarize(view(raw_rows, {}, 'raw')),
           'as_labelled': summarize(view(rows, adj, 'raw')),
           'adjusted': summarize(view(rows, adj, 'adjusted')),
           'sensitivity': summarize(view(rows, adj, 'sens')),
           'categories': dict(collections.Counter(a['category'] for a in adj_list)),
           'label_changes': dict(collections.Counter(
               f"{a['label']} -> {a['adjusted_label']}" for a in adj_list if a['category'] == 'LABEL_ERROR'))}

    adjv = view(rows, adj, 'adjusted')
    gp = [v for v in adjv if v['task8'] in GATE_PASS]
    gf = [v for v in adjv if v['task8'] not in GATE_PASS]
    res['ablation'] = {'gate_pass': summarize(gp), 'gate_fail': summarize(gf),
                       'gate_pass_tasks_in_blind_set': sorted({v['task8'] for v in gp})}

    # The executor has readers only for the LibreOffice families. Elsewhere it cannot accept, so the all-family rate is diluted.
    file_fams = {'libreoffice_calc', 'libreoffice_impress', 'libreoffice_writer'}
    res['file_families'] = summarize([v for v in adjv if v['family'] in file_fams])

    fam_rows = []
    for f in sorted({r['family'] for r in rows}):
        sub = [v for v in adjv if v['family'] == f]
        s = summarize(sub)
        fam_rows.append((f, len({v['task8'] for v in sub}), s['states'], s['wrong'], s['correct'],
                         s['wrong_accept'], s['correct_exec'].get('REJECT', 0), s['correct_exec'].get('UNDECIDED', 0),
                         s['correct_exec'].get('ACCEPT', 0), sum(v['official'] == 'NOT_RUNNABLE' for v in sub)))
    res['families'] = fam_rows

    task_rows = []
    for t in sorted({v['task8'] for v in adjv}):
        sub = [v for v in adjv if v['task8'] == t]
        s = summarize(sub)
        task_rows.append((t, sub[0]['family'], s['wrong'], s['correct'], s['wrong_accept'],
                          s['correct_exec'].get('REJECT', 0), s['correct_exec'].get('UNDECIDED', 0),
                          s['correct_exec'].get('ACCEPT', 0), sum(v['official'] == 'NOT_RUNNABLE' for v in sub)))
    res['tasks'] = task_rows

    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, 'blind_results.json'), 'w'), indent=1, ensure_ascii=False, default=str)
    write_md(res)
    print(json.dumps({k: res[k] for k in ('as_labelled', 'adjusted', 'sensitivity')}, indent=1, default=str)[:3000])


def pct(a, b):
    return f'{a}/{b} ({round(100 * a / b, 1)}%)' if b else 'n/a'


def write_md(res):
    A, B, S = res['as_labelled'], res['adjusted'], res['sensitivity']
    L = []
    L.append('# Exp 6 blind run: results\n')
    L.append('Generated by `research/exp6-executed/blind_results.py` from the private run files. Aggregates only.\n')
    L.append('## Scope\n')
    L.append(f"- {res['n_states']} blind end states from {res['n_tasks']} tasks (generator labels: "
             f"{A['wrong']} wrong, {A['correct']} correct).")
    L.append('- Specs run as written (`specexec.py`). OSWorld checker run where its functions read a file.')
    L.append('- End states are the normalized copies: 15 workbooks were re-saved and recalculated by LibreOffice '
             'because the generator dropped cached formula values (`normalize_states.py`, checks in '
             '`normalize_report.json`). The unnormalized run is shown below for comparison.')
    L.append('- The sample is below the 200-wrong-state gate (see Gates).\n')

    L.append('## Headline\n')
    L.append(f"- Wrong accepts, labels as claimed: {pct(A['wrong_accept'], A['wrong'])}; 95% upper bound "
             f"{A['wrong_accept_ub95_pct']}%.")
    L.append(f"- Wrong accepts, after label corrections: {pct(B['wrong_accept'], B['wrong'])}; 95% upper bound "
             f"{B['wrong_accept_ub95_pct']}%.")
    L.append(f"- Wrong accepts, if the a9f325aa formula state counts as wrong: {pct(S['wrong_accept'], S['wrong'])}; "
             f"upper bound {S['wrong_accept_ub95_pct']}%.")
    F = res['file_families']
    L.append(f"- Wrong accepts in the three LibreOffice families only (the executor has readers there; other families are "
             f"UNDECIDED or NOT_RUNNABLE by construction): {pct(F['wrong_accept'], F['wrong'])}; upper bound "
             f"{F['wrong_accept_ub95_pct']}%.")
    L.append(f"- Correct states rejected by the executor, after corrections: {pct(B['correct_exec'].get('REJECT', 0), B['correct'])}. "
             f"Of these, 2 come from an executor bug, 1 from a spec contradiction, 2 from a renderer question, and 1 from an "
             f"ambiguous reading.")
    L.append(f"- Correct states not accepted (REJECT or UNDECIDED), after corrections: "
             f"{pct(B['correct'] - B['correct_exec'].get('ACCEPT', 0), B['correct'])}.\n")

    L.append('## Gates\n')
    L.append('| gate | result | status |')
    L.append('|---|---|---|')
    L.append(f"| wrong accepts <= 2% of >= 200 wrong states | {B['wrong_accept']}/{B['wrong']}; sample is "
             f"{B['wrong']} < 200; upper bound {B['wrong_accept_ub95_pct']}% | not met (sample size and bound) |")
    L.append(f"| wrong rejects <= 10% of correct-but-different states | REJECT {pct(B['correct_exec'].get('REJECT', 0), B['correct'])}; "
             f"not accepted incl. UNDECIDED {pct(B['correct'] - B['correct_exec'].get('ACCEPT', 0), B['correct'])} | "
             f"met only for REJECT, and only by a small margin; UNDECIDED is not counted as a reject |")
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

    L.append('## Not done\n')
    L.append('- Judge wrong accepts (orchestrator-run judge on the packets in `judge_packets/`).')
    L.append('- Wrong-accept sample is below 200 wrong states. More blind states are needed to meet that gate.')
    L.append('- The executor defect in table(n).rows is not patched, so these numbers are from the frozen run.')
    L.append('- Word rendering was not available, so the renderer question is open.\n')
    with open(os.path.join(OUT, 'blind_results.md'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L))


if __name__ == '__main__':
    main()
