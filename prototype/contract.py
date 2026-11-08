"""Adapter contract for the commit engine: outcomes, levels, capabilities, receipts, and the protocols that adapters,
verifiers and scenario hooks implement. Declarations only. The engine decides; adapters do the operations on one kind
of state; verifiers judge views; hooks name the stages of a transaction where a scenario may act.

Phase 0 calls a subset of the roadmap's operations (section 3.2). ready, reconcile and read-set capture come with the
adapters that need them in Phase 1."""
from dataclasses import dataclass
from typing import Any, Optional, Protocol

# Outcomes. Every report names one. A refusal leaves the real resource as it was.
COMMITTED = "committed"
COMMITTED_RELEASE_FAILED = "committed_release_failed"  # the commit stands; some held effects were not released
POST_COMMIT_FAILED = "post_commit_failed"  # the commit did not stand; rolled_back and needs_user say what was restored
ERROR = "error"  # an unexpected failure after the commit started
REFUSED_ERROR = "refused_error"  # an unexpected failure before the commit started
TRUE_CONFLICT = "true_conflict"  # the user and the winner changed the same unit
ABORTED_USER_EDIT = "aborted_user_edit"  # the user changed the resource while the commit was in progress
ANCHOR_MISMATCH = "anchor_mismatch"  # the unit the winner wrote no longer has the anchor it was verified against
DOCUMENT_BUSY = "document_busy"  # replays kept losing to newer user edits
REPLAY_FAILED = "replay_failed"  # a replay on the current state did not pass the frozen spec
REFUSED_OWNER = "refused_owner"  # the resource has a live or unknown owner, and the adapter can see owners
SPEC_REJECTED = "spec_rejected"  # the spec failed its own mutation tests
NO_PASSING_FORK = "no_passing_fork"  # no fork passed the spec

REFUSALS = frozenset({REFUSED_ERROR, TRUE_CONFLICT, ABORTED_USER_EDIT, ANCHOR_MISMATCH, DOCUMENT_BUSY, REPLAY_FAILED,
                      REFUSED_OWNER, SPEC_REJECTED, NO_PASSING_FORK})

# Agreement levels between passing forks.
VERIFIED = "verified"
AMBIGUOUS = "ambiguous"
SINGLE = "single"
NONE = "none"

# Named stages where a transaction may call hooks.at(stage). Their order in a run is the order listed,
# with "fork" during the search and "replay" once per replay.
STAGES = ("prepare", "fork", "verify", "merge", "replay", "before_apply", "transplant", "post_verify",
          "before_rollback", "rollback", "release", "report")


@dataclass(frozen=True)
class Capabilities:
    precondition: str  # "atomic", "checked" (a window between check and act), or "none"
    revert: str  # "native", "recorded", "compensating", or "none"
    read_set: str  # "exact", "conservative", or "none"; the engine treats none as conservative
    owner_detection: str  # "required": the engine asks owner() and refuses a live or unknown owner; "none": it does not
    isolation: str  # "namespace", "in_process", or "none"; reported with every result
    time_budgets: tuple = ()  # (operation, seconds) pairs; empty when the adapter declares no time budget


@dataclass(frozen=True)
class Receipt:
    unit: str  # the smallest thing one apply wrote: a file in the file adapter
    landed: Optional[str]  # the fingerprint the real resource holds after the write; None when the unit was removed


class Unreadable(Exception):
    """A unit the adapter cannot decode. The engine refuses; it never treats the unit as unchanged."""


class Adapter(Protocol):
    capabilities: Capabilities
    hooks: "Hooks"  # set by the harness; apply calls hooks.candidate and hooks.window

    def live(self) -> str: ...  # handle of the real resource
    def setup(self) -> None: ...  # reset the test state before a run
    def start_channel(self) -> None: ...  # effect channel: a held effect leaves only through release()
    def stop_channel(self) -> None: ...
    def owner(self, resource: str) -> Any: ...  # None when nothing owns the resource; called only with owner_detection required
    def snapshot(self) -> str: ...  # copy of the live resource that the forks read; the live resource is not changed
    def reset_snapshot(self, root: str) -> None: ...  # make the snapshot a copy of root, for a replay
    def precommit(self) -> str: ...  # copy of the live resource taken at the merge check
    def hashes(self, root: str) -> dict: ...  # fingerprint of every unit under root
    def fingerprint(self, root: str, unit: str) -> Optional[str]: ...
    def anchor(self, root: str, address: str) -> Any: ...  # identity of a unit, found from its address in root
    def resolve(self, anchor: Any, root: str) -> Optional[str]: ...  # current address of an anchor; None when it is gone
    def changed_units(self, before: str, after: str) -> set: ...  # units that differ; raises Unreadable
    def fork(self, name: str, num: int, method: str, results: dict, env: str = "") -> None: ...  # stores into results[name]
    def view(self, name: str) -> str: ...  # read-only view of a fork's result
    def apply(self, unit: str, src_root: str, expect: Optional[str], landed: dict) -> bool: ...  # False if the precondition failed
    def revert(self, unit: str, src_root: str, expect: Optional[str]) -> bool: ...  # False if the precondition failed
    def release(self, effect: dict) -> None: ...  # raises on failure
    def released(self) -> list: ...  # effects the channel has received, in order
    def release_views(self) -> None: ...
    def scratch(self, name: str) -> str: ...  # a directory for the verifier's own copies


class Verifier(Protocol):
    spec: dict  # the frozen spec, as the report records it
    spec_hash: str
    target: str  # the cell the spec is about, as an address the adapter can anchor

    def evaluate(self, base: str, view: str, noise: tuple = ()) -> tuple: ...  # (passed, reasons, changed units)
    def summary(self, base: str, view: str) -> Any: ...  # outcome-level summary, compared between forks
    def self_test(self, base: str, scratch: str) -> dict: ...  # mutation tests; each result has passed and correct


class Hooks(Protocol):
    def plan(self) -> dict: ...  # {"forks": [(name, method), ...], "null": bool}
    def at(self, stage: str, **ctx) -> None: ...  # a scenario may act, or raise, at a named stage
    def candidate(self, unit: str, path: str) -> None: ...  # a transplant candidate, before its precondition check
    def window(self, unit: str) -> None: ...  # between the precondition check and the replace
    def state(self) -> dict: ...  # values of the real resource for the report
