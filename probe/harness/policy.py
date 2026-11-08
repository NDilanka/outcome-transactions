"""Which browser requests are held, which pass, and which are blocked.

Only the probe's own origins are reachable from the workspace. Requests to
any other origin are blocked. Requests to probe origins are held when they
change state: any method other than GET, HEAD or OPTIONS, and a few GET
routes that change state on the server. Everything else passes.
"""

from urllib.parse import parse_qs, urlsplit

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Probe origins the browser may use. Edge ports log the traffic before it
# reaches the app; the payment provider runs without an edge.
APP_BY_ORIGIN = {
    "http://127.0.0.1:8100": "checkout",
    "http://127.0.0.1:8200": "webmail",
    "http://127.0.0.1:8300": "records",
    "http://127.0.0.1:8102": "psp",
    "http://localhost:8102": "psp",
}


def _is_compose_reply(path, query):
    return path == "/compose" and "reply" in query


# GET routes that change server state. Each entry is a predicate on the path
# and the parsed query string. Verify the records list against the app's
# code before the measured run (see probe/apps/vikunja/NOTES.md).
STATE_CHANGING_GETS = {
    "checkout": [lambda path, query: path == "/checkout/return"],
    "webmail": [
        lambda path, query: path.startswith("/message/") and path.count("/") == 2,
        _is_compose_reply,
    ],
    "records": [],
    "psp": [],
}


def origin_of(url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or parts.hostname is None or parts.port is None:
        return None
    return f"{parts.scheme}://{parts.hostname}:{parts.port}"


def decide(method, url):
    """Return (verdict, reason). Verdict is "pass", "hold" or "block"."""
    origin = origin_of(url)
    app = APP_BY_ORIGIN.get(origin)
    if app is None:
        return "block", "not a probe origin"
    if method.upper() not in SAFE_METHODS:
        return "hold", f"{method.upper()} request"
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    for predicate in STATE_CHANGING_GETS[app]:
        if predicate(parts.path, query):
            return "hold", "GET with a server-side effect"
    return "pass", ""
