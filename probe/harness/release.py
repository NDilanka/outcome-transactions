"""Verified release of held requests, as one unit.

A unit is every request a task held, in the order the browser sent them.
Release runs in three steps:

  1. check: each held request must carry a version token, and that token is
     compared with the current version of its target. A held request with no
     token is refused ("no precondition available"), so it can never pass
     silently. A mismatch, or a current version that cannot be read, is refused
     too. Any refusal refuses the whole unit. Nothing is sent. A request can
     take its token from the page's own read of its task (see version_read.py),
     and the current version is read fresh here.
  2. send: the held requests are continued in their original order. The
     first request the server rejects (status 400 or more, or no status)
     stops the release, and the unit is reported as partial. For each sent
     request the release records the read-to-apply gap: the time from its
     check to the start of its send, and to its response. Every request's
     check runs before any send, so a later request's gap includes the sends
     before it.
  3. read back: the caller's read-back function compares the server state
     with the intended state. A unit is verified only when it matches.

The server still applies its own checks (CSRF, version fields, If-Match) when
a request is sent. The check in step 1 runs earlier, so a concurrent edit is
refused before anything is sent. A gap remains between step 1 and the server
check; the probe reports it where it matters.
"""

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional
from urllib.parse import parse_qs

# Form fields that carry a version token in the probe's apps. Empty values
# (a new draft, a new cart) carry no precondition.
VERSION_FIELDS = ("version", "cart_version", "address_version", "draft_version", "settings_version")


@dataclass
class Token:
    source: str  # "if-match", "form:<field name>", or "page-read:updated"
    value: str


@dataclass
class Held:
    seq: int
    method: str
    url: str
    headers: dict
    body: str
    token: Optional[Token] = None
    route: Any = field(default=None, repr=False)  # Playwright route; None in unit tests
    task_id: Optional[str] = None  # the task the request acts on, when it names one
    held_at: Optional[float] = None  # clock time the request was held


def token_from(headers, body):
    """Return the version token a held request was built against, or None."""
    lowered = {k.lower(): v for k, v in headers.items()}
    if lowered.get("if-match"):
        return Token("if-match", lowered["if-match"].strip())
    if body:
        fields = parse_qs(body, keep_blank_values=True)
        for name in VERSION_FIELDS:
            if name in fields and fields[name][0] != "":
                return Token(f"form:{name}", fields[name][0])
    return None


@dataclass
class Check:
    seq: int
    ok: bool
    expected: Optional[str]
    current: Optional[str]
    reason: str
    checked_at: Optional[float] = None  # clock time the answer was in hand; not part of the record


def check_unit(held, current_token, clock=time.monotonic):
    """Compare each token with the current version. current_token(h) returns str or None.

    A request with no token has nothing to compare, so it is never ok and is
    not read. Every check is timed when its answer is in hand, before any send.
    """
    checks = []
    for h in held:
        if h.token is None:
            checks.append(Check(h.seq, False, None, None, "no precondition available", clock()))
            continue
        expected = h.token.value
        current = current_token(h)
        now = clock()
        if current is None:
            checks.append(Check(h.seq, False, expected, None, "current version unreadable", now))
        elif current == expected:
            checks.append(Check(h.seq, True, expected, current, "ok", now))
        else:
            checks.append(Check(h.seq, False, expected, current, "version moved", now))
    return checks


@dataclass
class Release:
    status: str  # "refused", "partial" or "released"
    checks: list
    sent: list  # (seq, HTTP status or None) in send order
    verified: Optional[bool] = None
    refused_seqs: list = field(default_factory=list)
    gaps: list = field(default_factory=list)  # read-to-apply gap per sent request, in send order

    def as_dict(self):
        return {
            "status": self.status,
            "checks": [{k: v for k, v in asdict(c).items() if k != "checked_at"} for c in self.checks],
            "sent": [{"seq": s, "http_status": code} for s, code in self.sent],
            "verified": self.verified,
            "refused_seqs": self.refused_seqs,
            "gaps": self.gaps,
        }


def release_unit(
    held: list,
    current_token: Callable[[Held], Optional[str]],
    send: Callable[[Held], Optional[int]],
    read_back: Optional[Callable[[], bool]] = None,
    clock: Callable[[], float] = time.monotonic,
) -> Release:
    ordered = sorted(held, key=lambda h: h.seq)
    checks = check_unit(ordered, current_token, clock)
    refused = [c.seq for c in checks if not c.ok]
    if refused:
        return Release("refused", checks, [], None, refused)

    checked_at = {c.seq: c.checked_at for c in checks}
    sent = []
    gaps = []
    failed = False
    for h in ordered:
        sent_at = clock()
        code = send(h)
        responded_at = clock()
        sent.append((h.seq, code))
        gaps.append(
            {
                "seq": h.seq,
                "check_to_send_s": round(sent_at - checked_at[h.seq], 4),
                "check_to_response_s": round(responded_at - checked_at[h.seq], 4),
            }
        )
        if code is None or code >= 400:
            failed = True
            break
    verified = read_back() if (read_back is not None and sent) else None
    return Release("partial" if failed else "released", checks, sent, verified, gaps=gaps)
