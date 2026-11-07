import json
F = {r['id']: r for r in json.load(open('executor_results.json'))}
S = {r['id']: r for r in json.load(open('executor_results_eqfix.json'))}
# Followed reading: mapped by hand from the writer flag text vs reading_A / reading_B (A/B/NONE)
FOLLOW = {'amb01':'A','amb02':'A','amb03':'B','amb04':'A','amb05':'A','amb06':'A','amb07':'B','amb08':'A',
 'amb09':'A','amb10':'A','amb11':'A','amb12':'A','amb13':'A','amb14':'A','amb15':'A','amb16':'A',
 'amb17':'NONE','amb18':'A','amb19':'A','amb20':'A','amb21':'A','amb22':'NONE','amb23':'A','amb24':'A',
 'amb25':'A','amb26':'A','amb27':'A','amb28':'A','amb29':'A','amb30':'NONE','amb31':'A','amb32':'A',
 'amb33':'A','amb34':'A','amb35':'A','amb36':'A','amb37':'A','amb38':'A','amb39':'NONE','amb40':'A'}
# Reading is a no-op on the starting file (end state byte-identical to start, per verify_endstates.py)
NOOP = {'amb03':'A','amb14':'B','amb16':'A,B','amb24':'A','amb25':'A','amb26':'A','amb35':'A'}
def dec(R, aid, lab): return R[aid]['runs'][lab]['empty_all_undecided_decision']
rows = []
for aid in sorted(F):
    row = {'id': aid, 'followed': FOLLOW[aid], 'noop': NOOP.get(aid, '-')}
    for tag, R in (('F', F), ('S', S)):
        for lab in ('A', 'B', 'START'):
            row[f'{tag}_{lab}'] = dec(R, aid, lab)
    rows.append(row)
json.dump(rows, open('final_table.json', 'w'), indent=1)
for tag in ('F', 'S'):
    both = [r['id'] for r in rows if r[f'{tag}_A'] == 'ACCEPT' and r[f'{tag}_B'] == 'ACCEPT']
    start = [r['id'] for r in rows if r[f'{tag}_START'] == 'ACCEPT']
    accA = sum(r[f'{tag}_A'] == 'ACCEPT' for r in rows); accB = sum(r[f'{tag}_B'] == 'ACCEPT' for r in rows)
    print(tag, 'A-accept', accA, 'B-accept', accB, '| both-accept', len(both), both, '| START-accept', len(start), start)
