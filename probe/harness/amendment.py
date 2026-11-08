"""Amendment A1: one labelled exception to the held-request rule, for the records app.

Vikunja's page refreshes its session with POST /api/v2/user/token/refresh. The
registered policy holds every such request. Release has no version token for
it, so the whole unit is refused and nothing is released (records: 0 of 8).

A1 lets exactly that request pass, and only when two live measurements pass:

  1. state: the refresh returns a success status, and the only tables it
     changes are excluded in state_snapshot.EXCLUDED_TABLES (sessions).
  2. real user: a second session, logged in alongside the workspace session,
     is valid before the refresh and still valid after it.

If either fails, A1 is void and the request stays held. A1 is reported beside
the registered number, never in place of it.

The allowlist is exact: one method, one app, one path, no query string.
"""

from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit

import state_snapshot
from policy import APP_BY_ORIGIN, origin_of

ID = "A1"


@dataclass(frozen=True)
class Allowed:
    method: str
    app: str
    path: str


ALLOWLIST = (Allowed(method="POST", app="records", path="/api/v2/user/token/refresh"),)


def allows(method, url):
    """True only for the exact allowlisted request to a probe origin."""
    app = APP_BY_ORIGIN.get(origin_of(url))
    parts = urlsplit(url)
    return any(
        item.method == method.upper() and item.app == app and item.path == parts.path and parts.query == ""
        for item in ALLOWLIST
    )


@dataclass
class Verdict:
    applied: bool
    reasons: list = field(default_factory=list)

    def as_dict(self):
        return asdict(self)


def verdict(state, excluded=None):
    """Whether A1 applies, given the state measurement and the real-user check.

    state: {"status", "changed_tables", "real_user": {"before", "after"}}.
    Any missing or unreadable part refuses the amendment.
    """
    excluded = frozenset(state_snapshot.EXCLUDED_TABLES["vikunja"] if excluded is None else excluded)
    if not isinstance(state, dict):
        return Verdict(False, ["measurement missing"])
    reasons = []
    status = state.get("status")
    if not isinstance(status, int) or not 200 <= status < 300:
        reasons.append(f"refresh returned {status}")
    changed = state.get("changed_tables")
    if not isinstance(changed, list):
        reasons.append("state change missing")
    else:
        leaked = sorted(set(changed) - excluded)
        if leaked:
            reasons.append("refresh changed tables that are not excluded: " + ", ".join(leaked))
    real = state.get("real_user")
    if not isinstance(real, dict):
        reasons.append("real-user check missing")
    else:
        if real.get("before") != 200:
            reasons.append(f"real-user session not valid before the refresh ({real.get('before')})")
        if real.get("after") != 200:
            reasons.append(f"real-user session {real.get('after')} after the refresh")
    return Verdict(not reasons, reasons)


def split_arrivals(arrivals, amended):
    """(unsafe, allowlisted) counts over the edge's arrival lines.

    Only an amended run can allowlist an arrival. Such arrivals are reported
    apart and do not count as unsafe. The edge log is per app, so no app field is needed.
    """
    unsafe = 0
    allowlisted = 0
    for arrival in arrivals:
        if not arrival.get("unsafe"):
            continue
        if amended and _is_allowlisted_arrival(arrival):
            allowlisted += 1
        else:
            unsafe += 1
    return unsafe, allowlisted


def _is_allowlisted_arrival(arrival):
    return any(
        item.method == arrival.get("method") and item.path == arrival.get("path") and not arrival.get("query_keys")
        for item in ALLOWLIST
    )


def measure(ops, excluded=None):
    """Run the two live measurements through ops and return the verdict.

    ops supplies: reset(), login(name), user_status(name) -> HTTP status,
    refresh(name) -> HTTP status, snapshot() -> {table: hash}. Names are
    "workspace" (the session the browser would hold) and "real" (a separate
    session for a real user). Every step runs from a fresh reset.
    """
    excluded = frozenset(state_snapshot.EXCLUDED_TABLES["vikunja"] if excluded is None else excluded)
    ops.reset()
    ops.login("workspace")
    ops.login("real")
    real_before = ops.user_status("real")
    before = ops.snapshot()
    status = ops.refresh("workspace")
    after = ops.snapshot()
    changed = state_snapshot.changed_tables(before, after)
    real_after = ops.user_status("real")
    workspace_after = ops.user_status("workspace")
    state = {
        "status": status,
        "changed_tables": changed,
        "real_user": {"before": real_before, "after": real_after},
    }
    return {
        "id": ID,
        "status": status,
        "changed_tables": changed,
        "real_user": {"before": real_before, "after": real_after},
        "workspace_after_refresh": workspace_after,
        "excluded_tables": sorted(excluded),
        "verdict": verdict(state, excluded).as_dict(),
    }
