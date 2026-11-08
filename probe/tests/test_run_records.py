"""Unit tests for the records run driver: which server response a held request needs, and the
policy stamp in each result. No browser, no network.

Run: python -m unittest discover -s probe/tests -p "test_*.py" -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

import run_records  # noqa: E402


class KindForTests(unittest.TestCase):
    def test_creates_need_a_server_id(self):
        for path in (
            "/api/v2/projects",
            "/api/v2/labels",
            "/api/v2/projects/1/tasks",
            "/api/v2/projects/1/tasks/bulk",
            "/api/v2/tasks/1/comments",
        ):
            self.assertEqual(run_records.kind_for("POST", path), "server_id", path)

    def test_updates_deletes_and_session_calls_are_other(self):
        self.assertEqual(run_records.kind_for("PATCH", "/api/v2/tasks/1"), "other")
        self.assertEqual(run_records.kind_for("DELETE", "/api/v2/tasks/6"), "other")
        self.assertEqual(run_records.kind_for("POST", "/api/v2/tasks/2/labels"), "other")
        self.assertEqual(run_records.kind_for("POST", "/api/v2/user/token/refresh"), "other")


class PolicyStampTests(unittest.TestCase):
    def test_every_result_carries_the_policy_commit(self):
        self.assertRegex(run_records.POLICY_COMMIT, r"^[0-9a-f]{7,40}$")
        self.assertIsInstance(run_records.POLICY_DIRTY, bool)


class ReleaseCheckMarkTests(unittest.TestCase):
    """Held runs from before the read-compare are superseded. The summary must not report them."""

    def test_runs_with_the_current_release_check_pass(self):
        rows = [{"task": "R3", "release_check": run_records.RELEASE_CHECK}]
        run_records.require_current_release(rows)  # no error

    def test_runs_from_before_the_read_compare_are_refused_by_name(self):
        rows = [
            {"task": "R1", "release_check": run_records.RELEASE_CHECK},
            {"task": "R3"},
            {"task": "R4", "release_check": "none"},
        ]
        with self.assertRaises(ValueError) as caught:
            run_records.require_current_release(rows)
        self.assertIn("R3, R4", str(caught.exception))
        self.assertNotIn("R1", str(caught.exception))

    def test_runs_from_the_read_compare_without_the_create_guard_are_superseded(self):
        """The first read-compare marker did not check creates. Those held runs are superseded too."""
        rows = [{"task": "R5", "release_check": "page-read-updated+fresh-read"}]
        with self.assertRaisesRegex(ValueError, "R5"):
            run_records.require_current_release(rows)


class SettleOutcomeTests(unittest.TestCase):
    """completes needs a released unit and a matching read-back. The read-back alone is not enough."""

    def test_completes_when_released_and_read_back_matches(self):
        self.assertEqual(run_records.settle_held_outcome("completes", "released", True), ("completes", None))

    def test_read_back_mismatch_after_release_fails(self):
        outcome, reason = run_records.settle_held_outcome("completes", "released", False)
        self.assertEqual(outcome, "fails")
        self.assertEqual(reason, "read-back mismatch after release")

    def test_a_refused_unit_fails_even_when_the_read_back_matches(self):
        """A duplicate already present makes the read-back match, but the unit did not complete."""
        outcome, reason = run_records.settle_held_outcome("completes", "refused", True)
        self.assertEqual(outcome, "fails")
        self.assertIn("refused", reason)

    def test_a_partial_unit_fails_even_when_the_read_back_matches(self):
        self.assertEqual(run_records.settle_held_outcome("completes", "partial", True)[0], "fails")

    def test_other_candidates_are_not_changed(self):
        self.assertEqual(run_records.settle_held_outcome("needs_response", "refused", False), ("needs_response", None))
        self.assertEqual(run_records.settle_held_outcome("fails", "released", True), ("fails", None))


class PhaseFileTests(unittest.TestCase):
    def test_the_amended_phase_has_its_own_file_and_the_registered_one_keeps_its_own(self):
        self.assertEqual(run_records.phase_file("held").name, "held.json")
        self.assertEqual(run_records.phase_file("held-amended").name, "held_amended.json")
        self.assertEqual(run_records.phase_file("baseline").name, "baseline.json")


class AmendmentGuardTests(unittest.TestCase):
    def test_an_applied_amendment_is_accepted(self):
        run_records.require_applied({"id": "A1", "applied": True, "reasons": []})

    def test_a_void_amendment_is_refused_with_its_reasons(self):
        with self.assertRaisesRegex(ValueError, "not applied.*refresh returned 401"):
            run_records.require_applied({"id": "A1", "applied": False, "reasons": ["refresh returned 401"]})

    def test_a_missing_amendment_is_refused(self):
        with self.assertRaises(ValueError):
            run_records.require_applied(None)


class CreateCountTests(unittest.TestCase):
    def test_only_held_requests_that_add_an_object_are_counted(self):
        from release import Held

        create = Held(seq=1, method="POST", url="http://127.0.0.1:8300/api/v2/projects", headers={}, body="")
        create.create = object()
        update = Held(seq=2, method="PATCH", url="http://127.0.0.1:8300/api/v2/tasks/6", headers={}, body="")
        self.assertEqual(run_records.creates_held_count([create, update]), 1)
        self.assertEqual(run_records.creates_held_count([]), 0)


if __name__ == "__main__":
    unittest.main()
