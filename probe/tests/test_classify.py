"""Unit tests for run classification and K1. No browser, no network.

Run: python -m unittest discover -s probe/tests -p "test_*.py" -v
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

from classify import DEFAULT_TASKS, classify, load_tasks, main  # noqa: E402

TASKS = load_tasks(DEFAULT_TASKS)
ELIGIBLE = [t for t in TASKS if TASKS[t]["native_draft_required"] == "no"]


def held_run(task_id, outcome="completes", attempt=1, **changes):
    run = {
        "task": task_id,
        "attempt": attempt,
        "held_outcome": outcome,
        "needs_response": ["server_id"] if outcome == "needs_response" else [],
        "faked_response": False,
        "native_draft_used": False,
        "unsafe_before_release": 0,
        "read_back_match": True if outcome == "completes" else None,
    }
    if outcome == "fails":
        run["fail_reason"] = "selector not found"
    run.update(changes)
    return run


def runs_for(overrides=None, extra_held=(), baseline_outcome="completes"):
    """Every task completes cleanly unless overridden. Baseline runs for all tasks."""
    overrides = overrides or {}
    held = [overrides.get(t, held_run(t)) for t in TASKS]
    held.extend(extra_held)
    baseline = [{"task": t, "outcome": baseline_outcome} for t in TASKS]
    if baseline_outcome == "fails":
        for run in baseline:
            run["fail_reason"] = "selector not found"
    return {"held": held, "baseline": baseline}


def row(result, task_id):
    return next(r for r in result["tasks"] if r["task"] == task_id)


class FrozenTaskListTests(unittest.TestCase):
    def test_twenty_four_tasks_eight_per_app(self):
        self.assertEqual(len(TASKS), 24)
        apps = [t["app"] for t in TASKS.values()]
        self.assertEqual(apps.count("records"), 8)
        self.assertEqual(apps.count("webmail"), 8)
        self.assertEqual(apps.count("checkout"), 8)

    def test_draft_required_tasks_are_m3_m4_s6(self):
        required = {t for t in TASKS if TASKS[t]["native_draft_required"] == "yes"}
        self.assertEqual(required, {"M3", "M4", "S6"})

    def test_max_possible_numerator_is_21(self):
        result = classify(TASKS, runs_for())
        self.assertEqual(result["k1"]["max_possible"], 21)
        self.assertEqual(result["k1"]["numerator"], 21)
        self.assertFalse(result["k1"]["k1_triggered"])


class ExclusionTests(unittest.TestCase):
    def test_clean_eligible_task_counts(self):
        result = classify(TASKS, runs_for())
        r = row(result, "R1")
        self.assertTrue(r["counts_for_k1"])
        self.assertEqual(r["exclusions"], [])
        self.assertFalse(r["faked_response"])
        self.assertFalse(r["native_draft_used"])

    def test_draft_required_task_never_counts_even_if_draft_not_used(self):
        result = classify(TASKS, runs_for())
        for task_id in ("M3", "M4", "S6"):
            r = row(result, task_id)
            self.assertFalse(r["counts_for_k1"], task_id)
            self.assertIn("native_draft_required", r["exclusions"])

    def test_each_failed_condition_is_recorded(self):
        cases = [
            ("needs_response", held_run("R1", "needs_response"), "held_outcome is needs_response"),
            ("fails", held_run("R1", "fails"), "held_outcome is fails"),
            ("faked", held_run("R1", faked_response=True), "faked_response"),
            ("draft used", held_run("R1", native_draft_used=True), "native_draft_used"),
            ("hold leak", held_run("R1", unsafe_before_release=1), "hold_leak"),
            ("read back mismatch", held_run("R1", read_back_match=False), "read_back_mismatch"),
            ("read back missing", held_run("R1", read_back_match=None), "read_back_missing"),
        ]
        for label, run, reason in cases:
            with self.subTest(label):
                result = classify(TASKS, runs_for({"R1": run}))
                r = row(result, "R1")
                self.assertFalse(r["counts_for_k1"])
                self.assertIn(reason, r["exclusions"])
                self.assertEqual(result["k1"]["numerator"], 20)

    def test_faked_and_draft_are_recorded_as_separate_fields(self):
        run = held_run("R2", faked_response=True, native_draft_used=True)
        r = row(classify(TASKS, runs_for({"R2": run})), "R2")
        self.assertTrue(r["faked_response"])
        self.assertTrue(r["native_draft_used"])
        self.assertIn("faked_response", r["exclusions"])
        self.assertIn("native_draft_used", r["exclusions"])

    def test_baseline_does_not_change_the_numerator(self):
        result = classify(TASKS, runs_for(baseline_outcome="fails"))
        self.assertEqual(result["k1"]["numerator"], 21)
        self.assertEqual(result["k1"]["baseline_completes"], 0)
        self.assertEqual(row(result, "R1")["baseline_outcome"], "fails")


class ThresholdTests(unittest.TestCase):
    def _with_completing(self, count):
        """Make exactly `count` eligible tasks count; every other task fails."""
        keep = set(ELIGIBLE[:count])
        overrides = {}
        for t in TASKS:
            if t not in keep:
                overrides[t] = held_run(t, "fails")
        return classify(TASKS, runs_for(overrides))

    def test_twelve_of_twenty_four_does_not_trigger_k1(self):
        result = self._with_completing(12)
        self.assertEqual(result["k1"]["numerator"], 12)
        self.assertEqual(result["k1"]["denominator"], 24)
        self.assertFalse(result["k1"]["k1_triggered"])

    def test_eleven_of_twenty_four_triggers_k1(self):
        result = self._with_completing(11)
        self.assertEqual(result["k1"]["numerator"], 11)
        self.assertTrue(result["k1"]["k1_triggered"])

    def test_counted_by_app_adds_up(self):
        result = self._with_completing(12)
        self.assertEqual(sum(result["k1"]["counted_by_app"].values()), 12)


class RetryTests(unittest.TestCase):
    def test_retry_is_listed_and_does_not_change_the_numerator(self):
        overrides = {"R1": held_run("R1", "fails")}
        extra = [held_run("R1", attempt=2)]
        result = classify(TASKS, runs_for(overrides, extra_held=extra))
        self.assertFalse(row(result, "R1")["counts_for_k1"])
        self.assertEqual(result["k1"]["numerator"], 20)
        self.assertEqual(result["retries"], [{"task": "R1", "attempt": 2, "held_outcome": "completes", "counts_for_k1": False}])


class ValidationTests(unittest.TestCase):
    def assertRejects(self, runs, fragment):
        with self.assertRaises(ValueError) as ctx:
            classify(TASKS, runs)
        self.assertIn(fragment, str(ctx.exception))

    def test_missing_measured_run_is_an_error(self):
        runs = runs_for()
        runs["held"] = [r for r in runs["held"] if r["task"] != "R1"]
        self.assertRejects(runs, "R1")

    def test_missing_baseline_is_an_error(self):
        runs = runs_for()
        runs["baseline"] = [b for b in runs["baseline"] if b["task"] != "S8"]
        self.assertRejects(runs, "S8")

    def test_duplicate_attempt_is_an_error(self):
        runs = runs_for(extra_held=[held_run("R1")])
        self.assertRejects(runs, "duplicate attempt")

    def test_unknown_task_is_an_error(self):
        runs = runs_for(extra_held=[held_run("X9")])
        self.assertRejects(runs, "unknown task")

    def test_needs_response_must_name_the_response(self):
        self.assertRejects(runs_for({"R1": held_run("R1", "needs_response", needs_response=[])}), "needs_response")

    def test_unknown_response_kind_is_an_error(self):
        self.assertRejects(runs_for({"R1": held_run("R1", "needs_response", needs_response=["magic"])}), "needs_response")

    def test_completes_cannot_list_a_response(self):
        self.assertRejects(runs_for({"R1": held_run("R1", needs_response=["server_id"])}), "needs_response")

    def test_fails_needs_a_reason(self):
        self.assertRejects(runs_for({"R1": held_run("R1", "fails", fail_reason="")}), "fail_reason")

    def test_flags_must_be_booleans(self):
        self.assertRejects(runs_for({"R1": held_run("R1", faked_response="no")}), "faked_response")
        self.assertRejects(runs_for({"R1": held_run("R1", native_draft_used=0)}), "native_draft_used")

    def test_unsafe_count_must_be_a_non_negative_int(self):
        self.assertRejects(runs_for({"R1": held_run("R1", unsafe_before_release=-1)}), "unsafe_before_release")
        self.assertRejects(runs_for({"R1": held_run("R1", unsafe_before_release=True)}), "unsafe_before_release")

    def test_bad_held_outcome_is_an_error(self):
        self.assertRejects(runs_for({"R1": held_run("R1", "done")}), "held_outcome")

    def test_attempt_must_be_one_or_more(self):
        self.assertRejects(runs_for(extra_held=[held_run("R1", attempt=0)]), "attempt")


class CliTests(unittest.TestCase):
    def test_round_trip_writes_json_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runs.json"
            path.write_text(json.dumps(runs_for()), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["--runs", str(path)])
        self.assertEqual(code, 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["k1"]["numerator"], 21)

    def test_bad_input_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runs.json"
            path.write_text(json.dumps({"held": [], "baseline": []}), encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = main(["--runs", str(path)])
        self.assertEqual(code, 2)
        self.assertIn("no measured held run", err.getvalue())


if __name__ == "__main__":
    unittest.main()
