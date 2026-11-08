"""Records (Vikunja) runs for the browser probe: baseline and held runs for R1-R8.

Commands (run from probe/harness or with the path to this file):

  python run_records.py baseline --tasks R1 R2 ...   holds off; one run per task
  python run_records.py held --tasks R1 R2 ...       holds on for the steps; release, then read back
  python run_records.py measure                      GET measurement from the GETs the baseline runs made
  python run_records.py summary                      classify the records runs (records tasks only)

Every run starts with a reset to the seed snapshot (timed as reset_seconds). The
app must be running through the records edge (127.0.0.1:8300) with the edge
control port at 8310. The login is setup: it runs with holds off, before the
steps, and is not counted.

Baseline outcome: completes when the goal shows on the page and the read-back
matches, otherwise fails with a reason.

Held run, fixed before any run:
  - holds are on for the steps only. The page gets no response to any unsafe
    request. The held phase ends when the goal shows, or after 20 s with no
    change on the page.
  - held_outcome completes: the goal shows and the read-back after release matches.
  - held_outcome fails: the goal shows but the read-back differs, or the goal
    does not show and no unsafe request is pending (reason recorded).
  - held_outcome needs_response: the goal does not show and an unsafe request
    is pending. Kinds: POST to a collection (create) is server_id; any other
    unsafe request is other.
  - Then the held requests are released in order (release.py), and the
    read-back is made through a separate API context that the hold workspace
    does not route.

Output: probe/results/raw/records/<phase>.json (ignored by git).
"""

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from playwright.sync_api import sync_playwright  # noqa: E402

import state_snapshot  # noqa: E402
from classify import classify, load_tasks  # noqa: E402
from intercept import HoldWorkspace  # noqa: E402
from policy import GET_RULES, PRIMARY  # noqa: E402

PROBE = HERE.parent
APP = PROBE / "apps" / "vikunja"
RAW = PROBE / "results" / "raw" / "records"
SHOTS = RAW / "screenshots"
DB = APP / "data" / "vikunja.db"
EDGE_LOG = APP / "logs" / "edge.jsonl"
RESET = APP / "reset.mjs"
SECRETS = PROBE / "state" / "secrets.json"
SHELL = (
    Path.home()
    / "AppData"
    / "Local"
    / "ms-playwright"
    / "chromium_headless_shell-1243"
    / "chrome-headless-shell-win64"
    / "chrome-headless-shell.exe"
)
BASE = "http://127.0.0.1:8300"
CONTROL = "http://127.0.0.1:8310"
HOLD_STOP_SECONDS = 20
USER = "alex"
PHASES = ("baseline", "held")


def _policy_commit():
    """Commit that last changed policy.py, and whether the working copy differs from the code run."""
    git = ["git", "-C", str(PROBE)]
    commit = subprocess.run(git + ["log", "-1", "--format=%h", "--", "harness/policy.py"], capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(git + ["status", "--porcelain", "--", "harness/policy.py"], capture_output=True, text=True, check=True).stdout.strip() != ""
    return commit, dirty


POLICY_COMMIT, POLICY_DIRTY = _policy_commit()


def password():
    return json.loads(SECRETS.read_text(encoding="utf-8"))["records"]["alex"]["password"]


def mark(label):
    with urllib.request.urlopen(f"{CONTROL}/mark?label={urllib.parse.quote(label)}", timeout=5) as res:
        res.read()


def reset():
    out = subprocess.run(
        ["node", str(RESET), "restore"], capture_output=True, text=True, timeout=180, cwd=str(PROBE)
    )
    if out.returncode != 0:
        raise RuntimeError("reset failed: " + out.stderr.strip()[-300:])
    return json.loads(out.stdout.strip().splitlines()[-1])["seconds"]


def edge_events():
    if not EDGE_LOG.exists():
        return []
    return [json.loads(line) for line in EDGE_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]


def arrivals_between(start, end):
    """Arrival lines between two markers. Labels are unique per run."""
    events = edge_events()
    i = next(k for k, e in enumerate(events) if e.get("marker") == start)
    j = next(k for k, e in enumerate(events) if e.get("marker") == end and k > i)
    return [e for e in events[i + 1 : j] if e.get("event") == "arrival"]


def unsafe_count(arrivals):
    return sum(1 for a in arrivals if a.get("unsafe"))


def snippet(body, needle):
    idx = body.find(needle)
    if idx < 0:
        return ""
    return body[max(0, idx - 40) : idx + 80].replace("\n", " | ")


def _body(page):
    try:
        return page.inner_text("body")
    except Exception:
        return ""


def _editor_text(page):
    try:
        return page.locator(".tiptap.ProseMirror").last.inner_text().strip()
    except Exception:
        return None


# Task steps: run in the browser. Each one raises if a control is missing.

def login(page):
    page.goto(BASE + "/login")
    page.fill("#username", USER)
    page.fill("#password", password())
    page.keyboard.press("Enter")
    page.wait_for_url(lambda url: "/login" not in url, timeout=15000)
    page.wait_for_load_state("networkidle")


def step_R1(page):
    page.goto(BASE + "/projects/1")
    page.wait_for_load_state("domcontentloaded")
    page.get_by_placeholder("Add a task…").fill("Buy printer paper 2026-11-20")
    page.get_by_role("button", name=re.compile(r"^add$", re.I)).click()


def step_R2(page):
    page.goto(BASE + "/tasks/1")
    page.wait_for_load_state("domcontentloaded")
    page.get_by_role("button", name=re.compile(r"^mark task done", re.I)).click()


def step_R3(page):
    page.goto(BASE + "/tasks/4")
    page.wait_for_load_state("domcontentloaded")
    page.locator("h1").first.click()
    page.keyboard.press("Control+A")
    page.keyboard.type("Quarterly report v2")
    page.keyboard.press("Enter")


def step_R4(page):
    page.goto(BASE + "/tasks/2")
    page.wait_for_load_state("domcontentloaded")
    page.get_by_role("button", name=re.compile(r"add labels", re.I)).click()
    field = page.get_by_placeholder("Type to add a label…")
    # fill() does not open the suggestions; typing key by key does. Pick the existing label,
    # so no new label is created.
    field.click()
    field.press_sequentially("urgent", delay=60)
    page.get_by_role("listbox").locator("button.search-result-button", has_text=re.compile(r"^\s*urgent")).first.click(timeout=10000)


def step_R5(page):
    page.goto(BASE + "/projects/new")
    page.wait_for_load_state("domcontentloaded")
    page.get_by_placeholder("The project's title goes here…").fill("Hiring")
    page.get_by_role("button", name=re.compile(r"^create$", re.I)).click()


def step_R6(page):
    page.goto(BASE + "/tasks/1")
    page.wait_for_load_state("domcontentloaded")
    page.locator(".tiptap.ProseMirror").last.click()
    page.keyboard.type("Checked with Sam")
    page.get_by_role("button", name=re.compile(r"^comment$", re.I)).click()


def step_R7(page):
    page.goto(BASE + "/tasks/6")
    page.wait_for_load_state("domcontentloaded")
    page.get_by_role("button", name=re.compile(r"^delete$", re.I)).click()


def step_R8(page):
    page.goto(BASE + "/tasks/5")
    page.wait_for_load_state("domcontentloaded")
    page.get_by_role("button", name=re.compile(r"^move$", re.I)).click()
    search = page.get_by_placeholder("Type to search for a project…")
    # fill() does not open this multiselect; typing key by key does.
    search.click()
    search.press_sequentially("Home", delay=60)
    # The option's text is "Home" followed by a hint, with no space between them.
    page.get_by_role("listbox").locator("button.search-result-button", has_text=re.compile(r"^\s*Home")).first.click(timeout=10000)


# Goals: what the page must show. Each returns (ok, evidence).

def goal_R1(page):
    # Vikunja lists show a relative due date. "Due in N days" with N counted to 20 Nov 2026
    # from today's local date is the list's form of that due date.
    body = _body(page)
    days = (date(2026, 11, 20) - date.today()).days
    ok = "Buy printer paper" in body and f"Due in {days} days" in body
    return ok, snippet(body, "Buy printer paper")


def goal_R2(page):
    ok = page.get_by_role("button", name=re.compile("undone", re.I)).count() > 0
    return ok, "undone button shown" if ok else "no undone button"


def goal_R3(page):
    title = page.locator("h1").first.inner_text().strip()
    return title == "Quarterly report v2", title


def goal_R4(page):
    # The label chip on the task, not the suggestion list.
    chips = page.get_by_text("urgent", exact=True).evaluate_all("els => els.filter(e => !e.closest('[role=listbox]')).length")
    ok = chips > 0
    return ok, "urgent label shown" if ok else "no urgent label"


def goal_R5(page):
    ok = page.get_by_text("Hiring", exact=True).count() > 0
    return ok, "Hiring shown" if ok else "Hiring not shown"


def goal_R6(page):
    body = _body(page)
    ok = page.get_by_text("Checked with Sam").count() > 0 and _editor_text(page) == ""
    return ok, snippet(body, "Checked with Sam")


def goal_R7(page):
    body = _body(page)
    ok = "/projects/1" in page.url and "Old test item" not in body
    return ok, page.url


def goal_R8(page):
    # The task page's breadcrumb links to project Home (/projects/3) outside the sidebar.
    # The sidebar always lists Home, so the sidebar link does not count.
    body = _body(page)
    links = page.locator("a[href='/projects/3']").evaluate_all("els => els.map(e => !e.closest('aside'))")
    ok = "/tasks/5" in page.url and any(links)
    return ok, snippet(body, "Book venue")


STEPS = {"R1": step_R1, "R2": step_R2, "R3": step_R3, "R4": step_R4, "R5": step_R5, "R6": step_R6, "R7": step_R7, "R8": step_R8}
GOALS = {"R1": goal_R1, "R2": goal_R2, "R3": goal_R3, "R4": goal_R4, "R5": goal_R5, "R6": goal_R6, "R7": goal_R7, "R8": goal_R8}


# Read-backs: answered by the server through a separate API context. Each returns (ok, detail).

def _items(api, path):
    res = api.get(path)
    return res.json()["items"] if res.ok else []


def readback_R1(api):
    # The server stores the due instant in UTC. Compare the date in the machine's local time zone.
    tasks = _items(api, "/api/v2/projects/1/tasks?per_page=100")
    hits = [t for t in tasks if t.get("title") == "Buy printer paper"]
    local = None
    if hits and hits[0].get("due_date"):
        local = datetime.fromisoformat(hits[0]["due_date"]).astimezone().date()
    ok = len(hits) == 1 and local == date(2026, 11, 20)
    return ok, {"matches": len(hits), "due_local_date": local.isoformat() if local else None}


def readback_R2(api):
    task = api.get("/api/v2/tasks/1").json()
    return task.get("done") is True, {"done": task.get("done")}


def readback_R3(api):
    task = api.get("/api/v2/tasks/4").json()
    return task.get("title") == "Quarterly report v2", {"title": task.get("title")}


def readback_R4(api):
    task = api.get("/api/v2/tasks/2").json()
    names = [label.get("title") for label in (task.get("labels") or [])]  # null when the task has no labels
    return "urgent" in names, {"labels": names}


def readback_R5(api):
    projects = _items(api, "/api/v2/projects?per_page=100")
    hits = [p for p in projects if p.get("title") == "Hiring" and p.get("parent_project_id", 0) == 0]
    return len(hits) == 1, {"matches": len(hits)}


def readback_R6(api):
    comments = _items(api, "/api/v2/tasks/1/comments?per_page=100")
    hits = [c for c in comments if "Checked with Sam" in str(c.get("comment", ""))]
    return len(hits) == 1, {"matches": len(hits), "comments": len(comments)}


def readback_R7(api):
    tasks = _items(api, "/api/v2/projects/1/tasks?per_page=100")
    return not any(t.get("title") == "Old test item" for t in tasks), {"inbox_tasks": len(tasks)}


def readback_R8(api):
    task = api.get("/api/v2/tasks/5").json()
    return task.get("project_id") == 3, {"project_id": task.get("project_id")}


READBACK = {"R1": readback_R1, "R2": readback_R2, "R3": readback_R3, "R4": readback_R4, "R5": readback_R5, "R6": readback_R6, "R7": readback_R7, "R8": readback_R8}


def api_login(playwright):
    anon = playwright.request.new_context(base_url=BASE)
    res = anon.post("/api/v2/login", data={"username": USER, "password": password(), "long_token": False})
    token = res.json()["token"]
    anon.dispose()
    return playwright.request.new_context(base_url=BASE, extra_http_headers={"Authorization": f"Bearer {token}"})


def kind_for(method, path):
    if method == "POST" and re.fullmatch(r"/api/v2/(projects|labels|projects/\d+/tasks|projects/\d+/tasks/bulk|tasks/\d+/comments)", path):
        return "server_id"
    return "other"


def wait_for_goal(page, goal):
    """Poll until the goal shows, or 20 s pass with no change on the page."""
    last_sig, last_change = None, time.monotonic()
    while True:
        ok, evidence = goal(page)
        if ok:
            return True, evidence
        sig = page.url + "|" + _body(page)[:4000]
        if sig != last_sig:
            last_sig, last_change = sig, time.monotonic()
        if time.monotonic() - last_change >= HOLD_STOP_SECONDS:
            return False, evidence


def run_one(playwright, task, phase, attempt, nonce):
    tag = f"{phase}-{task}-{attempt}-{nonce}"
    seconds_reset = reset()
    started = time.monotonic()
    ws = HoldWorkspace(PRIMARY)
    ws.holding = False
    browser = playwright.chromium.launch(headless=True, executable_path=str(SHELL))
    record = {"task": task, "attempt": attempt, "phase": phase, "tag": tag, "reset_seconds": seconds_reset, "policy_commit": POLICY_COMMIT, "policy_dirty": POLICY_DIRTY}
    try:
        context = browser.new_context()
        ws.attach(context)
        page = context.new_page()
        mark(f"setup-start-{tag}")
        login(page)
        mark(f"setup-end-{tag}")

        ws.holding = phase == "held"
        mark(f"{phase}-start-{tag}")
        steps_error = None
        try:
            STEPS[task](page)
        except Exception as err:  # the step's own error, recorded as the reason
            steps_error = f"{type(err).__name__}: {str(err).splitlines()[0][:200]}"
        record["steps_error"] = steps_error
        goal_ok, evidence = wait_for_goal(page, GOALS[task])
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"{tag}-before-release.png"))
        pending = [{"seq": h.seq, "method": h.method, "path": urllib.parse.urlsplit(h.url).path} for h in ws.held]

        if phase == "baseline":
            mark(f"baseline-end-{tag}")
            record["outcome"] = "completes" if goal_ok else "fails"
            if not goal_ok:
                record["fail_reason"] = steps_error or f"goal not shown: {evidence}"
            record["held_guard"] = "holds off"
        else:
            if goal_ok:
                candidate = "completes"
            elif pending:
                candidate = "needs_response"
            else:
                candidate = "fails"
            record["held_candidate"] = candidate
            record["pending_held"] = pending
            if candidate == "needs_response":
                kinds = []
                for item in pending:
                    kind = kind_for(item["method"], item["path"])
                    if kind not in kinds:
                        kinds.append(kind)
                record["needs_response"] = kinds
            if candidate == "fails":
                record["fail_reason"] = steps_error or f"goal not shown and no unsafe request pending: {evidence}"
            mark(f"held-end-{tag}")
            mark(f"release-start-{tag}")
            release = ws.release(current_token=lambda h: None)
            record["release"] = release.as_dict()
            mark(f"release-end-{tag}")
            time.sleep(1.0)
            record["unsafe_before_release"] = unsafe_count(arrivals_between(f"held-start-{tag}", f"release-start-{tag}"))
            # Held requests the page made after the unit was released; they are not part of the unit.
            record["held_left_after_release"] = len(ws.held)
            record["held_outcome"] = candidate
            record["goal_during_hold"] = bool(goal_ok)
            record["gets_held"] = sorted(ws.gets_held)
            record["faked_response"] = False
            record["native_draft_used"] = False
            record["counts_during_steps"] = dict(ws.counts)
            record["evidence"] = evidence

        # Read-back: through a separate API context, after the page is closed, so the page
        # cannot send anything during the read-back window.
        context.close()
        counts_before = dict(ws.counts)
        api = api_login(playwright)
        mark(f"readback-start-{tag}")
        try:
            rb_ok, rb_detail = READBACK[task](api)
        except Exception as err:  # a failed read-back is a mismatch, recorded with its reason
            rb_ok, rb_detail = False, {"error": f"{type(err).__name__}: {str(err).splitlines()[0][:160]}"}
        mark(f"readback-end-{tag}")
        api.dispose()
        record["read_back_match"] = bool(rb_ok)
        record["read_back_detail"] = rb_detail
        record["readback_routed_by_workspace"] = dict(ws.counts) != counts_before

        if phase == "baseline":
            record["read_back_check"] = "match" if rb_ok else "mismatch"
            if goal_ok and not rb_ok:
                record["outcome"] = "fails"
                record["fail_reason"] = "read-back mismatch"
            # Steps and goal wait only. The read-back login and read-back GET come after baseline-end.
            record["unsafe_arrivals_in_steps"] = unsafe_count(arrivals_between(f"baseline-start-{tag}", f"baseline-end-{tag}"))
            record.setdefault("gets_held", [])
        else:
            if record.get("release", {}).get("sent"):
                # release_unit leaves verified empty here; the read-back above is the verification.
                record["release"]["verified"] = bool(rb_ok)
            if candidate == "completes" and not rb_ok:
                record["held_outcome"] = "fails"
                record["fail_reason"] = "read-back mismatch after release"
            record["seconds"] = round(time.monotonic() - started, 2)
        record["seconds"] = round(time.monotonic() - started, 2)
        record["get_seen"] = [
            {"method": k[0], "path": k[1], "query_keys": list(k[2]), "url": url} for k, url in ws.get_seen.items()
        ]
    finally:
        browser.close()
    return record


def write_phase(phase, records):
    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / f"{phase}.json"
    existing = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    keep = [r for r in existing if not any(r["task"] == n["task"] and r["attempt"] == n["attempt"] for n in records)]
    out.write_text(json.dumps(keep + records, indent=2), encoding="utf-8")
    return out


def run_phase(phase, tasks, attempt=1):
    nonce = time.strftime("%H%M%S")
    out = None
    with sync_playwright() as playwright:
        for task in tasks:
            record = run_one(playwright, task, phase, attempt, nonce)
            out = write_phase(phase, [record])  # saved per task, so a later error keeps earlier results
            summary = record.get("outcome") or record.get("held_outcome")
            print(json.dumps({"task": task, "phase": phase, "result": summary, "reset_seconds": record["reset_seconds"], "seconds": record.get("seconds")}))
    return out


def measure():
    """Measure every distinct GET the baseline runs made, each from a fresh reset."""
    candidates = {}
    for name in PHASES:
        path = RAW / f"{name}.json"
        if not path.exists():
            continue
        for run in json.loads(path.read_text(encoding="utf-8")):
            for item in run.get("get_seen", []):
                key = (item["method"], item["path"], tuple(item["query_keys"]))
                candidates.setdefault(key, item["url"])
    token = {"value": None}
    files_root = APP / "data" / "files"

    def files_state():
        if not files_root.exists():
            return []
        return sorted(f"{p.relative_to(files_root).as_posix()}:{p.stat().st_size}" for p in files_root.rglob("*") if p.is_file())

    file_diffs = {}

    def replay_tracked(url):
        # Files the app writes outside the database (attachments, avatars) are compared too.
        before = files_state()
        status = replay(url)
        after = files_state()
        file_diffs[url] = sorted([x for x in after if x not in before] + ["removed " + x for x in before if x not in after])
        return status

    def reset_and_login():
        reset()
        body = json.dumps({"username": USER, "password": password(), "long_token": False}).encode()
        req = urllib.request.Request(BASE + "/api/v2/login", data=body, headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as res:
            token["value"] = json.loads(res.read())["token"]

    def replay(url):
        headers = {"Authorization": f"Bearer {token['value']}"} if url.startswith(BASE + "/api/") else {}
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                res.read()
                return res.status
        except urllib.error.HTTPError as err:
            return err.code

    db = str(DB)
    exclude = state_snapshot.EXCLUDED_TABLES["vikunja"]
    results = []
    control = state_snapshot.measure_get(db, exclude, BASE + "/__control_no_request", reset_and_login, lambda url: 0)
    # The reset removes data/files, so with no request made, any file left is drift.
    control_files = bool(files_state())
    results.append({"method": "CONTROL", "path": "(no request)", "query_keys": [], "status": 0, "state_changing": control["state_changing"] or control_files, "changed_tables": control["changed_tables"], "files_changed": control_files, "policy_commit": POLICY_COMMIT, "policy_dirty": POLICY_DIRTY})
    for (method, path, keys), url in sorted(candidates.items()):
        out = state_snapshot.measure_get(db, exclude, url, reset_and_login, replay_tracked)
        files_changed = file_diffs.get(url, [])
        results.append({"method": method, "path": path, "query_keys": list(keys), "status": out["status"], "state_changing": out["state_changing"] or bool(files_changed), "changed_tables": out["changed_tables"], "files_changed": files_changed, "policy_commit": POLICY_COMMIT, "policy_dirty": POLICY_DIRTY})
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "get-measure.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    rules_names = [rule.name for rule in GET_RULES]
    return {"measured": len(results) - 1, "control_state_changing": results[0]["state_changing"], "state_changing": [r["method"] + " " + r["path"] for r in results if r["state_changing"] and r["method"] != "CONTROL"], "rules_in_policy": rules_names}


def summary():
    tasks = {t: v for t, v in load_tasks().items() if v["app"] == "records"}
    runs = {
        "baseline": json.loads((RAW / "baseline.json").read_text(encoding="utf-8")),
        "held": json.loads((RAW / "held.json").read_text(encoding="utf-8")),
    }
    result = classify(tasks, runs)
    result["policy_commit"] = POLICY_COMMIT
    result["policy_dirty"] = POLICY_DIRTY
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vikunja records runs for the browser probe.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in PHASES:
        p = sub.add_parser(name)
        p.add_argument("--tasks", nargs="+", required=True)
    sub.add_parser("measure")
    sub.add_parser("summary")
    args = parser.parse_args(argv)
    if args.command in PHASES:
        out = run_phase(args.command, args.tasks)
        print(json.dumps({"wrote": str(out)}))
    elif args.command == "measure":
        print(json.dumps(measure(), indent=2))
    else:
        print(json.dumps(summary(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
