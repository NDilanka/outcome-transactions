"""Exp 8: build GT v4 from GT v3 after the orchestrator's rulings. POST-HOC, not pre-registered.

Changes, each checked against v3 before it is written:
  ecc2413d (ruling 1c, LibreOffice render is the GT for page layout): m1, m2, m4 C -> W; m3 W -> C.
    The render (ruling_ecc2413d.py) shows only m3 adds a blank page after page 1, as the request asks.
  d53ff5ee (ruling d53ff5ee, option a, decided by the orchestrator): a6cac88c W -> C. Its output is identical to
    699226e8 (C). Both lowercase only all-caps text (ruling_d53ff5ee.py). 699226e8 stays C.
  6054afcb (ruling 1b): no change. All four end states stay C.
  The auto-save family is not changed here. The strict reading is applied in metrics.py (AUTOSAVE_STRICT_W).

Writes /home/factory-user/exp8/gt/final_gt_v4.tsv (private, not committed). Plain python3, no third-party imports.
"""
V3 = '/home/factory-user/exp8/gt/final_gt_v3.tsv'
V4 = '/home/factory-user/exp8/gt/final_gt_v4.tsv'

# code: (v3 verdict, v4 verdict, reason)
CHANGES = {
    '476b080a': ('C', 'W', 'ecc2413d m1: render has no blank page after page 1 (7 pages, text equal to input). Ruling 1c.'),
    'eeb4b683': ('C', 'W', 'ecc2413d m2: same render result as m1. Ruling 1c.'),
    '7b72ebd1': ('C', 'W', 'ecc2413d m4: same render result as m1. Ruling 1c.'),
    '02d030c7': ('W', 'C', 'ecc2413d m3: render adds a blank page 2 right after page 1, as requested. Ruling 1c.'),
    'a6cac88c': ('W', 'C', 'd53ff5ee m3: same output as 699226e8, only all-caps text lowercased. Ruling d53ff5ee.'),
}


def build():
    seen = set()
    lines = []
    for line in open(V3):
        if line.startswith('#') or not line.strip():
            lines.append(line.rstrip('\n'))
            continue
        cols = line.rstrip('\n').split('\t')
        code = cols[0]
        if code in CHANGES:
            old, new, note = CHANGES[code]
            assert cols[1] == old, (code, cols[1], old)
            cols[1] = new
            cols = cols[:6] + [f'v4 {old}->{new}: {note}']
            seen.add(code)
        lines.append('\t'.join(cols))
    assert seen == set(CHANGES), set(CHANGES) - seen
    lines.insert(0, '# GT v4, built from final_gt_v3.tsv by make_gt_v4.py. Post-hoc rulings; see exp8-results.md.')
    with open(V4, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print('wrote', V4, '| changed rows:', len(seen))
    for c in sorted(CHANGES):
        print(f'  {c} {CHANGES[c][0]}->{CHANGES[c][1]}')


if __name__ == '__main__':
    build()
