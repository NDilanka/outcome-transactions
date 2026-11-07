import glob, json, os
from collections import Counter
T6 = '/home/factory-user/t6-work'
bm = json.load(open(os.path.join(T6, 'private/judge_blind_map.json')))
ver = {}
for f in sorted(glob.glob('/tmp/t6_verdicts/research/t6-ambiguity/judge_verdicts/verdicts_*.json')):
    ver.update(json.load(open(f)))
by = {(v['amb'], v['state']): k for k, v in bm.items()}
F = {r['id']: r for r in json.load(open(os.path.join(T6, 'executor_results.json')))}
S = {r['id']: r for r in json.load(open(os.path.join(T6, 'executor_results_eqfix.json')))}
amb = {a['id']: a for a in json.load(open(os.path.join(T6, 'private/ambiguity-set.json')))}
FOLLOW = {'amb01':'A','amb02':'A','amb03':'B','amb04':'A','amb05':'A','amb06':'A','amb07':'B','amb08':'A',
 'amb09':'A','amb10':'A','amb11':'A','amb12':'A','amb13':'A','amb14':'A','amb15':'A','amb16':'A',
 'amb17':'neither','amb18':'A','amb19':'A','amb20':'A','amb21':'A','amb22':'neither','amb23':'A','amb24':'A',
 'amb25':'A','amb26':'A','amb27':'A','amb28':'A','amb29':'A','amb30':'neither','amb31':'A','amb32':'A',
 'amb33':'A','amb34':'A','amb35':'A','amb36':'A','amb37':'A','amb38':'A','amb39':'neither','amb40':'A'}
NOTE_NEITHER = {'amb17':'writer followed "magnitude of each Amount grows" (values scaled); neither A nor B',
 'amb22':'writer followed "table already sums to 10, leave it"; neither A nor B',
 'amb30':'writer followed italics on both conditional lines and bracketed instructions; union of A and B',
 'amb39':'writer followed "remove bullet markers, keep text"; neither A nor B'}
NOOP = {'amb03':'A is byte-identical to start', 'amb14':'B is byte-identical to start',
 'amb16':'A and B both byte-identical to start (A = B); excluded from rate, reported separately',
 'amb24':'A is byte-identical to start', 'amb25':'A is byte-identical to start',
 'amb26':'A is byte-identical to start', 'amb35':'A is byte-identical to start'}
NOTE_NEITHER_ORDER = ['amb17','amb22','amb30','amb39']
def jv(aid, st):
    v = ver[by[(aid, st)]]
    return f"{v['verdict']} ({v['confidence']})"
rows = []
cnt = Counter()
for aid in sorted(amb):
    fA, fB = F[aid]['runs']['A']['empty_all_undecided_decision'], F[aid]['runs']['B']['empty_all_undecided_decision']
    sA, sB = S[aid]['runs']['A']['empty_all_undecided_decision'], S[aid]['runs']['B']['empty_all_undecided_decision']
    jA, jB = ver[by[(aid,'A')]]['verdict'], ver[by[(aid,'B')]]['verdict']
    cnt['judgeA_accept'] += jA == 'accept'; cnt['judgeB_accept'] += jB == 'accept'
    cnt['judge_both_accept'] += (jA == 'accept' and jB == 'accept')
    cnt['frozen_both_accept'] += (fA == 'ACCEPT' and fB == 'ACCEPT')
    cnt['sens_both_accept'] += (sA == 'ACCEPT' and sB == 'ACCEPT')
    fol = FOLLOW[aid] if aid not in NOTE_NEITHER else f"neither (note {NOTE_NEITHER_ORDER.index(aid)+1})"
    rows.append(f"| {aid} | {fA} / {sA} | {fB} / {sB} | {jv(aid,'A')} | {jv(aid,'B')} | {fol} | {NOOP.get(aid, '-')} |")
hdr = ("| request | spec on A (frozen / sensitivity) | spec on B (frozen / sensitivity) | judge on A (verdict, confidence) "
       "| judge on B (verdict, confidence) | writer's followed reading | no-op flags |\n"
       "|---|---|---|---|---|---|---|")
both_frozen = [aid for aid in sorted(amb) if F[aid]['runs']['A']['empty_all_undecided_decision']=='ACCEPT' and F[aid]['runs']['B']['empty_all_undecided_decision']=='ACCEPT']
both_sens = [aid for aid in sorted(amb) if S[aid]['runs']['A']['empty_all_undecided_decision']=='ACCEPT' and S[aid]['runs']['B']['empty_all_undecided_decision']=='ACCEPT']
judge_both = [aid for aid in sorted(amb) if ver[by[(aid,'A')]]['verdict']=='accept' and ver[by[(aid,'B')]]['verdict']=='accept']
summary = {
 'spec_both_frozen': both_frozen, 'spec_both_sens': both_sens, 'judge_both': judge_both,
 'frozen_and_judge_both': sorted(set(both_frozen) & set(judge_both)),
 'sens_and_judge_both': sorted(set(both_sens) & set(judge_both)),
}
notes = "\n".join(f"{i+1}. {a}: {NOTE_NEITHER[a]}." for i, a in enumerate(NOTE_NEITHER_ORDER))
open(os.path.join(T6, 't6-joined-table.md'), 'w').write(hdr + '\n' + '\n'.join(rows) + '\n\nNotes on the followed-reading column:\n' + notes + '\n')
json.dump({'summary': summary, 'counts': dict(cnt)}, open(os.path.join(T6, 't6-joined-summary.json'), 'w'), indent=1)
print(json.dumps({'summary': summary, 'counts': dict(cnt)}, indent=1))
print(hdr); print('\n'.join(rows)); print(dict(cnt))
