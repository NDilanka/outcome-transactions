"""Which browser requests are held, which pass, and which are blocked.

Only the probe's own origins are reachable from the workspace. Requests to
any other origin are blocked. Requests to probe origins are held when they
change state: any method other than GET, HEAD or OPTIONS. GETs are held only
through GET_RULES, which are set from measurement (see probe/harness/state_snapshot.py).

Two modes:

- primary: every rule with primary_hold set is held. This is the run that
  answers K1.
- sensitivity: the same, except rules with sensitivity_pass set may pass. Used
  only for GETs whose measured effect is reversible and low-stakes. The
  payment return is never passed in either mode.
"""

from dataclasses import dataclass
from typing import Callable
from urllib.parse import parse_qs, urlsplit

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

PRIMARY = "primary"
SENSITIVITY = "sensitivity"
MODES = (PRIMARY, SENSITIVITY)

# Probe origins the browser may use. Edge ports log the traffic before it
# reaches the app; the payment provider runs without an edge.
APP_BY_ORIGIN = {
    "http://127.0.0.1:8100": "checkout",
    "http://127.0.0.1:8200": "webmail",
    "http://127.0.0.1:8300": "records",
    "http://127.0.0.1:8102": "psp",
    "http://localhost:8102": "psp",
}


def _is_open_message(path, query):
    return path.startswith("/message/") and path.count("/") == 2


def _is_compose_reply(path, query):
    return path == "/compose" and "reply" in query


def _is_payment_return(path, query):
    return path == "/checkout/return"


@dataclass(frozen=True)
class GetRule:
    name: str
    app: str
    match: Callable[[str, dict], bool]
    primary_hold: bool = True  # held in the primary run
    sensitivity_pass: bool = False  # may pass in the sensitivity run
    evidence: str = "registered, not measured yet"


# Rules set from measurement. Until a GET is measured, it stays held in both
# modes. Update primary_hold and sensitivity_pass only with the measured
# evidence written into the rule.
GET_RULES = (
    GetRule("webmail-open-message", "webmail", _is_open_message),
    GetRule("webmail-reply-compose", "webmail", _is_compose_reply),
    GetRule("checkout-payment-return", "checkout", _is_payment_return),
)

# Rules that must stay held in both modes, whatever the measurement says.
NEVER_PASS = frozenset({"checkout-payment-return"})


def validate_rules(rules):
    """Raise ValueError if a rule that must stay held could pass."""
    for rule in rules:
        if rule.name in NEVER_PASS and (not rule.primary_hold or rule.sensitivity_pass):
            raise ValueError(f"{rule.name} must stay held in both modes")
    names = [rule.name for rule in rules]
    if len(set(names)) != len(names):
        raise ValueError("duplicate GET rule names")


validate_rules(GET_RULES)


def origin_of(url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or parts.hostname is None or parts.port is None:
        return None
    return f"{parts.scheme}://{parts.hostname}:{parts.port}"


AMENDED_PASS_REASON = "allowlisted by amendment A1"


def decide_detail(method, url, mode=PRIMARY, rules=None, allowed=None):
    """Return (verdict, reason, rule_name).

    Verdict is "pass", "hold" or "block". rule_name is the GET rule that decided
    a probe GET, and None otherwise. allowed(method, url) is the amendment's
    allowlist (amendment.allows); None means the registered policy, with no exception.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}")
    origin = origin_of(url)
    app = APP_BY_ORIGIN.get(origin)
    if app is None:
        return "block", "not a probe origin", None
    if method.upper() not in SAFE_METHODS:
        if allowed is not None and allowed(method, url):
            return "pass", AMENDED_PASS_REASON, None
        return "hold", f"{method.upper()} request", None
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    for rule in GET_RULES if rules is None else rules:
        if rule.app != app or not rule.match(parts.path, query):
            continue
        held = rule.primary_hold and (mode == PRIMARY or not rule.sensitivity_pass)
        if held:
            return "hold", f"GET with a server-side effect ({rule.name})", rule.name
        return "pass", f"GET passed in {mode} mode ({rule.name})", rule.name
    return "pass", "", None


def decide(method, url, mode=PRIMARY, rules=None, allowed=None):
    """Return (verdict, reason). Verdict is "pass", "hold" or "block"."""
    verdict, reason, _ = decide_detail(method, url, mode, rules, allowed)
    return verdict, reason
