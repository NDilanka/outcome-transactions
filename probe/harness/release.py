"""Verified release of held requests, as one unit.

A unit is every request a task held, in the order the browser sent them.
Release runs in three steps:

  1. check: each held request must carry a version token, and that token is
     compared with the current version of its target. A held request with no
     token is refused ("no precondition available"), so it can never pass
     silently. A mismatch, or a current version that cannot be read, is refused
     too. A create also passes the duplicate guard (creates.py): its keys must
     be readable, absent under the parent, and unique in the unit. Any refusal
     refuses the whole unit. Nothing is sent. A request takes its token from the
     page's own read of its target (see version_read.py), and the current
     version is read fresh here.
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
    source: str  # "if-match", "form:<field name>", "page-read:updated" or "page-read:list-digest"
    value: str
    path: Optional[str] = None  # for a project-list version: the page's request path and query, read again the same way


@dataclass
class Held:
    seq: int
    method: str
    url: str
    headers: dict
    body: str
    token: Optional[Token] = None
    route: Any = field(default=None, repr=False)  # Playwright route; None in unit tests
    target: Optional[tuple] = None  # ("task", id), ("project", id) or ("project-list", None): the version the check reads
    create: Any = None  # creates.CreateSpec when the request adds an object, else None
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


def check_unit(held, current_token, clock=time.monotonic, existing=None):
    """Compare each token with the current version, and for creates, check the duplicate guard.

    current_token(h) returns the target's current version, str or None.
    existing(h) returns the keys already present under a create's parent, or None if unreadable.

    A request with no token has nothing to compare, so it is never ok and is
    not read. Every check is timed when its answer is in hand, before any send.
    Creates are checked in the order of the unit: a key claimed by an earlier
    create in the unit refuses a later one.
    """
    checks = []
    claimed = {}  # create key -> seq of the earlier create that claimed it in this unit
    for h in held:
        checks.append(_check_one(h, current_token, existing, claimed, clock))
    return checks


def _check_one(h, current_token, existing, claimed, clock):
    if h.token is None:
        return Check(h.seq, False, None, None, "no precondition available", clock())
    expected = h.token.value
    current = current_token(h)
    if current is None:
        return Check(h.seq, False, expected, None, "current version unreadable", clock())
    if current != expected:
        return Check(h.seq, False, expected, current, "version moved", clock())
    if h.create is not None:
        reason = _duplicate_reason(h, existing, claimed)
        if reason is not None:
            return Check(h.seq, False, expected, current, reason, clock())
    return Check(h.seq, True, expected, current, "ok", clock())


def _duplicate_reason(h, existing, claimed):
    """None when the create's keys are free, else the refusal reason. Claims the keys either way."""
    keys = h.create.keys
    if keys is None:
        return "create key unreadable"
    present = existing(h) if existing is not None else None
    if present is None:
        return "duplicate check unreadable"
    if any(key in present for key in keys):
        return "duplicate present"
    repeated = len(set(keys)) != len(keys) or any(key in claimed for key in keys)
    for key in keys:
        claimed.setdefault(key, h.seq)
    return "duplicate in unit" if repeated else None


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
    existing: Optional[Callable[[Held], Optional[set]]] = None,
) -> Release:
    ordered = sorted(held, key=lambda h: h.seq)
    checks = check_unit(ordered, current_token, clock, existing)
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
