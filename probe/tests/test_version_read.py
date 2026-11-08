"""Version reads for the release check: the page's own reads, the adapter's fresh
read, the read-to-apply gap, and the refusals that follow. No browser, no network.

Run: python -m unittest discover -s probe/tests -p "test_*.py" -v
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

from intercept import HoldWorkspace  # noqa: E402
from policy import PRIMARY  # noqa: E402
from release import Held, Token, release_unit  # noqa: E402
from version_read import (  # noqa: E402
    VersionReads,
    current_updated,
    fresh_version,
    task_id_from_url,
    updated_from_text,
)

API = "http://127.0.0.1:8300/api/v2"
TASK6 = f"{API}/tasks/6"
EARLIER_UPDATED = "2026-11-08T10:00:00+00:00"
LATER_UPDATED = "2026-11-08T10:05:00+00:00"
EARLIER = json.dumps({"id": 6, "title": "Buy milk", "updated": EARLIER_UPDATED})
LATER = json.dumps({"id": 6, "title": "Buy milk", "updated": LATER_UPDATED})
PATCH_BODY = '[{"op": "add", "path": "/title", "value": "Renamed"}]'


def closed_page():
    raise RuntimeError("page closed")


def broken_connection(path):
    raise OSError("connection reset")


class Response:
    def __init__(self, status):
        self.status = status


class Route:
    """Stands in for a Playwright route. The server answers only once the workspace continues it."""

    def __init__(self, status=200):
        self.status = status
        self.aborted = None
        self.continued = False
        self.request = self  # release reads h.route.request.response()

    def abort(self, reason):
        self.aborted = reason

    def continue_(self, **_):
        self.continued = True

    def response(self):
        return Response(self.status) if self.continued else None


class Request:
    def __init__(self, method, url, post_data=""):
        self.method = method
        self.url = url
        self.post_data = post_data

    def all_headers(self):
        return {}


def hold(ws, request):
    route = Route()
    ws._on_route(route, request)
    return route


class TaskIdTests(unittest.TestCase):
    def test_single_task_and_its_sub_routes_name_the_task(self):
        self.assertEqual(task_id_from_url(TASK6), "6")
        self.assertEqual(task_id_from_url(f"{API}/tasks/2/labels"), "2")
        self.assertEqual(task_id_from_url(f"{API}/tasks/6/comments"), "6")

    def test_collections_and_other_routes_name_no_task(self):
        self.assertIsNone(task_id_from_url(f"{API}/tasks/bulk"))
        self.assertIsNone(task_id_from_url(f"{API}/projects/1/tasks/bulk"))
        self.assertIsNone(task_id_from_url(f"{API}/projects"))
        self.assertIsNone(task_id_from_url(f"{API}/user/token/refresh"))


class UpdatedTests(unittest.TestCase):
    def test_reads_updated_from_a_task_body(self):
        self.assertEqual(updated_from_text(EARLIER), EARLIER_UPDATED)

    def test_anything_else_gives_none(self):
        self.assertIsNone(updated_from_text("not json"))
        self.assertIsNone(updated_from_text('{"id": 6}'))
        self.assertIsNone(updated_from_text('{"id": 6, "updated": ""}'))
        self.assertIsNone(updated_from_text(json.dumps([{"id": 6, "updated": EARLIER_UPDATED}])))


class PageReadTests(unittest.TestCase):
    def test_the_token_is_the_version_the_page_read_last_before_the_write(self):
        reads = VersionReads()
        reads.observe("GET", TASK6, 200, lambda: EARLIER, at=1.0)
        reads.observe("GET", TASK6, 200, lambda: LATER, at=5.0)
        self.assertEqual(reads.page_token("6", before=6.0), Token("page-read:updated", LATER_UPDATED))

    def test_a_read_after_the_write_is_not_used(self):
        reads = VersionReads()
        reads.observe("GET", TASK6, 200, lambda: EARLIER, at=1.0)
        reads.observe("GET", TASK6, 200, lambda: LATER, at=9.0)
        self.assertEqual(reads.page_token("6", before=6.0).value, EARLIER_UPDATED)

    def test_no_read_before_the_write_gives_no_token(self):
        reads = VersionReads()
        reads.observe("GET", TASK6, 200, lambda: EARLIER, at=7.0)
        self.assertIsNone(reads.page_token("6", before=6.0))

    def test_only_single_task_gets_with_status_200_count(self):
        reads = VersionReads()
        reads.observe("GET", f"{API}/tasks/4", 200, lambda: EARLIER, at=1.0)
        reads.observe("POST", TASK6, 200, lambda: EARLIER, at=1.0)
        reads.observe("GET", TASK6, 404, lambda: EARLIER, at=1.0)
        reads.observe("GET", f"{API}/projects/1/tasks", 200, lambda: "[]", at=1.0)
        self.assertIsNone(reads.page_token("6", before=6.0))

    def test_an_unreadable_last_read_gives_no_token_not_an_earlier_one(self):
        reads = VersionReads()
        reads.observe("GET", TASK6, 200, lambda: EARLIER, at=1.0)
        reads.observe("GET", TASK6, 200, closed_page, at=2.0)
        self.assertIsNone(reads.page_token("6", before=6.0))


class FreshReadTests(unittest.TestCase):
    def test_the_fresh_read_is_the_task_path_through_the_adapter_request(self):
        calls = []

        def get(path):
            calls.append(path)
            return 200, LATER

        self.assertEqual(current_updated(get, "6"), LATER_UPDATED)
        self.assertEqual(calls, ["/api/v2/tasks/6"])

    def test_failed_or_broken_fresh_reads_give_none(self):
        self.assertIsNone(current_updated(lambda path: (404, "{}"), "6"))
        self.assertIsNone(current_updated(lambda path: (200, "not json"), "6"))
        self.assertIsNone(current_updated(broken_connection, "6"))

    def test_fresh_version_reads_only_held_requests_that_name_a_task(self):
        read = fresh_version(lambda path: (200, LATER))
        with_task = Held(seq=1, method="PATCH", url=TASK6, headers={}, body="", task_id="6")
        no_task = Held(seq=2, method="POST", url=f"{API}/user/token/refresh", headers={}, body="")
        self.assertEqual(read(with_task), LATER_UPDATED)
        self.assertIsNone(read(no_task))


class WorkspaceReleaseTests(unittest.TestCase):
    """The page read the task at t=1 and held a rename at t=6. The release reads the task fresh."""

    def setUp(self):
        self.reads = VersionReads()
        self.reads.observe("GET", TASK6, 200, lambda: EARLIER, at=1.0)
        self.ws = HoldWorkspace(PRIMARY, page_reads=self.reads, clock=lambda: 6.0)
        self.route = hold(self.ws, Request("PATCH", TASK6, PATCH_BODY))

    def test_released_when_the_fresh_read_matches_the_page_read(self):
        result = self.ws.release(current_token=fresh_version(lambda path: (200, EARLIER)))
        self.assertEqual(result.status, "released")
        self.assertTrue(self.route.continued)
        self.assertEqual(self.ws.held, [])
        self.assertEqual(result.checks[0].reason, "ok")

    def test_refused_when_someone_changed_the_task_after_the_page_read(self):
        result = self.ws.release(current_token=fresh_version(lambda path: (200, LATER)))
        self.assertEqual(result.status, "refused")
        self.assertEqual(result.checks[0].reason, "version moved")
        self.assertFalse(self.route.continued)
        self.assertEqual(len(self.ws.held), 1)

    def test_refused_when_the_fresh_read_fails(self):
        result = self.ws.release(current_token=fresh_version(broken_connection))
        self.assertEqual(result.checks[0].reason, "current version unreadable")
        self.assertFalse(self.route.continued)

    def test_refused_when_the_page_never_read_the_task(self):
        ws = HoldWorkspace(PRIMARY, page_reads=VersionReads(), clock=lambda: 6.0)
        route = hold(ws, Request("PATCH", TASK6, PATCH_BODY))
        result = ws.release(current_token=fresh_version(lambda path: (200, EARLIER)))
        self.assertEqual(result.checks[0].reason, "no precondition available")
        self.assertFalse(route.continued)

    def test_one_write_without_a_precondition_refuses_the_whole_unit(self):
        refresh = hold(self.ws, Request("POST", f"{API}/user/token/refresh", ""))
        result = self.ws.release(current_token=fresh_version(lambda path: (200, EARLIER)))
        self.assertEqual(result.status, "refused")
        self.assertEqual(result.refused_seqs, [2])
        self.assertFalse(self.route.continued)
        self.assertFalse(refresh.continued)


class GapTests(unittest.TestCase):
    def test_each_sent_request_records_read_to_send_and_read_to_response(self):
        token = Token("page-read:updated", "t1")
        held = [Held(seq=1, method="PATCH", url=TASK6, headers={}, body="", token=token)]
        times = iter([10.0, 10.3, 10.8])  # the check, the send starts, the response arrives
        result = release_unit(held, lambda h: "t1", lambda h: 200, clock=lambda: next(times))
        self.assertEqual(result.status, "released")
        self.assertEqual(len(result.gaps), 1)
        self.assertEqual(result.gaps[0]["seq"], 1)
        self.assertAlmostEqual(result.gaps[0]["check_to_send_s"], 0.3)
        self.assertAlmostEqual(result.gaps[0]["check_to_response_s"], 0.8)

    def test_later_requests_carry_the_sends_before_them(self):
        token = Token("page-read:updated", "t1")
        held = [
            Held(seq=1, method="PATCH", url=TASK6, headers={}, body="", token=token),
            Held(seq=2, method="POST", url=f"{API}/tasks/6/comments", headers={}, body="", token=token),
        ]
        # Both checks run before any send: check 1, check 2, send 1 (start, end), send 2 (start, end).
        times = iter([0.0, 0.1, 1.0, 1.1, 2.0, 2.1])
        result = release_unit(held, lambda h: "t1", lambda h: 200, clock=lambda: next(times))
        first, second = result.gaps
        self.assertAlmostEqual(first["check_to_send_s"], 1.0)
        self.assertAlmostEqual(second["check_to_send_s"], 1.9)

    def test_every_release_has_a_gaps_field_even_when_refused(self):
        refused = release_unit([Held(seq=1, method="POST", url=TASK6, headers={}, body="")], lambda h: None, lambda h: 200)
        self.assertEqual(refused.as_dict()["gaps"], [])


if __name__ == "__main__":
    unittest.main()
