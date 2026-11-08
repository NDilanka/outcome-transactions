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


if __name__ == "__main__":
    unittest.main()
