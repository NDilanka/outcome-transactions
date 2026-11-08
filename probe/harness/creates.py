"""Creates: requests that add an object, checked against their parent and a duplicate guard.

A create has no version of its own, so its precondition has two parts.

  1. Parent version. The parent is the project a task goes into, the project a
     project goes under (or the project list, for a top-level project), or the
     task a comment goes on. The parent's version is read the same way as a
     task's version (version_read.py), and must be unchanged before release.
  2. Duplicate guard. The create's keys are its title (a task or project) or
     its plain comment text, scoped to the parent. Before release, the parent's
     children are read again. A key that already exists refuses. Two creates in
     one unit with the same key refuse the second. A children listing that
     cannot be read refuses. A body with no usable key refuses (fail closed).

After release, the read-back must find exactly one match (run_records.py).

Recognised creates: POST or PUT to a project's task collection (bulk or single),
to the project collection, and to a task's comments. Any other request is not a
create, and its precondition is its task's version (see request_target).
"""

import html
import json
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

from version_read import task_id_from_url

CREATE_METHODS = ("POST", "PUT")
PER_PAGE = 100  # the children listings are read in one page; a full page may hide more children
PROJECTS_PATH = f"/api/v2/projects?per_page={PER_PAGE}"
TASK_COLLECTION = re.compile(r"^/api/v2/projects/(\d+)/tasks(?:/bulk)?$")
PROJECT_COLLECTION = re.compile(r"^/api/v2/projects$")
COMMENT_COLLECTION = re.compile(r"^/api/v2/tasks/(\d+)/comments$")
TAG = re.compile(r"<[^>]*>")


@dataclass
class CreateSpec:
    kind: str  # "task", "project" or "comment"
    parent: Optional[tuple]  # ("project", id), ("project-list", None) or ("task", id); None if unreadable
    keys: Optional[tuple]  # one key per object the request adds; None if no usable key
    existing_path: str  # the children listing the duplicate guard reads, through the adapter's context


def _json(body):
    if body is None:
        return None
    try:
        return json.loads(body)
    except (TypeError, ValueError):
        return None


def _plain(markup):
    """The text of an HTML comment body: tags become spaces, entities are decoded, spaces are collapsed."""
    return " ".join(html.unescape(TAG.sub(" ", markup)).split())


def _task_items(data):
    if isinstance(data, dict) and isinstance(data.get("tasks"), list):
        items = data["tasks"]
    elif isinstance(data, list):
        items = data
    elif isinstance(data, dict) and "title" in data:
        items = [data]
    else:
        return None
    if not items or not all(isinstance(item, dict) for item in items):
        return None
    return items


def _task_spec(project, body):
    keys = None
    items = _task_items(_json(body))
    if items is not None:
        titles = [item.get("title") for item in items]
        if all(isinstance(t, str) and t.strip() for t in titles):
            keys = tuple(f"task:{project}:{t.strip()}" for t in titles)
    return CreateSpec("task", ("project", project), keys, f"/api/v2/projects/{project}/tasks?per_page={PER_PAGE}")


def _project_spec(body):
    data = _json(body)
    if not isinstance(data, dict):
        return CreateSpec("project", None, None, PROJECTS_PATH)
    parent_id = data.get("parent_project_id", 0)
    if not isinstance(parent_id, int) or isinstance(parent_id, bool) or parent_id < 0:
        return CreateSpec("project", None, None, PROJECTS_PATH)
    parent = ("project", str(parent_id)) if parent_id > 0 else ("project-list", None)
    title = data.get("title")
    keys = (f"project:{parent_id}:{title.strip()}",) if isinstance(title, str) and title.strip() else None
    return CreateSpec("project", parent, keys, PROJECTS_PATH)


def _comment_spec(task, body):
    data = _json(body)
    markup = data.get("comment") if isinstance(data, dict) else None
    text = _plain(markup) if isinstance(markup, str) else ""
    keys = (f"comment:{task}:{text}",) if text else None
    return CreateSpec("comment", ("task", task), keys, f"/api/v2/tasks/{task}/comments?per_page={PER_PAGE}")


def spec_for(method, url, body):
    """The CreateSpec for a request that adds an object, or None for any other request."""
    if method.upper() not in CREATE_METHODS:
        return None
    path = urlsplit(url).path
    match = TASK_COLLECTION.match(path)
    if match:
        return _task_spec(match.group(1), body)
    if PROJECT_COLLECTION.match(path):
        return _project_spec(body)
    match = COMMENT_COLLECTION.match(path)
    if match:
        return _comment_spec(match.group(1), body)
    return None


def request_target(method, url, body):
    """(target, spec) for a held request: the version target its check reads, and its create spec if it adds an object.

    A create's target is its parent. Any other request's target is the task it acts on, if it names one.
    """
    spec = spec_for(method, url, body)
    if spec is not None:
        return spec.parent, spec
    task = task_id_from_url(url)
    return (("task", task) if task else None), None


def existing_keys(spec, text):
    """The keys already present under the parent, from the children listing text. None if unreadable or possibly incomplete."""
    data = _json(text)
    if not isinstance(data, list) or len(data) >= PER_PAGE:
        return None
    keys = set()
    for item in data:
        if not isinstance(item, dict):
            return None
        if spec.kind == "comment":
            markup = item.get("comment")
            if not isinstance(markup, str):
                return None
            keys.add(f"comment:{spec.parent[1]}:{_plain(markup)}")
            continue
        title = item.get("title")
        if not isinstance(title, str):
            return None
        if spec.kind == "task":
            keys.add(f"task:{spec.parent[1]}:{title.strip()}")
        else:
            parent_id = item.get("parent_project_id", 0)
            if not isinstance(parent_id, int) or isinstance(parent_id, bool):
                return None
            keys.add(f"project:{parent_id}:{title.strip()}")
    return keys


def fresh_existing(get):
    """An existing-keys function for release: reads the children of the parent the create is added to."""

    def existing(held):
        spec = held.create
        if spec is None:
            return None
        try:
            status, text = get(spec.existing_path)
        except Exception:
            return None
        if status != 200:
            return None
        return existing_keys(spec, text)

    return existing
