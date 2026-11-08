"""Playwright wiring for the hold workspace.

Attach one HoldWorkspace to a browser context. Probe origins pass, state
changes are held, and every other origin is blocked. A held request stays
pending: the page receives no response for it until release.

Release relays the server's own answer. Each held request is continued to the
server in order, and the browser gets the real response. Nothing is faked.
Discard aborts the held requests, which the page sees as a network error.

Not run during the paused phase. Needs the orchestrator's go-ahead before any
browser start.
"""

import itertools
import time
from urllib.parse import parse_qs, urlsplit

from creates import request_target
from policy import AMENDED_PASS_REASON, PRIMARY, decide_detail
from release import Held, release_unit, token_from


class HoldWorkspace:
    def __init__(self, mode=PRIMARY, rules=None, page_reads=None, clock=time.monotonic, allowed=None):
        self.mode = mode
        self.rules = rules  # None means policy.GET_RULES
        self.page_reads = page_reads  # version_read.VersionReads of the page, or None
        self.clock = clock
        self.allowed = allowed  # amendment allowlist (amendment.allows) for A1 runs; None for the registered policy
        self.gets_held = set()  # names of GET rules that held a request in this workspace
        self.held = []
        self.counts = {"pass": 0, "hold": 0, "block": 0}
        self.blocked_reasons = []
        self.amended_passes = []  # paths of allowlisted requests passed under A1, in order
        self.holding = True  # False for setup and baseline runs: probe requests pass, other origins stay blocked
        self.get_seen = {}  # (method, path, query key names) -> first full URL seen, for the GET measurement
        self._seq = itertools.count(1)

    def attach(self, context):
        context.route("**/*", self._on_route)

    def _on_route(self, route, request):
        verdict, reason, rule = decide_detail(request.method, request.url, self.mode, self.rules, self.allowed)
        if verdict == "hold" and not self.holding:
            verdict, reason, rule = "pass", "holds off", None
        if verdict == "pass" and reason == AMENDED_PASS_REASON:
            self.amended_passes.append(urlsplit(request.url).path)
        if request.method == "GET" and verdict != "block":
            parts = urlsplit(request.url)
            keys = tuple(sorted(parse_qs(parts.query, keep_blank_values=True)))
            self.get_seen.setdefault((request.method, parts.path, keys), request.url)
        if verdict == "hold" and rule:
            self.gets_held.add(rule)
        self.counts[verdict] += 1
        if verdict == "block":
            self.blocked_reasons.append(reason)
            route.abort("blockedbyclient")
            return
        if verdict == "hold":
            # No response: the request stays pending until release or discard.
            headers = request.all_headers()
            body = request.post_data or ""
            target, create = request_target(request.method, request.url, body)
            self.held.append(
                Held(
                    seq=next(self._seq),
                    method=request.method,
                    url=request.url,
                    headers=headers,
                    body=body,
                    token=token_from(headers, body),
                    route=route,
                    target=target,
                    create=create,
                    held_at=self.clock(),
                )
            )
            return
        route.continue_()

    def release(self, current_token, read_back=None, existing=None):
        """Release the held unit in order.

        current_token(h) reads the version of the held request's target.
        existing(h) reads the keys already under a create's parent (creates only).

        A held request with no token of its own takes the version the page
        read last for its target, before the request was held.
        """
        if self.page_reads is not None:
            for h in self.held:
                if h.token is None and h.target is not None:
                    h.token = self.page_reads.page_version(h.target, before=h.held_at)

        def send(h):
            h.route.continue_(headers=h.headers)
            response = h.route.request.response()
            return response.status if response is not None else None

        result = release_unit(self.held, current_token, send, read_back, clock=self.clock, existing=existing)
        if result.status != "refused":
            sent = {seq for seq, _ in result.sent}
            self.held = [h for h in self.held if h.seq not in sent]
        return result

    def discard(self):
        """Abort every held request. The page sees a network error."""
        for h in self.held:
            h.route.abort("blockedbyclient")
        count = len(self.held)
        self.held = []
        return count
