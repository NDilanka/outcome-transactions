"""Classify browser probe runs and compute K1.

Input: the frozen task list (probe/tasks.json) and a runs file with two lists:

  "held":     one measured run per task (attempt 1), plus any retries
              (attempt 2 and up). Retries are listed in the output. They never
              change the numerator.
  "baseline": one run per task with holds off.

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


def _fail(where, message):
    raise ValueError(f"{where}: {message}")


def _is_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


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


def _check_baseline(run, where):
    if run.get("outcome") not in BASELINE_OUTCOMES:
        _fail(where, f"outcome must be one of {BASELINE_OUTCOMES}")
    if run["outcome"] == "fails" and not run.get("fail_reason"):
        _fail(where, "a fails baseline needs a fail_reason")


def _index_held(runs, tasks):
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
        "faked_response": run["faked_response"],
        "native_draft_used": run["native_draft_used"],
        "unsafe_before_release": run["unsafe_before_release"],
        "read_back_match": read_back,
        "baseline_outcome": base["outcome"],
        "counts_for_k1": not exclusions,
        "exclusions": exclusions,
    }


def _k1(rows):
    total = len(rows)
    counted = sum(1 for r in rows if r["counts_for_k1"])
    apps = sorted({r["app"] for r in rows})
    return {
        "rule": "K1 triggers when the numerator is below half the denominator",
        "denominator": total,
        "numerator": counted,
        "threshold": total / 2,
        "k1_triggered": counted < total / 2,
        "max_possible": sum(1 for r in rows if not r["native_draft_required"]),
        "counted_by_app": {a: sum(1 for r in rows if r["app"] == a and r["counts_for_k1"]) for a in apps},
        "baseline_completes": sum(1 for r in rows if r["baseline_outcome"] == "completes"),
    }


def classify(tasks, runs):
    """Return {"k1", "tasks", "retries"} for the given task list and runs."""
    held = _index_held(runs.get("held", []), tasks)
    baseline = _index_baseline(runs.get("baseline", []), tasks)

    missing_held = [t for t in tasks if 1 not in held.get(t, {})]
    if missing_held:
        raise ValueError(f"no measured held run (attempt 1) for: {', '.join(missing_held)}")
    missing_base = [t for t in tasks if t not in baseline]
    if missing_base:
        raise ValueError(f"no baseline run for: {', '.join(missing_base)}")

    rows, retries = [], []
    for task_id, task in tasks.items():
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
        rows.append(_row(task, attempts[1], baseline[task_id]))
    return {"k1": _k1(rows), "tasks": rows, "retries": retries}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Classify probe runs and compute K1.")
    parser.add_argument("--runs", required=True, help="JSON file with 'held' and 'baseline' lists")
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
