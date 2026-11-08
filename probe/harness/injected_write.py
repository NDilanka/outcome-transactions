"""The injected-write test for records (Vikunja): the same-second blind spot and the window.

The test is planned in browser-probe.md ("Same-second edits"), with predictions written before any
run. This module holds the logic that needs no browser: each case's sequence, whether a sample has
the timing its case needs, the comparison with the predictions, and the split of unsafe arrivals.
run_records.py holds the live side (LiveInjectedOps).

The cases run under amendment A1 (the session refresh passes, every other request is held). Under
the registered policy the page-load refresh POST is held, and it refuses every records release.

Cases:
  A  control. An injected write lands in a different second, after the page's read and before the
     page's rename. The check must see the change and refuse.
  B  same second. An injected write lands after the page's read, in the same second as the last
     write the page saw. The check cannot see it, so the release sends over it.
  C  window. An injected write lands after the check and before the first send (the hook). No check
     can see it.

A sample counts only when its timing matches its case. A missed sample is kept in the output and is
not counted. Errors are recorded, never raised past run_case.
"""

PAGE_TITLE = "Quarterly report v2"  # the R3 rename: the page's goal, and the title the held write sends
INJECTED_A = "Injected A"
INJECTED_B = "Injected B"  # case B, first write: the version the page reads
INJECTED_B_LATE = "Injected C"  # case B, second write: after the page's read, same second
INJECTED_D = "Injected D"  # case C: after the check, before the send
DIFFERENT_SECOND_GAP_S = 2.0
CASES = ("A", "B", "C")
ATTEMPTS = {"A": 1, "B": 3, "C": 1}

PREDICTIONS = {
    "A": {"release": "refused", "sent": 0, "read_back": None, "final_title": INJECTED_A, "hook": False, "goal": True},
    "B": {"release": "released", "sent": 1, "read_back": True, "final_title": PAGE_TITLE, "hook": False, "goal": True},
    "C": {"release": "released", "sent": 1, "read_back": True, "final_title": PAGE_TITLE, "hook": True, "goal": True},
}


def unsafe_split(raw, injector_writes):
    """Page requests that reached the server before release: unsafe arrivals minus the injector's own writes."""
    if injector_writes > raw:
        raise ValueError(f"{injector_writes} injector writes but only {raw} unsafe arrivals")
    return raw - injector_writes


def sample_problem(case, obs):
    """None when the sample has the timing its case needs. Otherwise the reason it does not."""
    if obs.get("error"):
        return "error: " + obs["error"]
    token = obs["release"]["token_used"]
    if token is None:
        return "the held write carried no token"
    injected = obs["injected"]
    if case == "A":
        if len(injected) != 1:
            return "the injected write did not land"
        if injected[0]["updated"] == token:
            return "the injected write landed in the page's second"
        return None
    if case == "B":
        if len(injected) != 2:
            return "the two injected writes did not both land"
        if injected[0]["updated"] != token:
            return "the page did not read the first injected write"
        if injected[1]["updated"] != token:
            return "the second injected write landed in a later second"
        return None
    if case == "C":
        if not obs["hook_ran"]:
            return "the hook did not run between the check and the send"
        if len(injected) != 1:
            return "the injected write did not land"
        if injected[0]["updated"] == token:
            return "the injected write landed in the page's second"
        return None
    return f"unknown case {case}"


def prediction_differences(case, obs):
    """Each way the observed result differs from the prediction. Empty when it matches."""
    pred = PREDICTIONS[case]
    release = obs["release"]
    diffs = []
    if obs["goal_ok"] != pred["goal"]:
        diffs.append(f"page goal reached {obs['goal_ok']}, predicted {pred['goal']}")
    if release["status"] != pred["release"]:
        diffs.append(f"release {release['status']}, predicted {pred['release']}")
    if pred["release"] == "refused" and "version moved" not in release["reasons"]:
        diffs.append(f"refusal reasons {release['reasons']}, predicted 'version moved'")
    if release["sent"] != pred["sent"]:
        diffs.append(f"sent {release['sent']}, predicted {pred['sent']}")
    if pred["read_back"] is not None and obs["read_back_match"] != pred["read_back"]:
        diffs.append(f"read-back {obs['read_back_match']}, predicted {pred['read_back']}")
    if obs["final_title"] != pred["final_title"]:
        diffs.append(f"final title {obs['final_title']!r}, predicted {pred['final_title']!r}")
    if obs["hook_ran"] != pred["hook"]:
        diffs.append(f"hook ran {obs['hook_ran']}, predicted {pred['hook']}")
    if obs["page_unsafe_before_release"] != 0:
        diffs.append(f"{obs['page_unsafe_before_release']} page request(s) reached the server before release")
    return diffs


def _run_once(case, ops):
    obs = {"case": case, "injected": [], "hook_ran": False}
    try:
        obs["reset"] = ops.reset()
        ops.start_page()
        ops.begin_hold()
        if case == "B":
            ops.wait_for_new_second()
            obs["injected"].append(ops.inject(INJECTED_B))
            obs["token_read"] = ops.open_task(on_read=lambda: obs["injected"].append(ops.inject(INJECTED_B_LATE)))
        else:
            obs["token_read"] = ops.open_task()
            if case == "A":
                ops.sleep(DIFFERENT_SECOND_GAP_S)
                obs["injected"].append(ops.inject(INJECTED_A))
        obs["goal_ok"] = bool(ops.rename_on_page())

        def hook():
            obs["hook_ran"] = True
            obs["injected"].append(ops.inject(INJECTED_D))

        obs["release"] = ops.release(before_send=hook if case == "C" else None)
        obs["final_title"] = ops.final_title()
        obs["read_back_match"] = (obs["final_title"] == PAGE_TITLE) if obs["release"]["sent"] else None
        window = ops.window_unsafe()
        obs["unsafe_raw_before_release"] = window["raw"]
        obs["injector_before_release"] = window["injector_before_release"]
        obs["page_unsafe_before_release"] = unsafe_split(window["raw"], window["injector_before_release"])
    finally:
        ops.close()
    problem = sample_problem(case, obs)
    obs["valid"] = problem is None
    obs["invalid_reason"] = problem
    obs["differences"] = prediction_differences(case, obs) if problem is None else []
    return obs


def run_case(case, new_ops):
    """Run one case, up to ATTEMPTS[case] times. new_ops(attempt) gives a fresh ops for each attempt.

    The counted sample is the first valid attempt. Every attempt is returned. matches_prediction is
    true only when a valid sample exists and it has no difference from the prediction.
    """
    if case not in CASES:
        raise ValueError(f"unknown case {case!r}")
    attempts = []
    for number in range(1, ATTEMPTS[case] + 1):
        try:
            obs = _run_once(case, new_ops(number))
        except Exception as err:
            message = (str(err).splitlines() or [""])[0][:200]
            obs = {"case": case, "error": f"{type(err).__name__}: {message}", "valid": False, "invalid_reason": "error", "differences": []}
        obs["attempt"] = number
        attempts.append(obs)
        if obs["valid"]:
            break
    counted = next((a for a in attempts if a["valid"]), None)
    return {
        "case": case,
        "predicted": PREDICTIONS[case],
        "attempts": attempts,
        "counted": counted,
        "matches_prediction": counted is not None and not counted["differences"],
    }
