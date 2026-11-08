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


class HeldPhaseTests(unittest.TestCase):
    """Held phase completes: the page reached its goal with everything held, before release.

    It is a second number beside K1. It does not change K1: a task whose release
    was refused still fails K1 when its read-back does not match.
    """

    def test_row_records_the_held_phase_separately_from_k1(self):
        run = held_run("R3", "fails", goal_during_hold=True, read_back_match=False, fail_reason="release refused: no precondition available")
        r = row(classify(TASKS, runs_for({"R3": run})), "R3")
        self.assertTrue(r["held_phase_completes"])
        self.assertFalse(r["counts_for_k1"])
        self.assertIn("held_outcome is fails", r["exclusions"])

    def test_a_task_whose_goal_never_showed_is_not_a_held_phase_completion(self):
        r = row(classify(TASKS, runs_for({"R2": held_run("R2", "needs_response")})), "R2")
        self.assertFalse(r["held_phase_completes"])

    def test_k1_reports_the_held_phase_count_beside_the_numerator(self):
        overrides = {
            "R1": held_run("R1", goal_during_hold=True),
            "R2": held_run("R2", "fails", goal_during_hold=True, read_back_match=False),
        }
        k1 = classify(TASKS, runs_for(overrides))["k1"]
        self.assertEqual(k1["held_phase_completes"], 2)
        self.assertEqual(k1["numerator"], 21 - 1)  # R2 fails K1; R1 still counts


RECORDS = [t for t in TASKS if TASKS[t]["app"] == "records"]
APPLIED = {"id": "A1", "applied": True, "reasons": []}


def amended_row(result, task_id):
    return next(r for r in result["tasks_amended"] if r["task"] == task_id)


def with_amended(runs, amended_runs, amendment=APPLIED):
    out = dict(runs)
    out["held_amended"] = amended_runs
    if amendment is not None:
        out["amendment"] = amendment
    return out


class AmendedTests(unittest.TestCase):
    """Amendment A1 is a labelled second policy, reported beside the registered one. It needs an applied amendment."""

    def test_without_amended_runs_there_are_no_amended_numbers(self):
        result = classify(TASKS, runs_for())
        self.assertNotIn("k1_amended", result)

    def test_registered_and_amended_are_reported_side_by_side(self):
        runs = runs_for({t: held_run(t, "needs_response") for t in RECORDS})
        result = classify(TASKS, with_amended(runs, [held_run(t) for t in TASKS]))
        self.assertEqual(result["k1"]["policy"], "primary")
        self.assertEqual(result["k1"]["numerator"], 21 - len(RECORDS))
        self.assertEqual(result["k1_amended"]["policy"], "amended")
        self.assertEqual(result["k1_amended"]["numerator"], 21)
        self.assertEqual(result["amendment"]["id"], "A1")

    def test_amended_runs_are_refused_unless_the_amendment_applied(self):
        runs = with_amended(runs_for(), [held_run(t) for t in TASKS], amendment={"id": "A1", "applied": False, "reasons": ["refresh returned 401"]})
        with self.assertRaisesRegex(ValueError, "amendment A1 is not applied.*refresh returned 401"):
            classify(TASKS, runs)

    def test_amended_runs_without_an_amendment_record_are_refused(self):
        runs = with_amended(runs_for(), [held_run(t) for t in TASKS], amendment=None)
        with self.assertRaisesRegex(ValueError, "amendment record"):
            classify(TASKS, runs)

    def test_amended_runs_must_cover_every_task(self):
        runs = with_amended(runs_for(), [held_run(t) for t in TASKS if t != "R1"])
        with self.assertRaisesRegex(ValueError, "no measured held run .*amended.*R1"):
            classify(TASKS, runs)

    def test_allowlisted_arrivals_are_reported_and_do_not_change_k1(self):
        amended = [held_run(t, allowlisted_arrivals_before_release=1) for t in TASKS]
        result = classify(TASKS, with_amended(runs_for(), amended))
        self.assertEqual(amended_row(result, "R1")["allowlisted_arrivals_before_release"], 1)
        self.assertTrue(amended_row(result, "R1")["counts_for_k1"])
        self.assertEqual(result["k1_amended"]["numerator"], 21)

    def test_an_unsafe_arrival_in_an_amended_run_still_refuses_the_task(self):
        amended = [held_run(t) for t in TASKS]
        amended[0] = held_run("R1", unsafe_before_release=1)
        result = classify(TASKS, with_amended(runs_for(), amended))
        self.assertIn("hold_leak", amended_row(result, "R1")["exclusions"])

    def test_timing_of_amended_runs_is_totalled(self):
        amended = [held_run(t, seconds=2.0, reset_seconds=1.0) for t in TASKS]
        timing = classify(TASKS, with_amended(runs_for(), amended))["timing"]
        self.assertEqual(timing["run_seconds_total"], 2.0 * len(TASKS))

    def test_bad_allowlisted_count_is_an_error(self):
        runs = with_amended(runs_for(), [held_run("R1", allowlisted_arrivals_before_release=-1)] + [held_run(t) for t in TASKS if t != "R1"])
        with self.assertRaisesRegex(ValueError, "allowlisted_arrivals_before_release must be a count"):
            classify(TASKS, runs)


CREATING = ("R1", "R5", "R6")


class CreateCategoryTests(unittest.TestCase):
    """A create adds an object. It is its own category, with its own count."""

    def test_a_task_that_holds_a_create_is_in_the_create_category(self):
        r = row(classify(TASKS, runs_for({"R1": held_run("R1", creates_held=1)})), "R1")
        self.assertEqual(r["category"], "create")

    def test_other_tasks_are_writes(self):
        self.assertEqual(row(classify(TASKS, runs_for()), "R2")["category"], "write")

    def test_the_create_summary_counts_only_creates(self):
        overrides = {
            "R1": held_run("R1", creates_held=1),
            "R5": held_run("R5", "needs_response", creates_held=1),
            "R6": held_run("R6", creates_held=1),
        }
        creates = classify(TASKS, runs_for(overrides))["creates"]
        self.assertEqual(creates["tasks"], sorted(CREATING))
        self.assertEqual((creates["denominator"], creates["numerator"]), (3, 2))

    def test_creates_held_must_be_a_count(self):
        with self.assertRaisesRegex(ValueError, "creates_held must be a count"):
            classify(TASKS, runs_for({"R1": held_run("R1", creates_held=-1)}))

    def test_amended_creates_are_summarised_beside_the_registered_ones(self):
        amended = [held_run(t, creates_held=1 if t in CREATING else 0) for t in TASKS]
        result = classify(TASKS, with_amended(runs_for(), amended))
        self.assertEqual(result["creates_amended"]["denominator"], 3)
        self.assertEqual(result["creates_amended"]["numerator"], 3)


class ReleaseStatusTests(unittest.TestCase):
    """A completed task whose unit was not fully released does not complete. The read-back alone is not enough."""

    def test_a_refused_or_partial_release_excludes_the_task(self):
        for status in ("refused", "partial"):
            r = row(classify(TASKS, runs_for({"R3": held_run("R3", release_status=status)})), "R3")
            self.assertFalse(r["counts_for_k1"], status)
            self.assertIn("release_not_released", r["exclusions"], status)

    def test_a_released_unit_counts(self):
        r = row(classify(TASKS, runs_for({"R3": held_run("R3", release_status="released")})), "R3")
        self.assertTrue(r["counts_for_k1"])

    def test_an_unknown_release_status_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "release_status"):
            classify(TASKS, runs_for({"R3": held_run("R3", release_status="sent")}))


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
