"""Amendment A1: the one allowlisted refresh POST, its two gates, and the arrival split.

No browser, no network. The measurement runs against fake ops here; the live
run comes later, after the orchestrator's go-ahead.

Run: python -m unittest discover -s probe/tests -p "test_*.py" -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

import amendment  # noqa: E402
from intercept import HoldWorkspace  # noqa: E402
from policy import AMENDED_PASS_REASON, PRIMARY, SENSITIVITY, decide, decide_detail, GET_RULES  # noqa: E402

REFRESH = "http://127.0.0.1:8300/api/v2/user/token/refresh"
TASK6 = "http://127.0.0.1:8300/api/v2/tasks/6"
PAYMENT_RETURN = "http://127.0.0.1:8100/checkout/return?order=1&intent=pi_x"


class Route:
    def __init__(self):
        self.aborted = None
        self.continued = False
        self.request = self

    def abort(self, reason):
        self.aborted = reason

    def continue_(self, **_):
        self.continued = True

    def response(self):
        return None


class Request:
    def __init__(self, method, url, post_data=""):
        self.method = method
        self.url = url
        self.post_data = post_data

    def all_headers(self):
        return {}


class AllowlistTests(unittest.TestCase):
    def test_exactly_one_entry_and_it_is_the_records_refresh_post(self):
        self.assertEqual(
            amendment.ALLOWLIST,
            (amendment.Allowed(method="POST", app="records", path="/api/v2/user/token/refresh"),),
        )

    def test_the_refresh_post_to_records_is_allowed(self):
        self.assertTrue(amendment.allows("POST", REFRESH))
        self.assertTrue(amendment.allows("post", REFRESH))

    def test_no_pattern_no_other_method_no_other_path_no_other_app(self):
        self.assertFalse(amendment.allows("PUT", REFRESH))
        self.assertFalse(amendment.allows("GET", REFRESH))
        self.assertFalse(amendment.allows("POST", REFRESH + "/extra"))
        self.assertFalse(amendment.allows("POST", "http://127.0.0.1:8300/api/v2/user/token"))
        self.assertFalse(amendment.allows("POST", REFRESH.replace("8300", "8100")))
        self.assertFalse(amendment.allows("POST", TASK6))

    def test_a_query_string_is_not_allowed(self):
        self.assertFalse(amendment.allows("POST", REFRESH + "?x=1"))


class PolicyHookTests(unittest.TestCase):
    def test_registered_policy_still_holds_the_refresh_post(self):
        self.assertEqual(decide("POST", REFRESH, PRIMARY)[0], "hold")
        self.assertEqual(decide("POST", REFRESH, SENSITIVITY)[0], "hold")

    def test_amended_policy_passes_exactly_the_allowlisted_post(self):
        verdict, reason, rule = decide_detail("POST", REFRESH, PRIMARY, allowed=amendment.allows)
        self.assertEqual((verdict, reason, rule), ("pass", AMENDED_PASS_REASON, None))

    def test_amended_policy_still_holds_other_writes(self):
        self.assertEqual(decide("PATCH", TASK6, PRIMARY, allowed=amendment.allows)[0], "hold")
        self.assertEqual(decide("POST", REFRESH + "/extra", PRIMARY, allowed=amendment.allows)[0], "hold")

    def test_amended_policy_never_passes_the_payment_return(self):
        for mode in (PRIMARY, SENSITIVITY):
            self.assertEqual(decide("GET", PAYMENT_RETURN, mode, allowed=amendment.allows)[0], "hold", mode)

    def test_gets_rules_are_unchanged_by_the_amendment(self):
        self.assertEqual([r.name for r in GET_RULES], ["webmail-open-message", "webmail-reply-compose", "checkout-payment-return"])


class VerdictTests(unittest.TestCase):
    """The amendment applies only when both live measurements pass."""

    def clean_state(self, **changes):
        state = {"status": 200, "changed_tables": ["sessions"], "real_user": {"before": 200, "after": 200}}
        state.update(changes)
        return state

    def test_applies_when_only_sessions_change_and_the_real_user_survives(self):
        v = amendment.verdict(self.clean_state())
        self.assertTrue(v.applied)
        self.assertEqual(v.reasons, [])

    def test_applies_when_nothing_changes(self):
        self.assertTrue(amendment.verdict(self.clean_state(changed_tables=[])).applied)

    def test_void_when_the_refresh_changes_a_business_table(self):
        v = amendment.verdict(self.clean_state(changed_tables=["sessions", "tasks"]))
        self.assertFalse(v.applied)
        self.assertIn("tasks", " ".join(v.reasons))

    def test_void_when_the_token_tables_change_because_they_are_not_excluded(self):
        v = amendment.verdict(self.clean_state(changed_tables=["sessions", "api_tokens"]))
        self.assertFalse(v.applied)
        self.assertIn("api_tokens", " ".join(v.reasons))

    def test_void_when_the_refresh_is_not_a_success(self):
        for status in (401, 403, 500, None):
            v = amendment.verdict(self.clean_state(status=status))
            self.assertFalse(v.applied, status)

    def test_void_when_the_real_user_is_signed_out_by_the_refresh(self):
        v = amendment.verdict(self.clean_state(real_user={"before": 200, "after": 401}))
        self.assertFalse(v.applied)
        self.assertIn("real-user session 401", " ".join(v.reasons))

    def test_void_when_the_real_user_was_not_valid_before_the_refresh(self):
        v = amendment.verdict(self.clean_state(real_user={"before": 401, "after": 401}))
        self.assertFalse(v.applied)

    def test_void_when_a_measurement_is_missing(self):
        self.assertFalse(amendment.verdict(None).applied)
        self.assertFalse(amendment.verdict({"status": 200, "changed_tables": []}).applied)


class FakeOps:
    """A toy app: tables are dicts, the refresh writes to sessions, and a real-user session can be signed out."""

    def __init__(self, refresh_writes=("sessions",), refresh_status=200, signs_out_real=False, real_valid=True):
        self.tables = {"sessions": {"n": 1}, "tasks": {"6": "Buy milk"}, "api_tokens": {}}
        self.refresh_writes = refresh_writes
        self.refresh_status = refresh_status
        self.signs_out_real = signs_out_real
        self.real_valid = real_valid
        self.calls = []
        self.signed_out = False

    def reset(self):
        self.calls.append("reset")
        self.tables = {"sessions": {"n": 1}, "tasks": {"6": "Buy milk"}, "api_tokens": {}}
        self.signed_out = False

    def login(self, name):
        self.calls.append(f"login {name}")

    def user_status(self, name):
        self.calls.append(f"user {name}")
        if name == "real":
            return 200 if (self.real_valid and not self.signed_out) else 401
        return 200

    def refresh(self, name):
        self.calls.append(f"refresh {name}")
        for table in self.refresh_writes:
            self.tables[table]["n"] = self.tables[table].get("n", 0) + 1
        if self.signs_out_real:
            self.signed_out = True
        return self.refresh_status

    def snapshot(self):
        return {name: dict(rows) for name, rows in self.tables.items()}


class MeasureTests(unittest.TestCase):
    def test_sessions_only_refresh_with_real_user_intact_applies(self):
        ops = FakeOps()
        result = amendment.measure(ops)
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["changed_tables"], ["sessions"])
        self.assertEqual(result["real_user"], {"before": 200, "after": 200})
        self.assertTrue(result["verdict"]["applied"])

    def test_the_real_user_is_checked_before_the_snapshot_and_before_the_refresh(self):
        ops = FakeOps()
        amendment.measure(ops)
        order = ops.calls
        self.assertLess(order.index("user real"), order.index("refresh workspace"))
        self.assertEqual(order[0], "reset")

    def test_a_refresh_that_writes_tasks_is_void(self):
        result = amendment.measure(FakeOps(refresh_writes=("sessions", "tasks")))
        self.assertFalse(result["verdict"]["applied"])
        self.assertIn("tasks", result["changed_tables"])

    def test_a_refresh_that_signs_out_the_real_user_is_void(self):
        result = amendment.measure(FakeOps(signs_out_real=True))
        self.assertFalse(result["verdict"]["applied"])
        self.assertEqual(result["real_user"]["after"], 401)

    def test_an_invalid_real_user_before_the_refresh_is_void(self):
        result = amendment.measure(FakeOps(real_valid=False))
        self.assertFalse(result["verdict"]["applied"])


class ArrivalSplitTests(unittest.TestCase):
    REFRESH_ARRIVAL = {"event": "arrival", "method": "POST", "path": "/api/v2/user/token/refresh", "query_keys": [], "unsafe": True}
    TASK_ARRIVAL = {"event": "arrival", "method": "PATCH", "path": "/api/v2/tasks/6", "query_keys": [], "unsafe": True}

    def test_amended_run_excludes_only_the_allowlisted_arrival_from_unsafe(self):
        self.assertEqual(amendment.split_arrivals([self.REFRESH_ARRIVAL, self.TASK_ARRIVAL], amended=True), (1, 1))

    def test_registered_run_counts_every_unsafe_arrival(self):
        self.assertEqual(amendment.split_arrivals([self.REFRESH_ARRIVAL, self.TASK_ARRIVAL], amended=False), (2, 0))

    def test_a_refresh_arrival_with_a_query_is_still_unsafe(self):
        arrival = dict(self.REFRESH_ARRIVAL, query_keys=["x"])
        self.assertEqual(amendment.split_arrivals([arrival], amended=True), (1, 0))

    def test_safe_arrivals_are_neither_counted_nor_allowlisted(self):
        safe = {"event": "arrival", "method": "GET", "path": "/api/v2/tasks/6", "query_keys": [], "unsafe": False}
        self.assertEqual(amendment.split_arrivals([safe], amended=True), (0, 0))


class WorkspaceAmendmentTests(unittest.TestCase):
    def test_registered_workspace_holds_the_refresh_post(self):
        ws = HoldWorkspace(PRIMARY)
        route = Route()
        ws._on_route(route, Request("POST", REFRESH))
        self.assertEqual(len(ws.held), 1)
        self.assertFalse(route.continued)

    def test_amended_workspace_passes_the_refresh_post_and_records_it(self):
        ws = HoldWorkspace(PRIMARY, allowed=amendment.allows)
        route = Route()
        ws._on_route(route, Request("POST", REFRESH))
        self.assertTrue(route.continued)
        self.assertEqual(ws.held, [])
        self.assertEqual(ws.amended_passes, ["/api/v2/user/token/refresh"])

    def test_amended_workspace_still_holds_a_task_write(self):
        ws = HoldWorkspace(PRIMARY, allowed=amendment.allows)
        route = Route()
        ws._on_route(route, Request("PATCH", TASK6, '{"title": "x"}'))
        self.assertFalse(route.continued)
        self.assertEqual(len(ws.held), 1)
        self.assertEqual(ws.amended_passes, [])


if __name__ == "__main__":
    unittest.main()
