"""Version reads for the release check, on the adapter side.

A held write or create acts on a target: a task, a project, or the project
list. The version of a target is what the page read for it:

  - a task or a project: its `updated` value (one JSON object).
  - the project list: a digest of (id, updated) for every project in the list.
    The page's list request is read again with the same path and query, so the
    two reads are the same request.

Before release, the adapter reads the same target again through its own request
context, which the hold workspace does not route. release.py compares the two.

  - VersionReads watches the page's responses. Only GETs with status 200 count:
    single task reads, single project reads, and project list reads (any query).
    The body is read when it is needed, not when the response arrives. A body
    that cannot be read gives no token, never an earlier read.
  - current_version is the fresh read. Any failure gives None, which refuses.

Live check still to do: the page's single-task GET must carry `updated`, the
fresh read must return the same string for an unchanged task, and the project
list must read the same on both sides.
"""

import hashlib
import json
import re
import time
from urllib.parse import urlsplit

from release import Token

TASK_GET = re.compile(r"^/api/v2/tasks/(\d+)$")
TASK_SCOPE = re.compile(r"^/api/v2/tasks/(\d+)(?:/|$)")
PROJECT_GET = re.compile(r"^/api/v2/projects/(\d+)$")
PROJECT_LIST = re.compile(r"^/api/v2/projects$")

SOURCE_OBJECT = "page-read:updated"
SOURCE_LIST = "page-read:list-digest"


def task_id_from_url(url):
    """The task a request acts on, or None. Collections, bulk routes and other routes name no task."""
    match = TASK_SCOPE.match(urlsplit(url).path)
    return match.group(1) if match else None


def updated_from_text(text):
    """The `updated` value of one task or project in a JSON body, or None."""
    try:
        body = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(body, dict):
        return None
    value = body.get("updated")
    if not isinstance(value, str) or value == "":
        return None
    return value


def list_version_from_text(text):
    """A digest of (id, updated) for every item of a JSON list, or None if any item lacks them.

    Order does not matter: the pairs are sorted before hashing.
    """
    try:
        body = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(body, list):
        return None
    pairs = []
    for item in body:
        if not isinstance(item, dict) or "id" not in item:
            return None
        value = item.get("updated")
        if not isinstance(value, str) or value == "":
            return None
        pairs.append(f"{item['id']}:{value}")
    digest = hashlib.sha256("\n".join(sorted(pairs)).encode("utf-8")).hexdigest()
    return "list:" + digest


class VersionReads:
    """The page's reads of versioned targets, in the order they arrived."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.reads = []  # (target, arrived_at, read_body, path_and_query); read_body() returns the text or raises

    def observe(self, method, url, status, read_body, at=None):
        if method != "GET" or status != 200:
            return
        parts = urlsplit(url)
        task = TASK_GET.match(parts.path)
        project = PROJECT_GET.match(parts.path)
        if task:
            target = ("task", task.group(1))
        elif project:
            target = ("project", project.group(1))
        elif PROJECT_LIST.match(parts.path):
            target = ("project-list", None)
        else:
            return
        path_and_query = parts.path + ("?" + parts.query if parts.query else "")
        self.reads.append((target, self.clock() if at is None else at, read_body, path_and_query))

    def page_version(self, target, before):
        """The version the page read last for this target before time `before`, as a Token, or None."""
        earlier = [read for read in self.reads if read[0] == target and read[1] <= before]
        if not earlier:
            return None
        _, _, read_body, path_and_query = earlier[-1]
        try:
            text = read_body()
        except Exception:
            return None
        if target[0] == "project-list":
            value = list_version_from_text(text)
            if value is None:
                return None
            return Token(SOURCE_LIST, value, path_and_query)
        value = updated_from_text(text)
        if value is None:
            return None
        return Token(SOURCE_OBJECT, value)

    def page_token(self, task_id, before):
        """The page's version of one task. Kept for the task-only callers."""
        return self.page_version(("task", task_id), before)


def current_updated(get, task_id):
    """The task's `updated` as the server holds it now. get(path) returns (status, text)."""
    return _current(get, f"/api/v2/tasks/{task_id}", updated_from_text)


def _current(get, path, value_of):
    try:
        status, text = get(path)
    except Exception:
        return None
    if status != 200:
        return None
    return value_of(text)


def current_version(get, held):
    """The target's version as the server holds it now, read the way the page read it. None if unreadable."""
    if held.target is None or held.token is None:
        return None
    kind, ident = held.target
    if kind == "task":
        return _current(get, f"/api/v2/tasks/{ident}", updated_from_text)
    if kind == "project":
        return _current(get, f"/api/v2/projects/{ident}", updated_from_text)
    if kind == "project-list":
        if not held.token.path:
            return None
        return _current(get, held.token.path, list_version_from_text)
    return None


def fresh_version(get):
    """A current_token function for release: reads the target each held request acts on."""

    def current(held):
        return current_version(get, held)

    return current
