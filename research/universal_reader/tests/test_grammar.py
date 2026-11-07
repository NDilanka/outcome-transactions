"""Tests for the extended predicate grammar (research/universal_reader/grammar.py).

Run from the repository root:
  python -m unittest research.universal_reader.tests.test_grammar -v
"""
import glob
import os
import sys
import unittest

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, REPO)

from research.universal_reader import evaluate, grammar  # noqa: E402

SPECS = os.path.join(REPO, 'research', 'exp5-grounded', 'specs')
frozen = grammar._frozen  # the frozen executor, loaded read-only


def _must_predicates():
    out = []
    for path in sorted(glob.glob(os.path.join(SPECS, 'batch_*.yaml'))):
        with open(path, encoding='utf-8') as fh:
            specs = yaml.safe_load(fh) or []
        for spec in specs:
            for src in spec.get('must', []):
                out.append((spec['id'], grammar.strip_comment(src)))
    return out


# Predicates the grammar cannot read as code. They are natural language, and evaluate to UNSUPPORTED.
# The count is fixed for the Exp 5 specs as they are now. A spec change that adds or removes one is a reviewed change.
PROSE_COUNT = 28


class FrozenEquivalenceTests(unittest.TestCase):
    def test_predicates_the_frozen_parser_reads_keep_the_same_tree(self):
        preds = _must_predicates()
        self.assertEqual(len(preds), 302)
        checked, differ = 0, []
        for sid, src in preds:
            try:
                want = frozen.parse(src)
            except Exception:
                continue
            checked += 1
            got = grammar.parse(src)
            if got != want:
                differ.append((sid, src[:80]))
        self.assertEqual(checked, 206)
        self.assertEqual(differ, [])

    def test_frozen_module_is_the_one_file_in_the_repository(self):
        path = os.path.join(REPO, 'research', 'exp6-executed', 'specexec.py')
        self.assertEqual(os.path.abspath(frozen.__file__), os.path.abspath(path))


class ParseCoverageTests(unittest.TestCase):
    def test_every_predicate_gives_a_node_and_the_count_of_unreadable_text_is_fixed(self):
        kinds = {}
        for _, src in _must_predicates():
            node = grammar.parse(src)  # never raises
            kinds[node[0]] = kinds.get(node[0], 0) + 1
        self.assertEqual(kinds.get('prose', 0), PROSE_COUNT, kinds)
        self.assertEqual(sum(kinds.values()), 302)

    def test_live_probe_predicates_are_marked_live_not_parsed_as_code(self):
        live = [src for _, src in _must_predicates() if grammar.parse(src)[0] == 'live']
        self.assertTrue(live)
        for src in live:
            self.assertTrue(src.lstrip().startswith('probe'), src[:60])
            with self.assertRaises(Exception):
                frozen.parse(src)  # a probe that the frozen parser reads is an ordinary name, never 'live'


def _status(pred):
    """Status of one predicate on an empty state, the way the evaluator runs it."""
    res = evaluate.run_spec({'id': 't', 'must': [pred]}, {}, {}, None, None)
    rec = res['predicates'][0]
    return rec['status'], rec['reason']


class NewFormsEvaluateTests(unittest.TestCase):
    """Each new form gives PASS, FAIL or UNSUPPORTED. Never ERROR."""

    def test_new_forms_have_their_expected_status(self):
        cases = [
            ("'abc' matches /B/i", 'PASS'),
            ("'abc' does_not_match /z/", 'PASS'),
            ("'abc' matches /z/", 'FAIL'),
            ("'abc' contains 'b'", 'PASS'),
            ("{'a': 1}['a'] == 1", 'PASS'),
            ("(1, 2) == (1, 2)", 'PASS'),
            ("(1 == 2) ? false : true", 'PASS'),
            ("if 1 == 2: 1 == 3", 'PASS'),
            ("let x = 2; x + 1 == 3", 'PASS'),
            ("2 as y; y == 2", 'PASS'),
            ("set_equal([1, 2], [2, 1])", 'PASS'),
            ("[1, 2, 3] ordered_by ascending", 'PASS'),
            ("[3, 1] ordered_by ascending", 'FAIL'),
            ("all x in [1, 2] where x > 0", 'PASS'),
            ("count(x for x in [1, 2, 3] if x > 1) == 2", 'PASS'),
            ("for each v in [1, 2]: v > 0", 'PASS'),
            ("join(['a', 'b'], sep='-') == 'a-b'", 'PASS'),
            ("'a' is 'a'", 'PASS'),
            ("null is null", 'PASS'),
            ("6 & 3 == 2", 'PASS'),
            ("'x' & 1 == 1", 'UNSUPPORTED'),
            ("1 / 0 == 1", 'UNSUPPORTED'),
            ("[1, 2] similarity >= 0.5 [1, 2]", 'UNSUPPORTED'),
            ("let x = 2", 'UNSUPPORTED'),
            ("probe.launch('x').ok == true", 'UNSUPPORTED'),
            ("probe: the window opens", 'UNSUPPORTED'),
            ("the cat sat on the mat", 'UNSUPPORTED'),
            ("no_such_root.value == 1", 'UNSUPPORTED'),
        ]
        for pred, want in cases:
            status, reason = _status(pred)
            self.assertNotEqual(status, 'ERROR', f'{pred}: {reason}')
            self.assertEqual(status, want, f'{pred}: {reason}')


if __name__ == '__main__':
    unittest.main()
