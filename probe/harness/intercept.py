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

from policy import PRIMARY, decide_detail
from release import Held, release_unit, token_from


class HoldWorkspace:
    def __init__(self, mode=PRIMARY, rules=None):
        self.mode = mode
        self.rules = rules  # None means policy.GET_RULES
        self.gets_held = set()  # names of GET rules that held a request in this workspace
        self.held = []
        self.counts = {"pass": 0, "hold": 0, "block": 0}
        self.blocked_reasons = []
        self._seq = itertools.count(1)

    def attach(self, context):
        context.route("**/*", self._on_route)

    def _on_route(self, route, request):
        verdict, reason, rule = decide_detail(request.method, request.url, self.mode, self.rules)
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
            self.held.append(
                Held(
                    seq=next(self._seq),
                    method=request.method,
                    url=request.url,
                    headers=headers,
                    body=body,
                    token=token_from(headers, body),
                    route=route,
                )
            )
            return
        route.continue_()

    def release(self, current_token, read_back=None):
        """Release the held unit in order. current_token(h) reads the target's version."""

        def send(h):
            h.route.continue_(headers=h.headers)
            response = h.route.request.response()
            return response.status if response is not None else None

        result = release_unit(self.held, current_token, send, read_back)
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
