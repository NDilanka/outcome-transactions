"""Classify browser probe runs and compute K1.

Input: the frozen task list (probe/tasks.json) and a runs file with these lists:

  "held":             one measured held run per task (attempt 1), plus any
                      retries (attempt 2 and up). Primary GET policy.
  "held_sensitivity": the sensitivity GET policy, for scope tasks only. The
                      scope is the set of tasks whose primary attempt-1 run held
                      a GET that the sensitivity policy passes. Each scope task
                      needs an attempt-1 run here, and no other task may have
                      one. The policies differ only on those GETs, so every
                      other task copies its primary row (copied_from_primary).
  "baseline":         one run per task with holds off. Shared by both policies.

Every held run lists "gets_held": the GET rules (probe/harness/policy.py) that
held a request in that run. The scope depends on it.

Each run may carry "reset_seconds" (time spent resetting the app to seed state)
and "seconds" (time for the run). Both are totalled in "timing". Neither
affects K1. Copied rows add no time.

A held run counts for K1 only when every condition holds:

  - held_outcome is "completes"
  - faked_response is false (the harness did not synthesise a server answer)
  - native_draft_used is false (the saved draft or quote was not used)
  - the task is not native_draft_required
  - unsafe_before_release is 0 (no unsafe request reached the server early)
  - read_back_match is true

Each row lists every condition that failed, so no task drops out silently.
K1 triggers when the numerator is below half the denominator (12 of 24).

Run: python probe/harness/classify.py --runs <runs.json> [--tasks probe/tasks.json]
"""

import argparse
import json
import sys
from pathlib import Path

from policy import GET_RULES

DEFAULT_TASKS = Path(__file__).resolve().parent.parent / "tasks.json"

HELD_OUTCOMES = ("completes", "needs_response", "fails")
BASELINE_OUTCOMES = ("completes", "fails")
RESPONSE_KINDS = (
    "server_id",
    "csrf_rotation",
    "validation_result",
    "payment_redirect",
    "held_get_content",
    "other",
)
TIMED_LISTS = ("held", "held_sensitivity", "baseline")

# GET rule name -> the app it belongs to.
RULE_APP = {rule.name: rule.app for rule in GET_RULES}
# Rules the sensitivity policy passes (set in policy.GET_RULES after measurement).
SENSITIVITY_RULES = frozenset(rule.name for rule in GET_RULES if rule.sensitivity_pass)


def _fail(where, message):
    raise ValueError(f"{where}: {message}")


def _is_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_seconds(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def load_tasks(path=DEFAULT_TASKS):
    """Return the frozen tasks keyed by id, in list order."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = {}
    for task in data["tasks"]:
        task_id = task["id"]
        if task_id in tasks:
            raise ValueError(f"duplicate task id {task_id} in task list")
        for key in ("native_draft_available", "native_draft_required"):
            if task[key] not in ("yes", "no"):
                _fail(task_id, f"{key} must be 'yes' or 'no'")
        tasks[task_id] = task
    return tasks


def _check_held(run, where):
    outcome = run.get("held_outcome")
    if outcome not in HELD_OUTCOMES:
        _fail(where, f"held_outcome must be one of {HELD_OUTCOMES}")
    responses = run.get("needs_response", [])
    if not isinstance(responses, list) or any(r not in RESPONSE_KINDS for r in responses):
        _fail(where, f"needs_response must list kinds from {RESPONSE_KINDS}")
    if (outcome == "needs_response") != bool(responses):
        _fail(where, "needs_response lists kinds only when held_outcome is needs_response")
    if outcome == "fails" and not run.get("fail_reason"):
        _fail(where, "a fails run needs a fail_reason")
    for key in ("faked_response", "native_draft_used"):
        if not isinstance(run.get(key), bool):
            _fail(where, f"{key} must be true or false")
    if not _is_count(run.get("unsafe_before_release")):
        _fail(where, "unsafe_before_release must be a count of 0 or more")
    read_back = run.get("read_back_match")
    if read_back is not None and not isinstance(read_back, bool):
        _fail(where, "read_back_match must be true, false or null")


def _check_gets(run, task, where, sensitivity_rules):
    """Check the GET rules a held run records. sensitivity_rules is set for sensitivity runs only."""
    gets = run.get("gets_held")
    if not isinstance(gets, list) or any(not isinstance(g, str) for g in gets) or len(set(gets)) != len(gets):
        _fail(where, "gets_held must list each GET rule name once")
    for name in gets:
        if name not in RULE_APP:
            _fail(where, f"gets_held has unknown GET rule {name!r}")
        if RULE_APP[name] != task["app"]:
            _fail(where, f"GET rule {name} belongs to {RULE_APP[name]}, not {task['app']}")
    if sensitivity_rules is not None and set(gets) & sensitivity_rules:
        _fail(where, "a sensitivity run held a GET that the sensitivity policy passes")


def _check_baseline(run, where):
    if run.get("outcome") not in BASELINE_OUTCOMES:
        _fail(where, f"outcome must be one of {BASELINE_OUTCOMES}")
    if run["outcome"] == "fails" and not run.get("fail_reason"):
        _fail(where, "a fails baseline needs a fail_reason")


def _index_held(runs, tasks, sensitivity_rules=None):
    by_task = {}
    for run in runs:
        task_id = run.get("task")
        if task_id not in tasks:
            raise ValueError(f"held run for unknown task {task_id!r}")
        attempt = run.get("attempt", 1)
        if not _is_count(attempt) or attempt < 1:
            _fail(task_id, "attempt must be 1 or more")
        where = f"{task_id} attempt {attempt}"
        _check_held(run, where)
        _check_gets(run, tasks[task_id], where, sensitivity_rules)
        attempts = by_task.setdefault(task_id, {})
        if attempt in attempts:
            _fail(where, "duplicate attempt")
        attempts[attempt] = run
    return by_task


def _index_baseline(runs, tasks):
    by_task = {}
    for run in runs:
        task_id = run.get("task")
        if task_id not in tasks:
            raise ValueError(f"baseline run for unknown task {task_id!r}")
        _check_baseline(run, f"{task_id} baseline")
        if task_id in by_task:
            _fail(task_id, "duplicate baseline run")
        by_task[task_id] = run
    return by_task


def _row(task, run, base):
    draft_required = task["native_draft_required"] == "yes"
    exclusions = []
    if run["held_outcome"] != "completes":
        exclusions.append(f"held_outcome is {run['held_outcome']}")
    if run["faked_response"]:
        exclusions.append("faked_response")
    if run["native_draft_used"]:
        exclusions.append("native_draft_used")
    if draft_required:
        exclusions.append("native_draft_required")
    if run["unsafe_before_release"] > 0:
        exclusions.append("hold_leak")
    read_back = run.get("read_back_match")
    if read_back is None:
        exclusions.append("read_back_missing")
    elif not read_back:
        exclusions.append("read_back_mismatch")
    return {
        "task": task["id"],
        "app": task["app"],
        "native_draft_available": task["native_draft_available"] == "yes",
        "native_draft_required": draft_required,
        "held_outcome": run["held_outcome"],
        "needs_response": run.get("needs_response", []),
        "fail_reason": run.get("fail_reason"),
        "gets_held": list(run["gets_held"]),
        "faked_response": run["faked_response"],
        "native_draft_used": run["native_draft_used"],
        "unsafe_before_release": run["unsafe_before_release"],
        "read_back_match": read_back,
        "baseline_outcome": base["outcome"],
        "counts_for_k1": not exclusions,
        "exclusions": exclusions,
    }


def _k1(rows, policy, scope=None):
    total = len(rows)
    counted = sum(1 for r in rows if r["counts_for_k1"])
    apps = sorted({r["app"] for r in rows})
    result = {
        "policy": policy,
        "rule": "K1 triggers when the numerator is below half the denominator",
        "denominator": total,
        "numerator": counted,
        "threshold": total / 2,
        "k1_triggered": counted < total / 2,
        "max_possible": sum(1 for r in rows if not r["native_draft_required"]),
        "counted_by_app": {a: sum(1 for r in rows if r["app"] == a and r["counts_for_k1"]) for a in apps},
        "baseline_completes": sum(1 for r in rows if r["baseline_outcome"] == "completes"),
    }
    if scope is not None:
        result["sensitivity_run_tasks"] = sorted(scope)
        result["copied_from_primary"] = sorted(r["task"] for r in rows if r.get("copied_from_primary"))
    return result


def _require_first_attempts(held, tasks, policy):
    missing = [t for t in tasks if 1 not in held.get(t, {})]
    if missing:
        raise ValueError(f"no measured held run (attempt 1) for {policy} policy: {', '.join(missing)}")


def sensitivity_scope(held, sensitivity_rules):
    """Tasks whose primary attempt-1 run held a GET that the sensitivity policy passes."""
    return {t for t, attempts in held.items() if set(attempts[1]["gets_held"]) & sensitivity_rules}


def _check_sensitivity_runs(sens_held, scope):
    extra = sorted(t for t in sens_held if t not in scope)
    if extra:
        raise ValueError(
            "held_sensitivity has runs for tasks that touch no sensitivity GET "
            f"(their primary row is copied): {', '.join(extra)}"
        )
    missing = sorted(t for t in scope if 1 not in sens_held.get(t, {}))
    if missing:
        raise ValueError(f"no sensitivity run (attempt 1) for tasks that touch a sensitivity GET: {', '.join(missing)}")


def _score(tasks, held, baseline, policy, scope=None, primary_rows=None):
    """Return (rows, retries, k1) for one held-run policy.

    With scope set (the sensitivity policy), a task outside scope copies its
    primary row. Only scope tasks have sensitivity runs, so only they can have
    retries.
    """
    rows, retries = [], []
    for task_id, task in tasks.items():
        if scope is not None and task_id not in scope:
            rows.append({**primary_rows[task_id], "copied_from_primary": True})
            continue
        attempts = held[task_id]
        for attempt in sorted(a for a in attempts if a > 1):
            retries.append(
                {
                    "task": task_id,
                    "attempt": attempt,
                    "held_outcome": attempts[attempt]["held_outcome"],
                    "counts_for_k1": False,
                }
            )
        row = _row(task, attempts[1], baseline[task_id])
        if scope is not None:
            row["copied_from_primary"] = False
        rows.append(row)
    return rows, retries, _k1(rows, policy, scope)


def _timing(runs):
    totals = {"reset_seconds_total": 0.0, "run_seconds_total": 0.0, "runs_with_reset_time": 0, "runs_with_run_time": 0}
    for key in TIMED_LISTS:
        for run in runs.get(key, []):
            where = f"{key} run {run.get('task')}"
            if "reset_seconds" in run:
                if not _is_seconds(run["reset_seconds"]):
                    _fail(where, "reset_seconds must be a number of 0 or more")
                totals["reset_seconds_total"] += run["reset_seconds"]
                totals["runs_with_reset_time"] += 1
            if "seconds" in run:
                if not _is_seconds(run["seconds"]):
                    _fail(where, "seconds must be a number of 0 or more")
                totals["run_seconds_total"] += run["seconds"]
                totals["runs_with_run_time"] += 1
    totals["reset_seconds_total"] = round(totals["reset_seconds_total"], 1)
    totals["run_seconds_total"] = round(totals["run_seconds_total"], 1)
    return totals


def classify(tasks, runs, sensitivity_rules=SENSITIVITY_RULES):
    """Return the K1 result for the primary policy and the sensitivity policy.

    sensitivity_rules is the set of GET rule names the sensitivity policy passes.
    """
    sensitivity_rules = frozenset(sensitivity_rules)
    unknown = sorted(sensitivity_rules - set(RULE_APP))
    if unknown:
        raise ValueError(f"unknown sensitivity rules: {', '.join(unknown)}")

    baseline = _index_baseline(runs.get("baseline", []), tasks)
    missing_base = [t for t in tasks if t not in baseline]
    if missing_base:
        raise ValueError(f"no baseline run for: {', '.join(missing_base)}")

    held = _index_held(runs.get("held", []), tasks)
    _require_first_attempts(held, tasks, "primary")
    primary_rows, primary_retries, primary_k1 = _score(tasks, held, baseline, "primary")

    scope = sensitivity_scope(held, sensitivity_rules)
    sens_held = _index_held(runs.get("held_sensitivity", []), tasks, sensitivity_rules)
    _check_sensitivity_runs(sens_held, scope)
    primary_by_task = {r["task"]: r for r in primary_rows}
    sens_rows, sens_retries, sens_k1 = _score(
        tasks, sens_held, baseline, "sensitivity", scope=scope, primary_rows=primary_by_task
    )

    return {
        "k1": primary_k1,
        "tasks": primary_rows,
        "retries": primary_retries,
        "k1_sensitivity": sens_k1,
        "tasks_sensitivity": sens_rows,
        "retries_sensitivity": sens_retries,
        "timing": _timing(runs),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Classify probe runs and compute K1.")
    parser.add_argument("--runs", required=True, help="JSON file with 'held', 'held_sensitivity' and 'baseline' lists")
    parser.add_argument("--tasks", default=str(DEFAULT_TASKS), help="frozen task list")
    args = parser.parse_args(argv)
    runs = json.loads(Path(args.runs).read_text(encoding="utf-8"))
    try:
        result = classify(load_tasks(args.tasks), runs)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
