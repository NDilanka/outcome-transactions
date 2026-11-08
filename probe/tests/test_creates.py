"""Creates: the parent-version precondition and the duplicate guard for requests that add an object.

A create has no version of its own. Its precondition is the version of the
parent it is added to (read the same way as a task's version), plus a
duplicate guard: no object with the same key may already exist under that
parent, and no two creates in one unit may share a key. Unreadable parts
refuse. No browser, no network.

Run: python -m unittest discover -s probe/tests -p "test_*.py" -v
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

import creates  # noqa: E402
from intercept import HoldWorkspace  # noqa: E402
from policy import PRIMARY  # noqa: E402
from release import Held, Token, check_unit, release_unit  # noqa: E402
from version_read import VersionReads  # noqa: E402

API = "http://127.0.0.1:8300/api/v2"
PROJECT1 = f"{API}/projects/1"
BULK = f"{API}/projects/1/tasks/bulk"
PROJECTS_NEW = f"{API}/projects"
PROJECT_LIST = f"{API}/projects?per_page=50&is_archived=false"
COMMENTS = f"{API}/tasks/1/comments"
TASK1 = f"{API}/tasks/1?expand=comments"
UPDATED_A = "2026-11-08T10:00:00+00:00"
UPDATED_B = "2026-11-08T10:05:00+00:00"
BULK_BODY = json.dumps({"tasks": [{"title": "Buy printer paper", "due_date": "2026-11-20T00:00:00Z"}]})
PROJECT_BODY = json.dumps({"title": "Hiring", "parent_project_id": 0})
COMMENT_BODY = json.dumps({"comment": "<p>Checked with Sam</p>"})


class Response:
    def __init__(self, status):
        self.status = status


class Route:
    """Stands in for a Playwright route. The server answers 200 once the workspace continues it."""

    def __init__(self, status=200):
        self.status = status
        self.aborted = None
        self.continued = False
        self.request = self

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


class KindTests(unittest.TestCase):
    def test_the_three_creates_are_recognised(self):
        self.assertEqual(creates.spec_for("POST", BULK, BULK_BODY).kind, "task")
        self.assertEqual(creates.spec_for("POST", PROJECTS_NEW, PROJECT_BODY).kind, "project")
        self.assertEqual(creates.spec_for("POST", COMMENTS, COMMENT_BODY).kind, "comment")

    def test_a_single_task_create_by_put_is_also_a_create(self):
        spec = creates.spec_for("PUT", f"{API}/projects/1/tasks", json.dumps({"title": "Buy milk"}))
        self.assertEqual((spec.kind, spec.keys), ("task", ("task:1:Buy milk",)))

    def test_updates_and_other_requests_are_not_creates(self):
        self.assertIsNone(creates.spec_for("PATCH", f"{API}/tasks/6", '{"title": "x"}'))
        self.assertIsNone(creates.spec_for("POST", f"{API}/tasks/2/labels", '{"label_id": 3}'))
        self.assertIsNone(creates.spec_for("POST", f"{API}/tasks/bulk", "{}"))
        self.assertIsNone(creates.spec_for("GET", PROJECTS_NEW, None))
        self.assertIsNone(creates.spec_for("POST", f"{API}/user/token/refresh", ""))


class ParentTests(unittest.TestCase):
    def test_a_task_create_takes_its_project_as_parent(self):
        self.assertEqual(creates.spec_for("POST", BULK, BULK_BODY).parent, ("project", "1"))

    def test_a_project_create_under_a_parent_takes_that_project(self):
        body = json.dumps({"title": "Hiring", "parent_project_id": 3})
        self.assertEqual(creates.spec_for("POST", PROJECTS_NEW, body).parent, ("project", "3"))

    def test_a_top_level_project_create_takes_the_project_list_as_parent(self):
        self.assertEqual(creates.spec_for("POST", PROJECTS_NEW, PROJECT_BODY).parent, ("project-list", None))
        no_field = json.dumps({"title": "Hiring"})
        self.assertEqual(creates.spec_for("POST", PROJECTS_NEW, no_field).parent, ("project-list", None))

    def test_a_comment_takes_its_task_as_parent(self):
        self.assertEqual(creates.spec_for("POST", COMMENTS, COMMENT_BODY).parent, ("task", "1"))

    def test_an_unreadable_project_body_has_no_parent(self):
        self.assertIsNone(creates.spec_for("POST", PROJECTS_NEW, "not json").parent)


class KeyTests(unittest.TestCase):
    def test_a_bulk_create_has_one_key_per_task_title(self):
        self.assertEqual(creates.spec_for("POST", BULK, BULK_BODY).keys, ("task:1:Buy printer paper",))
        two = json.dumps({"tasks": [{"title": "A"}, {"title": " B "}]})
        self.assertEqual(creates.spec_for("POST", BULK, two).keys, ("task:1:A", "task:1:B"))

    def test_a_bulk_body_that_is_a_bare_list_or_single_object_is_read_too(self):
        self.assertEqual(creates.spec_for("POST", BULK, json.dumps([{"title": "A"}])).keys, ("task:1:A",))
        self.assertEqual(creates.spec_for("POST", BULK, json.dumps({"title": "A"})).keys, ("task:1:A",))

    def test_a_project_key_is_its_parent_and_title(self):
        self.assertEqual(creates.spec_for("POST", PROJECTS_NEW, PROJECT_BODY).keys, ("project:0:Hiring",))

    def test_a_comment_key_is_its_task_and_plain_text(self):
        self.assertEqual(creates.spec_for("POST", COMMENTS, COMMENT_BODY).keys, ("comment:1:Checked with Sam",))
        escaped = json.dumps({"comment": "<p>Tom &amp; Sam</p><p>again</p>"})
        self.assertEqual(creates.spec_for("POST", COMMENTS, escaped).keys, ("comment:1:Tom & Sam again",))

    def test_a_body_without_a_usable_title_gives_no_key_so_the_create_is_refused_later(self):
        self.assertIsNone(creates.spec_for("POST", BULK, json.dumps({"tasks": [{"title": "  "}]})).keys)
        self.assertIsNone(creates.spec_for("POST", BULK, json.dumps({"tasks": []})).keys)
        self.assertIsNone(creates.spec_for("POST", BULK, "not json").keys)
        self.assertIsNone(creates.spec_for("POST", COMMENTS, json.dumps({"comment": "<p></p>"})).keys)
        self.assertIsNone(creates.spec_for("POST", PROJECTS_NEW, json.dumps({"parent_project_id": 0})).keys)


class ExistingTests(unittest.TestCase):
    def test_the_task_listing_of_the_parent_project_gives_its_keys(self):
        spec = creates.spec_for("POST", BULK, BULK_BODY)
        text = json.dumps([{"title": "Buy printer paper", "project_id": 1, "done": True}, {"title": "Other", "project_id": 1}])
        self.assertEqual(creates.existing_keys(spec, text), {"task:1:Buy printer paper", "task:1:Other"})
        self.assertEqual(spec.existing_path, "/api/v2/projects/1/tasks?per_page=100")

    def test_the_project_listing_gives_parent_and_title_keys(self):
        spec = creates.spec_for("POST", PROJECTS_NEW, PROJECT_BODY)
        text = json.dumps([{"title": "Hiring", "parent_project_id": 0}, {"title": "Work", "parent_project_id": 0}])
        self.assertEqual(creates.existing_keys(spec, text), {"project:0:Hiring", "project:0:Work"})
        self.assertEqual(spec.existing_path, "/api/v2/projects?per_page=100")

    def test_the_comment_listing_gives_plain_text_keys(self):
        spec = creates.spec_for("POST", COMMENTS, COMMENT_BODY)
        text = json.dumps([{"comment": "<p>Checked with Sam</p>"}, {"comment": "<p>Other</p>"}])
        self.assertEqual(creates.existing_keys(spec, text), {"comment:1:Checked with Sam", "comment:1:Other"})
        self.assertEqual(spec.existing_path, "/api/v2/tasks/1/comments?per_page=100")

    def test_an_unreadable_listing_gives_none(self):
        spec = creates.spec_for("POST", BULK, BULK_BODY)
        self.assertIsNone(creates.existing_keys(spec, "not json"))
        self.assertIsNone(creates.existing_keys(spec, json.dumps({"items": []})))
        self.assertIsNone(creates.existing_keys(spec, json.dumps([{"title": None}])))

    def test_a_full_page_of_children_gives_none_because_a_duplicate_may_be_on_the_next_page(self):
        spec = creates.spec_for("POST", BULK, BULK_BODY)
        full = [{"title": f"Task {n}", "project_id": 1} for n in range(creates.PER_PAGE)]
        self.assertIsNone(creates.existing_keys(spec, json.dumps(full)))
        almost = full[:-1]
        self.assertEqual(len(creates.existing_keys(spec, json.dumps(almost))), creates.PER_PAGE - 1)


def get_from(pages):
    """A fake adapter GET: pages maps a path to (status, text). Unknown paths fail."""

    def get(path):
        if path not in pages:
            raise OSError("no such page " + path)
        return pages[path]

    return get


class CheckTests(unittest.TestCase):
    """check_unit on held creates, with the parent token and the existing keys supplied directly."""

    def held(self, seq, url, body, token="v1"):
        spec = creates.spec_for("POST", url, body)
        parent = spec.parent
        target = parent
        return Held(seq=seq, method="POST", url=url, headers={}, body=body, token=Token("page-read:updated", token), target=target, create=spec)

    def existing(self, present):
        return lambda h: present

    def test_a_create_with_matching_parent_and_no_duplicate_is_ok(self):
        h = self.held(1, BULK, BULK_BODY)
        checks = check_unit([h], lambda x: "v1", existing=self.existing(set()))
        self.assertEqual((checks[0].ok, checks[0].reason), (True, "ok"))

    def test_a_duplicate_already_present_refuses(self):
        h = self.held(1, BULK, BULK_BODY)
        checks = check_unit([h], lambda x: "v1", existing=self.existing({"task:1:Buy printer paper"}))
        self.assertEqual((checks[0].ok, checks[0].reason), (False, "duplicate present"))

    def test_two_creates_with_one_key_in_a_unit_refuse_the_second(self):
        first = self.held(1, BULK, BULK_BODY)
        second = self.held(2, BULK, BULK_BODY)
        checks = check_unit([first, second], lambda x: "v1", existing=self.existing(set()))
        self.assertEqual([(c.seq, c.ok, c.reason) for c in checks], [(1, True, "ok"), (2, False, "duplicate in unit")])

    def test_a_key_repeated_inside_one_body_refuses(self):
        body = json.dumps({"tasks": [{"title": "A"}, {"title": "A"}]})
        checks = check_unit([self.held(1, BULK, body)], lambda x: "v1", existing=self.existing(set()))
        self.assertEqual(checks[0].reason, "duplicate in unit")

    def test_an_unreadable_duplicate_check_refuses(self):
        checks = check_unit([self.held(1, BULK, BULK_BODY)], lambda x: "v1", existing=self.existing(None))
        self.assertEqual(checks[0].reason, "duplicate check unreadable")

    def test_a_create_without_a_usable_key_refuses(self):
        h = self.held(1, BULK, json.dumps({"tasks": []}))
        checks = check_unit([h], lambda x: "v1", existing=self.existing(set()))
        self.assertEqual(checks[0].reason, "create key unreadable")

    def test_a_moved_parent_refuses(self):
        checks = check_unit([self.held(1, BULK, BULK_BODY)], lambda x: "v2", existing=self.existing(set()))
        self.assertEqual(checks[0].reason, "version moved")

    def test_an_unreadable_parent_refuses(self):
        checks = check_unit([self.held(1, BULK, BULK_BODY)], lambda x: None, existing=self.existing(set()))
        self.assertEqual(checks[0].reason, "current version unreadable")

    def test_a_create_without_a_parent_token_refuses_and_is_not_read(self):
        h = self.held(1, BULK, BULK_BODY)
        h.token = None
        checks = check_unit([h], lambda x: "v1", existing=lambda x: self.fail("must not read"))
        self.assertEqual(checks[0].reason, "no precondition available")

    def test_one_refused_create_refuses_the_whole_unit_and_nothing_is_sent(self):
        sent = []
        held = [self.held(1, BULK, BULK_BODY), self.held(2, COMMENTS, COMMENT_BODY)]
        result = release_unit(
            held,
            lambda x: "v1",
            lambda h: sent.append(h.seq) or 200,
            existing=lambda h: set() if h.seq == 1 else {"comment:1:Checked with Sam"},
        )
        self.assertEqual(result.status, "refused")
        self.assertEqual(result.refused_seqs, [2])
        self.assertEqual(sent, [])


class IntegrationTests(unittest.TestCase):
    """The page's reads, the held create, and the fresh reads, through the hold workspace."""

    def page_reads(self, pages):
        """pages maps the full URL the page GETs to (status, text)."""
        reads = VersionReads()
        for url, (status, text) in pages.items():
            reads.observe("GET", url, status, lambda t=text: t, at=1.0)
        return reads

    def workspace(self, reads):
        return HoldWorkspace(PRIMARY, page_reads=reads, clock=lambda: 6.0)

    def test_bulk_create_in_a_project_is_released_when_project_and_listing_match(self):
        project = json.dumps({"id": 1, "title": "Inbox", "updated": UPDATED_A})
        listing = json.dumps([{"title": "Old", "project_id": 1}])
        reads = self.page_reads({PROJECT1: (200, project)})
        ws = self.workspace(reads)
        route = Route()
        ws._on_route(route, Request("POST", BULK, BULK_BODY))
        pages = {"/api/v2/projects/1": (200, project), "/api/v2/projects/1/tasks?per_page=100": (200, listing)}
        result = ws.release(current_token=_fresh(pages), existing=_fresh_existing(pages), read_back=None)
        self.assertEqual(result.status, "released")
        self.assertTrue(route.continued)

    def test_bulk_create_is_refused_when_the_project_changed_after_the_page_read(self):
        page = json.dumps({"id": 1, "title": "Inbox", "updated": UPDATED_A})
        moved = json.dumps({"id": 1, "title": "Inbox", "updated": UPDATED_B})
        ws = self.workspace(self.page_reads({PROJECT1: (200, page)}))
        route = Route()
        ws._on_route(route, Request("POST", BULK, BULK_BODY))
        pages = {"/api/v2/projects/1": (200, moved), "/api/v2/projects/1/tasks?per_page=100": (200, "[]")}
        result = ws.release(current_token=_fresh(pages), existing=_fresh_existing(pages))
        self.assertEqual(result.checks[0].reason, "version moved")
        self.assertFalse(route.continued)

    def test_top_level_project_create_uses_the_page_read_of_the_list_with_the_same_query(self):
        listing = json.dumps([{"id": 2, "title": "Home", "parent_project_id": 0, "updated": UPDATED_A}])
        reads = self.page_reads({PROJECT_LIST: (200, listing)})
        ws = self.workspace(reads)
        route = Route()
        ws._on_route(route, Request("POST", PROJECTS_NEW, PROJECT_BODY))
        held = ws.held[0]
        self.assertEqual(held.target, ("project-list", None))
        pages = {"/api/v2/projects?per_page=50&is_archived=false": (200, listing), "/api/v2/projects?per_page=100": (200, listing)}
        result = ws.release(current_token=_fresh(pages), existing=_fresh_existing(pages))
        self.assertEqual(result.status, "released")
        self.assertEqual(held.token.path, "/api/v2/projects?per_page=50&is_archived=false")

    def test_top_level_project_create_is_refused_when_another_project_was_added(self):
        before = json.dumps([{"id": 2, "title": "Home", "parent_project_id": 0, "updated": UPDATED_A}])
        after = json.dumps([{"id": 2, "title": "Home", "parent_project_id": 0, "updated": UPDATED_A}, {"id": 7, "title": "New", "parent_project_id": 0, "updated": UPDATED_B}])
        ws = self.workspace(self.page_reads({PROJECT_LIST: (200, before)}))
        ws._on_route(Route(), Request("POST", PROJECTS_NEW, PROJECT_BODY))
        pages = {"/api/v2/projects?per_page=50&is_archived=false": (200, after), "/api/v2/projects?per_page=100": (200, after)}
        result = ws.release(current_token=_fresh(pages), existing=_fresh_existing(pages))
        self.assertEqual(result.checks[0].reason, "version moved")

    def test_top_level_project_create_is_refused_when_the_title_already_exists(self):
        listing = json.dumps([{"id": 9, "title": "Hiring", "parent_project_id": 0, "updated": UPDATED_A}])
        ws = self.workspace(self.page_reads({PROJECT_LIST: (200, listing)}))
        route = Route()
        ws._on_route(route, Request("POST", PROJECTS_NEW, PROJECT_BODY))
        pages = {"/api/v2/projects?per_page=50&is_archived=false": (200, listing), "/api/v2/projects?per_page=100": (200, listing)}
        result = ws.release(current_token=_fresh(pages), existing=_fresh_existing(pages))
        self.assertEqual(result.checks[0].reason, "duplicate present")
        self.assertFalse(route.continued)

    def test_comment_create_is_released_when_the_task_matches_and_no_comment_exists(self):
        task = json.dumps({"id": 1, "title": "Call supplier", "updated": UPDATED_A})
        ws = self.workspace(self.page_reads({TASK1: (200, task)}))
        route = Route()
        ws._on_route(route, Request("PUT", COMMENTS, COMMENT_BODY))
        pages = {"/api/v2/tasks/1": (200, task), "/api/v2/tasks/1/comments?per_page=100": (200, "[]")}
        result = ws.release(current_token=_fresh(pages), existing=_fresh_existing(pages))
        self.assertEqual(result.status, "released")
        self.assertTrue(route.continued)


def _fresh(pages):
    from version_read import fresh_version

    return fresh_version(get_from(pages))


def _fresh_existing(pages):
    return creates.fresh_existing(get_from(pages))


if __name__ == "__main__":
    unittest.main()
