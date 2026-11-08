"""Version reads for the release check, on the adapter side.

A held write to one task carries the version the page read for that task. The
page's own GET of the task gives the value (`updated`). Before release, the
adapter reads the task again through its own request context, which the hold
workspace does not route, and compares the two values. release.py does the
comparison; this module supplies the two reads.

  - VersionReads watches the page's responses. Only single-task GETs with status
    200 count. The body is read when it is needed, not when the response
    arrives. A body that cannot be read gives no token, never an earlier read.
  - current_updated is the fresh read. Any failure gives None, which refuses.

Live check still to do: the page's single-task GET must carry `updated`, and
the fresh read must return the same string for an unchanged task.
"""

import json
import re
import time
from urllib.parse import urlsplit

from release import Token

TASK_GET = re.compile(r"^/api/v2/tasks/(\d+)$")
TASK_SCOPE = re.compile(r"^/api/v2/tasks/(\d+)(?:/|$)")


def task_id_from_url(url):
    """The task a request acts on, or None. Collections, bulk routes and other routes name no task."""
    match = TASK_SCOPE.match(urlsplit(url).path)
    return match.group(1) if match else None


def updated_from_text(text):
    """The `updated` value of one task in a JSON body, or None."""
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


class VersionReads:
    """The page's single-task reads, in the order they arrived."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.reads = []  # (task_id, arrived_at, read_body); read_body() returns the text or raises

    def observe(self, method, url, status, read_body, at=None):
        if method != "GET" or status != 200:
            return
        match = TASK_GET.match(urlsplit(url).path)
        if not match:
            return
        self.reads.append((match.group(1), self.clock() if at is None else at, read_body))

    def page_token(self, task_id, before):
        """The version the page read last for this task before time `before`, or None."""
        earlier = [read for read in self.reads if read[0] == task_id and read[1] <= before]
        if not earlier:
            return None
        _, _, read_body = earlier[-1]
        try:
            text = read_body()
        except Exception:
            return None
        value = updated_from_text(text)
        if value is None:
            return None
        return Token("page-read:updated", value)


def current_updated(get, task_id):
    """The task's `updated` as the server holds it now. get(path) returns (status, text)."""
    try:
        status, text = get(f"/api/v2/tasks/{task_id}")
    except Exception:
        return None
    if status != 200:
        return None
    return updated_from_text(text)


def fresh_version(get):
    """A current_token function for release: reads the task a held request acts on."""

    def current(held):
        if held.task_id is None:
            return None
        return current_updated(get, held.task_id)

    return current
