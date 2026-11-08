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
# M5 is a webmail task. Its primary run holds the open-message GET, which the
# sensitivity policy passes in these tests.
SCOPE_TASK = "M5"
SCOPE_RULE = "webmail-open-message"
SCOPE_RULES = frozenset({SCOPE_RULE})


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
        "gets_held": [],
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


def sens_row(result, task_id):
    return next(r for r in result["tasks_sensitivity"] if r["task"] == task_id)


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


class GetRecordTests(unittest.TestCase):
    """gets_held: every held run names the GET rules that held a request in it."""

    def assertRejects(self, runs, fragment):
        with self.assertRaises(ValueError) as ctx:
            classify(TASKS, runs, SCOPE_RULES)
        self.assertIn(fragment, str(ctx.exception))

    def test_gets_held_is_required(self):
        run = held_run("R1")
        del run["gets_held"]
        self.assertRejects(runs_for({"R1": run}), "gets_held")

    def test_gets_held_must_be_a_list_of_names(self):
        self.assertRejects(runs_for({"M5": held_run("M5", gets_held=SCOPE_RULE)}), "gets_held")
        self.assertRejects(runs_for({"M5": held_run("M5", gets_held=[{"name": SCOPE_RULE}])}), "gets_held")

    def test_gets_held_names_each_rule_once(self):
        self.assertRejects(runs_for({"M5": held_run("M5", gets_held=[SCOPE_RULE, SCOPE_RULE])}), "gets_held")

    def test_unknown_rule_name_is_an_error(self):
        self.assertRejects(runs_for({"M5": held_run("M5", gets_held=["made-up-rule"])}), "made-up-rule")

    def test_rule_must_belong_to_the_task_app(self):
        self.assertRejects(runs_for({"R1": held_run("R1", gets_held=[SCOPE_RULE])}), "belongs to webmail")

    def test_unknown_sensitivity_rule_is_an_error(self):
        with self.assertRaises(ValueError) as ctx:
            classify(TASKS, runs_for(), frozenset({"no-such-rule"}))
        self.assertIn("no-such-rule", str(ctx.exception))


class SensitivityTests(unittest.TestCase):
    def _scope_runs(self, primary_outcome="completes", baseline_outcome="completes"):
        """M5 touches the passable GET in its primary run. Every other task is clean."""
        overrides = {SCOPE_TASK: held_run(SCOPE_TASK, primary_outcome, gets_held=[SCOPE_RULE])}
        return runs_for(overrides, baseline_outcome=baseline_outcome)

    def test_no_passable_gets_means_every_row_is_copied(self):
        result = classify(TASKS, runs_for(), frozenset())
        self.assertEqual(result["k1_sensitivity"]["numerator"], result["k1"]["numerator"])
        self.assertEqual(result["k1_sensitivity"]["sensitivity_run_tasks"], [])
        self.assertEqual(result["k1_sensitivity"]["copied_from_primary"], sorted(TASKS))
        self.assertTrue(all(r["copied_from_primary"] for r in result["tasks_sensitivity"]))

    def test_scope_is_the_tasks_whose_primary_run_held_a_passable_get(self):
        runs = self._scope_runs("fails")
        runs["held_sensitivity"] = [held_run(SCOPE_TASK)]
        result = classify(TASKS, runs, SCOPE_RULES)
        self.assertEqual(result["k1_sensitivity"]["sensitivity_run_tasks"], [SCOPE_TASK])
        self.assertEqual(
            result["k1_sensitivity"]["copied_from_primary"],
            sorted(t for t in TASKS if t != SCOPE_TASK),
        )
        self.assertFalse(sens_row(result, SCOPE_TASK)["copied_from_primary"])
        self.assertTrue(sens_row(result, "R1")["copied_from_primary"])

    def test_only_the_scope_task_changes_between_policies(self):
        # M5 fails under the primary policy and completes under the sensitivity policy.
        runs = self._scope_runs("fails")
        runs["held_sensitivity"] = [held_run(SCOPE_TASK)]
        result = classify(TASKS, runs, SCOPE_RULES)
        self.assertEqual(result["k1"]["numerator"], 20)
        self.assertEqual(result["k1_sensitivity"]["numerator"], 21)
        for task_id in TASKS:
            if task_id != SCOPE_TASK:
                self.assertEqual(sens_row(result, task_id)["counts_for_k1"], row(result, task_id)["counts_for_k1"], task_id)

    def test_copied_row_is_the_primary_row(self):
        runs = self._scope_runs("fails")
        runs["held_sensitivity"] = [held_run(SCOPE_TASK)]
        result = classify(TASKS, runs, SCOPE_RULES)
        copied = sens_row(result, "R1")
        self.assertEqual(copied, {**row(result, "R1"), "copied_from_primary": True})

    def test_both_policies_are_reported_separately(self):
        # Primary: 11 eligible tasks count. M5 is one of the 10 failures. Sensitivity: M5 completes, so 12 count.
        keep = [t for t in ELIGIBLE if t != SCOPE_TASK][:11]
        overrides = {t: held_run(t, "fails") for t in ELIGIBLE if t not in keep}
        overrides[SCOPE_TASK] = held_run(SCOPE_TASK, "fails", gets_held=[SCOPE_RULE])
        runs = runs_for(overrides)
        runs["held_sensitivity"] = [held_run(SCOPE_TASK)]
        result = classify(TASKS, runs, SCOPE_RULES)
        self.assertEqual(result["k1"]["policy"], "primary")
        self.assertEqual(result["k1"]["numerator"], 11)
        self.assertTrue(result["k1"]["k1_triggered"])
        self.assertEqual(result["k1_sensitivity"]["policy"], "sensitivity")
        self.assertEqual(result["k1_sensitivity"]["numerator"], 12)
        self.assertFalse(result["k1_sensitivity"]["k1_triggered"])
        self.assertEqual(len(result["tasks_sensitivity"]), 24)

    def test_scope_task_without_a_sensitivity_run_is_an_error(self):
        with self.assertRaises(ValueError) as ctx:
            classify(TASKS, self._scope_runs("fails"), SCOPE_RULES)
        self.assertIn(SCOPE_TASK, str(ctx.exception))

    def test_sensitivity_run_for_a_task_outside_scope_is_an_error(self):
        runs = self._scope_runs("fails")
        runs["held_sensitivity"] = [held_run(SCOPE_TASK), held_run("R1")]
        with self.assertRaises(ValueError) as ctx:
            classify(TASKS, runs, SCOPE_RULES)
        self.assertIn("R1", str(ctx.exception))

    def test_sensitivity_run_cannot_hold_a_rule_it_passes(self):
        runs = self._scope_runs("fails")
        runs["held_sensitivity"] = [held_run(SCOPE_TASK, gets_held=[SCOPE_RULE])]
        with self.assertRaises(ValueError) as ctx:
            classify(TASKS, runs, SCOPE_RULES)
        self.assertIn("sensitivity", str(ctx.exception))

    def test_sensitivity_retry_is_listed_and_does_not_change_the_numerator(self):
        runs = self._scope_runs("fails")
        runs["held_sensitivity"] = [held_run(SCOPE_TASK), held_run(SCOPE_TASK, "fails", attempt=2)]
        result = classify(TASKS, runs, SCOPE_RULES)
        self.assertEqual(result["k1_sensitivity"]["numerator"], 21)
        self.assertEqual(
            result["retries_sensitivity"],
            [{"task": SCOPE_TASK, "attempt": 2, "held_outcome": "fails", "counts_for_k1": False}],
        )

    def test_sensitivity_uses_the_same_baseline(self):
        runs = self._scope_runs("completes", baseline_outcome="fails")
        runs["held_sensitivity"] = [held_run(SCOPE_TASK)]
        result = classify(TASKS, runs, SCOPE_RULES)
        self.assertEqual(result["k1_sensitivity"]["baseline_completes"], 0)
        self.assertEqual(sens_row(result, SCOPE_TASK)["baseline_outcome"], "fails")

    def test_copied_rows_add_no_time(self):
        runs = self._scope_runs("fails")
        for run in runs["held"]:
            run["seconds"] = 10.0
        runs["held_sensitivity"] = [held_run(SCOPE_TASK, seconds=4.0)]
        timing = classify(TASKS, runs, SCOPE_RULES)["timing"]
        self.assertEqual(timing["run_seconds_total"], 24 * 10.0 + 4.0)
        self.assertEqual(timing["runs_with_run_time"], 25)


class TimingTests(unittest.TestCase):
    def test_reset_and_run_time_are_totalled_separately_and_do_not_change_k1(self):
        runs = runs_for()
        for run in runs["held"]:
            run["reset_seconds"] = 2.5
            run["seconds"] = 10.0
        for run in runs["baseline"]:
            run["reset_seconds"] = 1.0
        result = classify(TASKS, runs)
        timing = result["timing"]
        self.assertEqual(timing["reset_seconds_total"], 24 * 2.5 + 24 * 1.0)
        self.assertEqual(timing["run_seconds_total"], 24 * 10.0)
        self.assertEqual(timing["runs_with_reset_time"], 48)
        self.assertEqual(result["k1"]["numerator"], 21)

    def test_timing_is_empty_when_not_recorded(self):
        timing = classify(TASKS, runs_for())["timing"]
        self.assertEqual(timing["reset_seconds_total"], 0)
        self.assertEqual(timing["runs_with_run_time"], 0)

    def test_bad_seconds_are_rejected(self):
        runs = runs_for()
        runs["held"][0]["reset_seconds"] = -1
        with self.assertRaises(ValueError) as ctx:
            classify(TASKS, runs)
        self.assertIn("reset_seconds", str(ctx.exception))


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
        self.assertIn("no baseline run", err.getvalue())


if __name__ == "__main__":
    unittest.main()
