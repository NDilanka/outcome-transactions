"""Agreement between the COM fork and the openpyxl fork.

Two rules, applied per property and never assumed:
- The openpyxl round trip of the base must keep a property. A property it loses cannot be agreed, so it refuses
  agreement, whether or not the spec checks that property.
- The two forks must produce the same value for every property both can carry.

Both forks must also pass the spec. Commit needs agreement on every property in ALL_PROPS.
"""
import os
import shutil
import tempfile

import openpyxl

from xlsx_props import CELL_PROPS, compare_props, read_props

ALL_PROPS = CELL_PROPS + ("col_width", "csv")


def roundtrip_losses(path):
    """Properties that openpyxl changes when it loads and saves this file with no edits."""
    d = tempfile.mkdtemp(prefix="otx-roundtrip-")
    try:
        out = os.path.join(d, "roundtrip.xlsx")
        openpyxl.load_workbook(path).save(out)
        return compare_props(read_props(path), read_props(out))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _csv(fork):
    path = os.path.join(fork, "out", "q3.csv")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return f.read()


def fork_diffs(fork_a, fork_b):
    """Differences between two forks' budget.xlsx and out/q3.csv."""
    diffs = compare_props(read_props(os.path.join(fork_a, "budget.xlsx")),
                          read_props(os.path.join(fork_b, "budget.xlsx")))
    ca, cb = _csv(fork_a), _csv(fork_b)
    if ca != cb:
        diffs["csv"] = [("out/q3.csv", None if ca is None else len(ca), None if cb is None else len(cb))]
    return diffs


def decide(second_verified, losses, diffs):
    """Returns (outcome, status). status maps every property in ALL_PROPS to agreed, refused, or disagree."""
    status = {}
    for p in ALL_PROPS:
        if p in losses:
            status[p] = "refused"
        elif p in diffs:
            status[p] = "disagree"
        else:
            status[p] = "agreed"
    if not second_verified:
        return "agreement_refused", dict(status, reason="second method failed verification")
    refused = [p for p in ALL_PROPS if status[p] == "refused"]
    if refused:
        return "agreement_refused", dict(status, reason=f"openpyxl round trip loses: {refused}")
    if any(s == "disagree" for s in status.values()):
        return "method_disagreement", status
    return "two_method_agreed", status
