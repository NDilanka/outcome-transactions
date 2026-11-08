"""Unit tests for the hold policy and the release logic. No browser, no network.

Run: python -m unittest discover -s probe/tests -p "test_*.py" -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

from dataclasses import replace  # noqa: E402

from intercept import HoldWorkspace  # noqa: E402
from policy import GET_RULES, MODES, PRIMARY, SENSITIVITY, decide, decide_detail, validate_rules  # noqa: E402
from release import Held, Token, release_unit, token_from  # noqa: E402


class PolicyTests(unittest.TestCase):
    def test_probe_get_passes(self):
        self.assertEqual(decide("GET", "http://127.0.0.1:8300/projects")[0], "pass")
        self.assertEqual(decide("GET", "http://127.0.0.1:8200/drafts")[0], "pass")

    def test_options_passes(self):
        self.assertEqual(decide("OPTIONS", "http://127.0.0.1:8300/api/v2/tasks")[0], "pass")

    def test_writes_are_held(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertEqual(decide(method, "http://127.0.0.1:8200/compose/send")[0], "hold", method)

    def test_webmail_state_changing_gets_are_held(self):
        self.assertEqual(decide("GET", "http://127.0.0.1:8200/message/abc123")[0], "hold")
        self.assertEqual(decide("GET", "http://127.0.0.1:8200/compose?reply=abc123")[0], "hold")

    def test_webmail_plain_compose_and_draft_pass(self):
        self.assertEqual(decide("GET", "http://127.0.0.1:8200/compose")[0], "pass")
        self.assertEqual(decide("GET", "http://127.0.0.1:8200/compose?draft=2")[0], "pass")
        self.assertEqual(decide("GET", "http://127.0.0.1:8200/?folder=sent")[0], "pass")

    def test_checkout_return_is_held_and_pay_page_passes(self):
        self.assertEqual(decide("GET", "http://127.0.0.1:8100/checkout/return?order=1&intent=pi_x")[0], "hold")
        self.assertEqual(decide("GET", "http://127.0.0.1:8100/checkout/pay/1")[0], "pass")

    def test_provider_hosted_pay_is_held_and_hosted_page_passes(self):
        self.assertEqual(decide("POST", "http://localhost:8102/psp/hosted/pi_x/pay")[0], "hold")
        self.assertEqual(decide("GET", "http://127.0.0.1:8102/psp/hosted/pi_x")[0], "pass")

    def test_other_origins_are_blocked_not_held(self):
        self.assertEqual(decide("POST", "https://example.com/submit")[0], "block")
        self.assertEqual(decide("GET", "http://127.0.0.1:9999/")[0], "block")
        self.assertEqual(decide("GET", "http://127.0.0.1:8025/")[0], "block")  # Mailpit UI is not a browser origin

    def test_reason_is_given_for_hold(self):
        verdict, reason = decide("POST", "http://127.0.0.1:8100/cart/items")
        self.assertEqual(verdict, "hold")
        self.assertIn("POST", reason)


class TokenTests(unittest.TestCase):
    def test_if_match_header_wins(self):
        t = token_from({"If-Match": '"v3"'}, "version=9")
        self.assertEqual(t, Token("if-match", '"v3"'))

    def test_form_version_field(self):
        t = token_from({}, "name=Desk&price=12.50&version=4&csrf=abc")
        self.assertEqual(t, Token("form:version", "4"))

    def test_cart_and_draft_fields(self):
        self.assertEqual(token_from({}, "cart_version=5&qty=2"), Token("form:cart_version", "5"))
        self.assertEqual(token_from({}, "draft_id=7&draft_version=2"), Token("form:draft_version", "2"))

    def test_empty_version_carries_no_token(self):
        self.assertIsNone(token_from({}, "draft_id=&draft_version=&to=bob%40example.test"))

    def test_no_version_field_no_token(self):
        self.assertIsNone(token_from({"Content-Type": "application/json"}, '{"name": "x"}'))
        self.assertIsNone(token_from({}, "sku=LMP-1&qty=1"))


def held(seq, token=None):
    return Held(seq=seq, method="POST", url=f"http://127.0.0.1:8100/x/{seq}", headers={}, body="", token=token)


TOKEN = Token("updated", "t1")


def current_matches_page(h):
    """The server still shows the version the page built on."""
    return h.token.value


class ReleaseTests(unittest.TestCase):
    def test_refused_when_a_version_moved_and_nothing_is_sent(self):
        sent = []
        units = [held(1, Token("form:version", "4")), held(2, Token("form:version", "5"))]
        result = release_unit(units, lambda h: "5", lambda h: sent.append(h.seq) or 200)
        self.assertEqual(result.status, "refused")
        self.assertEqual(result.refused_seqs, [1])
        self.assertEqual(sent, [])
        self.assertEqual(result.sent, [])

    def test_refused_when_current_version_cannot_be_read(self):
        sent = []
        result = release_unit([held(1, Token("if-match", '"v2"'))], lambda h: None, lambda h: sent.append(h.seq) or 200)
        self.assertEqual(result.status, "refused")
        self.assertEqual(sent, [])

    def test_released_in_seq_order_and_read_back_runs(self):
        order = []
        units = [held(3, Token("form:version", "2")), held(1, Token("form:version", "2")), held(2, Token("form:version", "2"))]
        result = release_unit(
            units,
            lambda h: "2",
            lambda h: order.append(h.seq) or 303,
            read_back=lambda: True,
        )
        self.assertEqual(result.status, "released")
        self.assertEqual(order, [1, 2, 3])
        self.assertEqual([s for s, _ in result.sent], [1, 2, 3])
        self.assertTrue(result.verified)

    def test_read_back_mismatch_is_reported(self):
        result = release_unit([held(1, TOKEN)], current_matches_page, lambda h: 200, read_back=lambda: False)
        self.assertEqual(result.status, "released")
        self.assertFalse(result.verified)

    def test_partial_stops_at_first_rejection_and_still_reads_back(self):
        codes = {1: 200, 2: 409, 3: 200}
        sent = []
        read_calls = []
        result = release_unit(
            [held(1, TOKEN), held(2, TOKEN), held(3, TOKEN)],
            current_matches_page,
            lambda h: sent.append(h.seq) or codes[h.seq],
            read_back=lambda: read_calls.append(1) or False,
        )
        self.assertEqual(result.status, "partial")
        self.assertEqual(sent, [1, 2])
        self.assertEqual(result.sent, [(1, 200), (2, 409)])
        self.assertEqual(read_calls, [1])
        self.assertFalse(result.verified)

    def test_missing_status_is_partial(self):
        result = release_unit([held(1, TOKEN)], current_matches_page, lambda h: None)
        self.assertEqual(result.status, "partial")

    def test_empty_unit_is_released_with_nothing_sent(self):
        result = release_unit([], lambda h: None, lambda h: 200, read_back=lambda: True)
        self.assertEqual(result.status, "released")
        self.assertEqual(result.sent, [])
        self.assertIsNone(result.verified)

    def test_as_dict_is_json_ready(self):
        import json

        result = release_unit([held(1, Token("form:cart_version", "3"))], lambda h: "3", lambda h: 303, read_back=lambda: True)
        json.dumps(result.as_dict())


class UnguardedReleaseTests(unittest.TestCase):
    """A held request with no comparable token must never pass the check silently."""

    def test_request_without_token_is_refused_and_nothing_is_sent(self):
        sent = []
        result = release_unit([held(1)], lambda h: None, lambda h: sent.append(h.seq) or 200)
        self.assertEqual(result.status, "refused")
        self.assertEqual(result.refused_seqs, [1])
        self.assertEqual(sent, [])
        self.assertFalse(result.checks[0].ok)
        self.assertEqual(result.checks[0].reason, "no precondition available")

    def test_one_unguarded_request_refuses_the_whole_unit(self):
        sent = []
        units = [held(1, Token("form:version", "4")), held(2)]
        result = release_unit(units, lambda h: "4", lambda h: sent.append(h.seq) or 200)
        self.assertEqual(result.status, "refused")
        self.assertEqual(result.refused_seqs, [2])
        self.assertEqual(sent, [])

    def test_unguarded_request_is_not_ok_even_when_the_server_reports_a_version(self):
        result = release_unit([held(1)], lambda h: "7", lambda h: 200)
        self.assertEqual(result.status, "refused")
        self.assertFalse(result.checks[0].ok)
        self.assertIsNone(result.checks[0].expected)

    def test_refusal_reason_is_in_the_record(self):
        result = release_unit([held(1)], lambda h: None, lambda h: 200)
        self.assertEqual(result.as_dict()["checks"][0]["reason"], "no precondition available")

    def test_moved_and_unreadable_versions_have_their_own_reasons(self):
        moved = release_unit([held(1, TOKEN)], lambda h: "t2", lambda h: 200)
        unreadable = release_unit([held(1, TOKEN)], lambda h: None, lambda h: 200)
        self.assertEqual(moved.checks[0].reason, "version moved")
        self.assertEqual(unreadable.checks[0].reason, "current version unreadable")


MESSAGE = "http://127.0.0.1:8200/message/m1"
REPLY = "http://127.0.0.1:8200/compose?reply=m1"
PAYMENT_RETURN = "http://127.0.0.1:8100/checkout/return?order=1&intent=pi_x"


class PolicyModeTests(unittest.TestCase):
    def test_before_measurement_both_modes_hold_the_same_gets(self):
        for url in (MESSAGE, REPLY, PAYMENT_RETURN):
            for mode in MODES:
                self.assertEqual(decide("GET", url, mode)[0], "hold", (url, mode))

    def test_sensitivity_passes_only_the_rules_marked_for_it(self):
        rules = (replace(GET_RULES[0], sensitivity_pass=True), GET_RULES[1], GET_RULES[2])
        self.assertEqual(decide("GET", MESSAGE, PRIMARY, rules)[0], "hold")
        self.assertEqual(decide("GET", MESSAGE, SENSITIVITY, rules)[0], "pass")
        self.assertEqual(decide("GET", REPLY, SENSITIVITY, rules)[0], "hold")

    def test_a_get_measured_unchanged_passes_in_both_modes(self):
        rules = (GET_RULES[0], replace(GET_RULES[1], primary_hold=False), GET_RULES[2])
        for mode in MODES:
            self.assertEqual(decide("GET", REPLY, mode, rules)[0], "pass", mode)

    def test_payment_return_is_held_in_both_modes(self):
        for mode in MODES:
            self.assertEqual(decide("GET", PAYMENT_RETURN, mode)[0], "hold", mode)

    def test_writes_are_held_in_both_modes(self):
        for mode in MODES:
            self.assertEqual(decide("POST", "http://127.0.0.1:8200/compose/send", mode)[0], "hold", mode)

    def test_unknown_mode_is_an_error(self):
        with self.assertRaises(ValueError):
            decide("GET", MESSAGE, "fast")

    def test_rules_that_would_pass_the_payment_return_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_rules((replace(GET_RULES[2], sensitivity_pass=True),))
        with self.assertRaises(ValueError):
            validate_rules((replace(GET_RULES[2], primary_hold=False),))

    def test_duplicate_rule_names_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_rules((GET_RULES[0], GET_RULES[0]))


class DecideDetailTests(unittest.TestCase):
    def test_held_get_names_its_rule(self):
        self.assertEqual(decide_detail("GET", MESSAGE, PRIMARY)[2], "webmail-open-message")
        self.assertEqual(decide_detail("GET", REPLY, PRIMARY)[2], "webmail-reply-compose")

    def test_writes_and_plain_gets_name_no_rule(self):
        self.assertIsNone(decide_detail("POST", "http://127.0.0.1:8200/compose/send", PRIMARY)[2])
        self.assertEqual(decide_detail("GET", "http://127.0.0.1:8200/compose", PRIMARY), ("pass", "", None))

    def test_passed_get_in_sensitivity_still_names_its_rule(self):
        rules = (replace(GET_RULES[0], sensitivity_pass=True), GET_RULES[1], GET_RULES[2])
        verdict, _, rule = decide_detail("GET", MESSAGE, SENSITIVITY, rules)
        self.assertEqual((verdict, rule), ("pass", "webmail-open-message"))


class FakeRoute:
    def __init__(self):
        self.aborted = None
        self.continued = False

    def abort(self, reason):
        self.aborted = reason

    def continue_(self, **_):
        self.continued = True


class FakeRequest:
    def __init__(self, method, url):
        self.method = method
        self.url = url
        self.post_data = None

    def all_headers(self):
        return {}


def _send(ws, method, url):
    route = FakeRoute()
    ws._on_route(route, FakeRequest(method, url))
    return route


class HoldWorkspaceTests(unittest.TestCase):
    def test_held_get_is_recorded_by_rule_name(self):
        ws = HoldWorkspace(PRIMARY)
        _send(ws, "GET", MESSAGE)
        self.assertEqual(ws.gets_held, {"webmail-open-message"})
        self.assertEqual(ws.counts["hold"], 1)

    def test_passed_get_and_held_write_record_no_rule(self):
        ws = HoldWorkspace(PRIMARY)
        passed = _send(ws, "GET", "http://127.0.0.1:8200/compose")
        held = _send(ws, "POST", "http://127.0.0.1:8200/compose/send")
        self.assertTrue(passed.continued)
        self.assertIsNone(held.aborted)
        self.assertFalse(held.continued)
        self.assertEqual(ws.gets_held, set())
        self.assertEqual(ws.counts, {"pass": 1, "hold": 1, "block": 0})

    def test_other_origin_is_blocked_not_held(self):
        ws = HoldWorkspace(PRIMARY)
        route = _send(ws, "GET", "https://example.com/")
        self.assertEqual(route.aborted, "blockedbyclient")
        self.assertEqual(ws.held, [])
        self.assertEqual(ws.counts["block"], 1)

    def test_sensitivity_workspace_passes_a_rule_marked_for_it(self):
        rules = (replace(GET_RULES[0], sensitivity_pass=True), GET_RULES[1], GET_RULES[2])
        ws = HoldWorkspace(SENSITIVITY, rules)
        route = _send(ws, "GET", MESSAGE)
        self.assertTrue(route.continued)
        self.assertEqual(ws.gets_held, set())

    def test_held_request_gets_no_answer_until_release(self):
        ws = HoldWorkspace(PRIMARY)
        route = _send(ws, "POST", "http://127.0.0.1:8200/compose/send")
        self.assertIsNone(route.aborted)
        self.assertFalse(route.continued)
        self.assertEqual(len(ws.held), 1)

    def test_release_of_a_write_without_token_sends_nothing(self):
        """A Vikunja-style write: JSON body, no If-Match, no version field. The unit is refused."""
        ws = HoldWorkspace(PRIMARY)
        route = FakeRoute()
        request = FakeRequest("PATCH", "http://127.0.0.1:8300/api/v2/tasks/6")
        request.post_data = '{"title": "Renamed"}'
        ws._on_route(route, request)
        self.assertEqual(len(ws.held), 1)
        result = ws.release(current_token=lambda h: None)
        self.assertEqual(result.status, "refused")
        self.assertEqual(result.checks[0].reason, "no precondition available")
        self.assertFalse(route.continued)
        self.assertEqual(len(ws.held), 1)  # still pending: the page gets no answer


class NoFakedResponseTests(unittest.TestCase):
    """The harness never answers a page itself. Only the server's own answer reaches the page."""

    def test_harness_never_calls_route_fulfill(self):
        import ast

        harness = Path(__file__).resolve().parent.parent / "harness"
        files = sorted(harness.glob("*.py"))
        self.assertTrue(files)
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and "fulfill" in node.attr:
                    self.fail(f"{path.name}:{node.lineno} uses .{node.attr}")
                if isinstance(node, ast.Name) and "fulfill" in node.id:
                    self.fail(f"{path.name}:{node.lineno} uses {node.id}")


if __name__ == "__main__":
    unittest.main()
