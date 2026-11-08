"""Tests for the injected-write test (records): cases A, B and C against a stand-in server.

The fake server holds one task. Its `updated` is the whole second the last write landed in, as
Vikunja stores it. The release is the real release_unit, so the check and the hook run as they do
in a live run. No browser is started.

Run: python -m unittest discover -s probe/tests -p "test_*.py" -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

import injected_write as iw  # noqa: E402
from release import Held, Token, release_unit  # noqa: E402


class FakeServer:
    def __init__(self, seed_updated="seed-time"):
        self.clock = 100.0
        self.title = "Quarterly report draft"
        self.updated = seed_updated

    def stamp(self):
        return str(int(self.clock))


class FakeOps:
    """The primitives injected_write.run_case calls.

    late_offset: seconds between the page's read and the injector's second write (case B).
    page_unsafe: page requests that reached the server before release (must be 0 to count).
    check_sees_updated: False simulates a check that cannot see the version at all.
    stale_token: True gives the page a token that the server does not hold.
    """

    def __init__(self, server, late_offset=0.6, page_unsafe=0, check_sees_updated=True, stale_token=False):
        self.server = server
        self.late_offset = late_offset
        self.page_unsafe = page_unsafe
        self.check_sees_updated = check_sees_updated
        self.stale_token = stale_token
        self.calls = []
        self.token_read = None
        self.pending_title = None
        self.released = False
        self.injector_before_release = 0

    def reset(self):
        self.calls.append("reset")
        self.server.title = "Quarterly report draft"
        self.server.updated = "seed-time"
        return {"reset_seconds": 0.0, "seed_semantic": {"sha256": "fake"}}

    def start_page(self):
        self.calls.append("start_page")

    def begin_hold(self):
        self.calls.append("begin_hold")

    def wait_for_new_second(self):
        self.calls.append("wait_for_new_second")
        self.server.clock = float(int(self.server.clock) + 1)

    def inject(self, title):
        self.calls.append(f"inject {title}")
        self.server.title = title
        self.server.updated = self.server.stamp()
        if not self.released:
            self.injector_before_release += 1
        return {"title": title, "updated": self.server.updated}

    def sleep(self, seconds):
        self.calls.append(f"sleep {seconds}")
        self.server.clock += seconds

    def open_task(self, on_read=None):
        self.calls.append("open_task")
        self.server.clock += 0.3
        self.token_read = "stale-token" if self.stale_token else self.server.updated
        if on_read is not None:
            self.server.clock += self.late_offset
            on_read()
        return self.token_read

    def rename_on_page(self):
        self.calls.append("rename_on_page")
        self.pending_title = iw.PAGE_TITLE
        self.server.clock += 0.5
        return True

    def release(self, before_send=None):
        self.calls.append("release")
        self.released = True
        token = None if self.token_read is None else Token("page-read:updated", self.token_read)
        held = [Held(seq=1, method="PATCH", url="http://127.0.0.1:8300/api/v2/tasks/4", headers={}, body="", token=token, target=("task", "4"))]

        def current(h):
            return self.server.updated if self.check_sees_updated else h.token.value

        def send(h):
            self.calls.append("send")
            self.server.title = self.pending_title
            self.server.updated = self.server.stamp()
            return 200

        result = release_unit(held, current, send, clock=lambda: self.server.clock, before_send=before_send)
        return {
            "status": result.status,
            "sent": len(result.sent),
            "reasons": [c.reason for c in result.checks if not c.ok],
            "token_used": result.checks[0].expected,
            "current": result.checks[0].current,
        }

    def window_unsafe(self):
        return {"raw": self.page_unsafe + self.injector_before_release, "allowlisted": 0, "injector_before_release": self.injector_before_release}

    def final_title(self):
        self.calls.append("final_title")
        return self.server.title

    def close(self):
        self.calls.append("close")


def factory(**kwargs):
    return lambda attempt: FakeOps(FakeServer(), **kwargs)


class PredictionTests(unittest.TestCase):
    """The predictions are fixed in browser-probe.md before any run. A change here is a change to the test."""

    def test_predictions_match_the_doc(self):
        self.assertEqual(
            iw.PREDICTIONS,
            {
                "A": {"release": "refused", "sent": 0, "read_back": None, "final_title": "Injected A", "hook": False, "goal": True},
                "B": {"release": "released", "sent": 1, "read_back": True, "final_title": "Quarterly report v2", "hook": False, "goal": True},
                "C": {"release": "released", "sent": 1, "read_back": True, "final_title": "Quarterly report v2", "hook": True, "goal": True},
            },
        )

    def test_the_page_title_is_the_r3_rename(self):
        self.assertEqual(iw.PAGE_TITLE, "Quarterly report v2")

    def test_attempts_per_case(self):
        self.assertEqual(iw.ATTEMPTS, {"A": 1, "B": 3, "C": 1})


class UnsafeSplitTests(unittest.TestCase):
    def test_injector_writes_are_taken_out_of_the_page_count(self):
        self.assertEqual(iw.unsafe_split(3, 2), 1)

    def test_no_page_arrivals_is_zero(self):
        self.assertEqual(iw.unsafe_split(2, 2), 0)

    def test_more_injector_writes_than_arrivals_is_an_error(self):
        with self.assertRaises(ValueError):
            iw.unsafe_split(1, 2)


class CaseATests(unittest.TestCase):
    def test_refused_with_nothing_sent_when_the_second_differs(self):
        result = iw.run_case("A", factory())
        counted = result["counted"]
        self.assertTrue(result["matches_prediction"], counted["differences"])
        self.assertEqual(counted["release"]["status"], "refused")
        self.assertEqual(counted["release"]["reasons"], ["version moved"])
        self.assertEqual(counted["final_title"], "Injected A")
        self.assertIsNone(counted["read_back_match"])

    def test_a_check_that_cannot_see_the_version_is_reported_as_a_mismatch(self):
        result = iw.run_case("A", factory(check_sees_updated=False))
        self.assertFalse(result["matches_prediction"])
        self.assertTrue(any("released" in d for d in result["counted"]["differences"]), result["counted"]["differences"])


class CaseBTests(unittest.TestCase):
    def test_same_second_edit_is_not_detected_and_is_overwritten(self):
        result = iw.run_case("B", factory(late_offset=0.6))
        counted = result["counted"]
        self.assertTrue(result["matches_prediction"], counted["differences"])
        self.assertEqual(counted["release"]["status"], "released")
        self.assertEqual(counted["final_title"], "Quarterly report v2")
        self.assertEqual(counted["page_unsafe_before_release"], 0)
        writes = counted["injected"]
        self.assertEqual([w["title"] for w in writes], [iw.INJECTED_B, iw.INJECTED_B_LATE])
        self.assertEqual(writes[0]["updated"], writes[1]["updated"])
        self.assertEqual(writes[0]["updated"], counted["release"]["token_used"])

    def test_a_sample_whose_second_changed_is_recorded_and_not_counted(self):
        offsets = iter([1.1, 0.6, 0.6])
        result = iw.run_case("B", lambda attempt: FakeOps(FakeServer(), late_offset=next(offsets)))
        self.assertEqual(len(result["attempts"]), 2)
        self.assertFalse(result["attempts"][0]["valid"])
        self.assertIn("later second", result["attempts"][0]["invalid_reason"])
        self.assertEqual(result["counted"]["attempt"], 2)
        self.assertTrue(result["matches_prediction"])

    def test_no_valid_sample_in_three_attempts_is_not_a_match(self):
        result = iw.run_case("B", factory(late_offset=1.1))
        self.assertEqual(len(result["attempts"]), 3)
        self.assertIsNone(result["counted"])
        self.assertFalse(result["matches_prediction"])


class CaseCTests(unittest.TestCase):
    def test_the_write_after_the_check_is_overwritten(self):
        ops_list = []
        result = iw.run_case("C", lambda attempt: ops_list.append(FakeOps(FakeServer())) or ops_list[-1])
        counted = result["counted"]
        self.assertTrue(result["matches_prediction"], counted["differences"])
        self.assertTrue(counted["hook_ran"])
        self.assertEqual(counted["release"]["status"], "released")
        self.assertEqual(counted["final_title"], "Quarterly report v2")
        calls = ops_list[0].calls
        self.assertLess(calls.index("release"), calls.index("inject Injected D"))
        self.assertLess(calls.index("inject Injected D"), calls.index("send"))

    def test_the_hook_does_not_run_when_the_check_refuses(self):
        result = iw.run_case("C", factory(stale_token=True))
        self.assertIsNone(result["counted"])
        self.assertFalse(result["matches_prediction"])
        self.assertFalse(result["attempts"][0]["hook_ran"])


class RunCaseTests(unittest.TestCase):
    def test_every_attempt_resets_first_and_closes_last(self):
        ops_list = []
        iw.run_case("A", lambda attempt: ops_list.append(FakeOps(FakeServer())) or ops_list[-1])
        self.assertEqual(ops_list[0].calls[0], "reset")
        self.assertEqual(ops_list[0].calls[-1], "close")

    def test_an_error_in_an_attempt_is_recorded_not_raised(self):
        class Broken(FakeOps):
            def open_task(self, on_read=None):
                raise RuntimeError("page did not load")

        result = iw.run_case("A", lambda attempt: Broken(FakeServer()))
        self.assertIsNone(result["counted"])
        self.assertFalse(result["matches_prediction"])
        self.assertIn("page did not load", result["attempts"][0]["error"])

    def test_the_seed_fingerprint_from_the_reset_is_kept_with_the_attempt(self):
        result = iw.run_case("A", factory())
        self.assertEqual(result["attempts"][0]["reset"]["seed_semantic"], {"sha256": "fake"})


if __name__ == "__main__":
    unittest.main()
