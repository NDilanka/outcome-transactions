"""Counterfactual test of writing-time rules for the spec writer. NOT a spec and NOT used for blind results.

Each variant applies hand-written edits to a copy of one exp5 must list, to show what a rule would change. The spec
YAML files are not modified. Each variant runs the executor on that task's gate roots (gold or positive, starts,
mutants) and reports decisions next to the unedited spec's decisions.

Rule under test (R): never pin order, names, geometry, or whitespace unless the request names them.
Variants that test other causes are labelled.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import specexec  # noqa: E402
import gate_check  # noqa: E402

IMPRESS = "libreoffice.impress.file('/home/user/Desktop/69_4.pptx')"
WRITER_GRAPHEME = "libreoffice.writer.file('/home/user/Desktop/Graphemes_Sound_Letter_Patterns.docx')"
WRITER_TUTORIAL = "libreoffice.writer.file('/home/user/Desktop/CCCH9003_Tutorial_guidelines.docx')"


def sub(must, idx, old, new):
    assert old in must[idx], (idx, must[idx][:120])
    must = list(must)
    must[idx] = must[idx].replace(old, new, 1)
    return must


def drop(must, idx, expect):
    assert expect in must[idx], (idx, must[idx][:120])
    return [m for i, m in enumerate(must) if i != idx]


# ---------------------------------------------------------------- variants: (task8, label, cause, edit(must) -> must)

def v_order_sheet(must):  # R: never pin order
    return sub(must, 0, 'sheet_names == ["Sheet1", "Sheet2"]', 'sheet_names set_equal ["Sheet1", "Sheet2"]')


def v_f23_rule(must):  # R: no geometry, no shape names; address the body by its text
    m = drop(must, 3, "shape('PlaceHolder 1') == before(")  # geometry of an untouched shape
    body = "Art is a diverse"
    m[1] = (f"{IMPRESS}.slide(1).shapes[*].text multiset_equal before({IMPRESS}.slide(1).shapes[*].text)")
    m[2] = (f'any(s.paragraph(1).bullet.type in ["char", "picture"] for s in {IMPRESS}.slide(1).shapes '
            f'if s.text startswith "{body}")')
    return m


def v_f23_geom_only(must):  # R, geometry part only: the names still pinned (gold 1 keeps failing)
    return drop(must, 3, "shape('PlaceHolder 1') == before(")


def v_ws(must):  # R: never pin whitespace in the table
    lhs = ("[[collapse_whitespace(replace(c.text, '\\u00a0', ' ')).strip() for c in row] "
           f"for row in {WRITER_TUTORIAL}.table(1).rows]")
    m = list(must)
    m[2] = f"{lhs} == before({lhs})"
    return m


def v_ws_noprose(must):  # class 3 check: the same, with the prose clause moved out of must (into footprint)
    return drop(v_ws(must), 0, 'followed by zero or one additional')


def v_936_order(must):  # R: never pin order or position; table content found by content
    rows_orig = must[1].split(' == ', 1)
    lhs = rows_orig[0].replace(f"{WRITER_GRAPHEME}.table(1).rows", 't.rows')
    m = sub(must, 1, rows_orig[0], f"any({lhs}")
    m[1] = m[1] + f" for t in {WRITER_GRAPHEME}.tables)"
    m[4] = (f"all(b in {WRITER_GRAPHEME}.tables for b in before({WRITER_GRAPHEME}.tables))")
    return m


def v_936_order_nocount(must):  # plus: the count pin dropped (R does not cover counts; tested separately)
    return drop(v_936_order(must), 0, 'len(libreoffice.writer.file')


def v_936_noprose(must):  # class 3 check: body_order prose moved out of must
    return drop(v_936_order(must), 2, 'body_order')


def v_a9f_drop_contradiction(must):  # class 2 check: drop the predicate that contradicts predicate 0
    return drop(must, 1, 'proper_case(')


VARIANTS = [
    ('42e0a640', 'rule_order_sheet', 'class1 order', v_order_sheet),
    ('1273e544', 'rule_order_sheet', 'class1 order', v_order_sheet),
    ('f23acfd2', 'rule_geometry_only', 'class1 geometry only', v_f23_geom_only),
    ('f23acfd2', 'rule_geometry_names', 'class1 geometry+names', v_f23_rule),
    ('88fe4b2d', 'rule_whitespace', 'class1 whitespace', v_ws),
    ('88fe4b2d', 'rule_whitespace_noprose', 'class1 whitespace + class3 prose removed', v_ws_noprose),
    ('936321ce', 'rule_order_position', 'class1 order/position', v_936_order),
    ('936321ce', 'rule_order_position_nocount', 'class1 order/position + count removed', v_936_order_nocount),
    ('936321ce', 'rule_order_position_noprose', 'class1 order/position + class3 prose removed', v_936_noprose),
    ('a9f325aa', 'drop_contradiction', 'class2 contradiction', v_a9f_drop_contradiction),
]


def main():
    specs = gate_check.load_specs()
    roots = json.load(open(os.path.join(HERE, 'gate', 'roots_mutants.json')))
    out = []
    for task8, label, cause, edit in VARIANTS:
        full = next(k for k in specs if k.startswith(task8))
        orig_must = specs[full]['must']
        new_must = edit(orig_must)
        for r in [x for x in roots if x['task'][:8] == task8]:
            o = specexec.run_spec({'must': orig_must}, r['root'], r['start_root'])['decision']
            n = specexec.run_spec({'must': new_must}, r['root'], r['start_root'])['decision']
            out.append({'task': task8, 'variant': label, 'cause': cause, 'state': r['state'], 'kind': r['kind'],
                        'original': o, 'variant_decision': n})
            print(f"{task8} {label:30} {r['state']:28} {r['kind']:9} {o:9} -> {n}", flush=True)
    json.dump(out, open(os.path.join(HERE, 'gate', 'rule_test.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
