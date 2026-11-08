"""Verified release of held requests, as one unit.

A unit is every request a task held, in the order the browser sent them.
Release runs in three steps:

  1. check: each held request that carries a version token is compared with
     the current version of its target. A mismatch, or a current version that
     cannot be read, refuses the whole unit. Nothing is sent.
  2. send: the held requests are continued in their original order. The
     first request the server rejects (status 400 or more, or no status)
     stops the release, and the unit is reported as partial.
  3. read back: the caller's read-back function compares the server state
     with the intended state. A unit is verified only when it matches.

The server still applies its own checks (CSRF, version fields, If-Match) when
a request is sent. The check in step 1 runs earlier, so a concurrent edit is
refused before anything is sent. A gap remains between step 1 and the server
check; the probe reports it where it matters.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional
from urllib.parse import parse_qs

# Form fields that carry a version token in the probe's apps. Empty values
# (a new draft, a new cart) carry no precondition.
VERSION_FIELDS = ("version", "cart_version", "address_version", "draft_version", "settings_version")


@dataclass
class Token:
    source: str  # "if-match" or "form:<field name>"
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


def check_unit(held, current_token):
    """Compare each token with the current version. current_token(h) returns str or None."""
    checks = []
    for h in held:
        if h.token is None:
            checks.append(Check(h.seq, True, None, None))
            continue
        current = current_token(h)
        checks.append(Check(h.seq, current == h.token.value, h.token.value, current))
    return checks


@dataclass
class Release:
    status: str  # "refused", "partial" or "released"
    checks: list
    sent: list  # (seq, HTTP status or None) in send order
    verified: Optional[bool] = None
    refused_seqs: list = field(default_factory=list)

    def as_dict(self):
        return {
            "status": self.status,
            "checks": [asdict(c) for c in self.checks],
            "sent": [{"seq": s, "http_status": code} for s, code in self.sent],
            "verified": self.verified,
            "refused_seqs": self.refused_seqs,
        }


def release_unit(
    held: list,
    current_token: Callable[[Held], Optional[str]],
    send: Callable[[Held], Optional[int]],
    read_back: Optional[Callable[[], bool]] = None,
) -> Release:
    ordered = sorted(held, key=lambda h: h.seq)
    checks = check_unit(ordered, current_token)
    refused = [c.seq for c in checks if not c.ok]
    if refused:
        return Release("refused", checks, [], None, refused)

    sent = []
    failed = False
    for h in ordered:
        code = send(h)
        sent.append((h.seq, code))
        if code is None or code >= 400:
            failed = True
            break
    verified = read_back() if (read_back is not None and sent) else None
    return Release("partial" if failed else "released", checks, sent, verified)
