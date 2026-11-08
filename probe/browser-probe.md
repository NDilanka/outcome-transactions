# Browser feasibility probe

Status: records block run. Vikunja (R1 to R8) ran in baseline and held modes, then
was stopped and its runtime data removed. Mail (Mailpit with the webmail stub) and
checkout (with the payment provider) have not run. Nothing is running now. The K1
rule and the task list are unchanged from the frozen version. The next runs wait for
the orchestrator's go-ahead.

## Question

Can real web write tasks finish inside a private browser workspace while every
state-changing request is held, and then be released as one verified unit?

The answer decides kill criterion K1.

## Kill criterion K1

Roadmap text: "If fewer than half of the probe's write tasks finish with requests
held (no faked responses, no drafts), drop generic browser writes."

How this probe applies it. The orchestrator fixed the counting rule before any run:

- Denominator: the 24 write tasks in `probe/tasks.json`.
- A task counts in the numerator only when its measured held run meets every
  condition below:
  - `held_outcome` is `completes`
  - `faked_response` is false (the harness did not answer a page itself)
  - `native_draft_used` is false (the saved draft or quote was not used)
  - the task is not `native_draft_required`
  - `unsafe_before_release` is 0 (no unsafe request reached the server early)
  - `read_back_match` is true
- K1 triggers when the numerator is below 12, which is half of 24. Twelve of 24
  does not trigger it.
- The highest possible numerator is 21. M3, M4 and S6 are `native_draft_required`:
  their goal is the saved draft or quote itself, so they cannot count.
- Each task row lists every condition that failed. `faked_response` and
  `native_draft_used` are separate fields, and each one also appears in the
  exclusion list when it is true.
- Attempt 1 is the measured held run and the only one that counts. A retry is
  recorded in the output and never changes the numerator.
- Baseline runs (holds off) cover all 24 tasks. They do not change the numerator.
- Held phase completes is a second number, labelled, reported beside K1. It counts
  the tasks whose page reached its goal with every unsafe request held, before
  release. It separates whether holding works from whether release can be
  verified. It does not change K1: a task whose release is refused, or whose
  read-back does not match, still fails K1 when its held phase completes.

Two K1 numbers are reported, one per GET policy (see "GET policy" below):

- Primary: every GET measured to change state is held, and so is every GET the
  registered policy holds until it is measured. The primary number is the K1
  reading.
- Sensitivity: the same, except GETs whose measured effect is reversible and
  low-stakes may pass. Reported beside the primary number and labelled. The payment
  return never passes in either.

Sensitivity scope: the two policies differ only on GETs that the sensitivity policy
passes. So a sensitivity held run is needed only for the tasks whose primary held
run recorded such a GET in `gets_held`. Those are the scope tasks. Every other task
copies its primary row into the sensitivity table, marked `copied_from_primary`.
Its counted result is therefore the primary result, not a second measurement.
Copied rows add no time to the timing totals.

This text replaces an earlier reading that counted tasks which completed by saving
a draft. That reading is withdrawn.

Calculation: `python probe/harness/classify.py --runs <runs.json>` prints the
per-task rows, both K1 summaries, and the timing totals. It stops with an error on
incomplete input: a missing measured run, a missing baseline, a missing sensitivity
run for a scope task, a sensitivity run for a task outside the scope, an unknown
task, a GET rule name that is unknown or belongs to another app, or a field with a
bad value.

## Definitions

Each task gets these fields for its measured held run.

`held_outcome`, one of:

- completes: the goal is reached on the page while every unsafe request is still
  held and no server response has reached the page. The release read-back must
  also match the intended effect.
- needs_response: the page cannot reach the goal without a server response. The
  run records each response it needed, from this list: `server_id`,
  `csrf_rotation`, `validation_result`, `payment_redirect`, `held_get_content`,
  `other`.
- fails: the goal is not reached, and the cause is not a missing response (a
  selector that cannot be found, an app error that also appears with holds off).
  Each fail gets a reason.

`native_draft_available`: yes when the app offers a saved, not-final record of the
write (a draft message or a saved quote). Carts and orders are not drafts.

`native_draft_required`: yes when the goal cannot be reached without that saved
record. Such a task cannot count for K1.

`native_draft_used`: recorded per run. Yes when the run touched the draft or quote
feature at any point. Such a run cannot count for K1.

`gets_held`: recorded per held run. The names of the GET rules that held a request
during that run. It sets the sensitivity scope, and the classifier checks each name
against the rule's app.

`faked_response`: yes when the harness answered a page with a response the server
did not send. The harness never does this. No code in `probe/harness` calls
`route.fulfill`, and a unit test checks that. The field is still recorded for
every run.

Baseline: each task also runs once with holds off. The baseline tells a fail apart
from a task the app cannot do at all.

## Method

Workspace: one Playwright Chromium context per task. Each context has a fresh
profile with no saved logins. The user's browser profiles are not used.

Origins: the browser may reach only the probe's own origins: the checkout edge
(127.0.0.1:8100), the webmail edge (127.0.0.1:8200), the records edge
(127.0.0.1:8300), and the payment provider page (127.0.0.1 and localhost on port
8102). Any other origin is blocked. The Mailpit UI is not a browser origin.

Holds (`probe/harness/policy.py`):

- Every non-GET request to a probe origin is held. HEAD and OPTIONS pass.
- GETs are held only through `GET_RULES`. Each rule has a name, the app it
  applies to, a path and query predicate, and two flags: `primary_hold` and
  `sensitivity_pass`. A held request gets no response. The page waits. Release
  relays the server's own response. Discard aborts the request, which the page
  sees as a network error.

GET policy (set from measurement, not from guesses):

- Before measurement, the three registered GETs stay held in both policies:
  webmail opening a message (`/message/<id>`), webmail reply compose
  (`/compose?reply=`), and the checkout payment return (`/checkout/return`).
- Each GET that the baseline edge log shows is measured (see "GET measurement").
  A GET that measures state-changing is held in the primary policy. A
  registered GET that measures unchanged passes in both policies.
- The sensitivity policy passes only GETs whose changed tables are reversible and
  low-stakes, for example a read flag. The rule records the evidence.
- The payment return (S7) stays held in both policies. Code enforces this, because
  it finalises a payment.

Consequence for the numbers: opening a message (M2, M5) and the reply compose page
(M2) are held GETs under the registered policy. If they change state, the page
stalls until release, which is the probe's test of GET side effects. If they do
not change state, they pass in both policies and the task runs normally. The
measurement decides which case applies.

GET measurement (`probe/harness/state_snapshot.py`, `measure_get`):

1. Every distinct GET in the baseline edge log is listed (path and query key names).
2. Each GET is measured from a freshly reset database, never from the state left
   by an earlier GET. Otherwise a GET that marks a message read would look harmless
   on the second measurement.
3. Snapshot: every table in the app's SQLite database is hashed (rows read in full
   and sorted). Housekeeping tables are excluded: `sessions` for webmail and
   checkout. The Vikunja list is set from the live database before the first
   measurement.
4. The GET is replayed with the baseline session. The status is recorded.
5. Snapshot again. The GET is state-changing when any non-excluded table differs.
   The result names the changed tables.

Server-side evidence: each app sits behind a logging edge
(`probe/apps/common/edge-log.mjs`). The edge writes an `arrival` line when a
request reaches it and a `done` line when the app has answered. Lines carry method,
path, query key names, the unsafe flag, and for `done` the status and duration. No
cookies, tokens or bodies are logged. The run writes phase markers (setup,
held, release) to a control port. A held request never reaches the edge, so every
unsafe arrival is a request the browser policy let through. The held phase passes
only when the edge shows zero unsafe arrivals between the held and release
markers. That count is `unsafe_before_release`.

Release (`probe/harness/release.py`, `probe/harness/intercept.py`):

1. Check: each held request must carry a version token, and that token is
   compared with the current server version. The token is an If-Match header or
   a version form field in the request, or else the `updated` value the page
   itself read for the request's task (`probe/harness/version_read.py`). The
   current version is read fresh, through the adapter's own request context (not
   routed), just before the sends. A request with no token is refused ("no
   precondition available"), so it never passes silently. A mismatch ("version
   moved") or an unreadable version ("current version unreadable") is refused
   too. Any refusal refuses the whole unit. Nothing is sent, and the held requests
   stay pending.
2. Send: held requests are continued in their original order. The first
   rejection (status 400 or more, or no status) stops the release. The unit is
   then partial. For each sent request the release records the read-to-apply
   gap: `check_to_send_s`, the time from its check to the start of its send, and
   `check_to_response_s`, the time from its check to its response. The checks of
   a unit all run before its first send, so a later request's gap includes the
   sends before it. Every release record has a `gaps` list, empty when refused.
3. Read back: a GET after release compares the server state with the intended
   effect. The unit is verified only when they match. The read-back runs outside
   the hold workspace (a separate request context, not routed), so it is never held
   and never appears in `gets_held`.

The server still applies its own checks when a request is sent. The check in
step 1 runs first, so a concurrent edit is refused before anything is sent. A
small gap remains between step 1 and the server check. The run reports it.

Reset between runs: every run, baseline and held, starts from the seed state. The
baseline writes change what a held run would see. Each run records
`reset_seconds`, the time to reset the app and seed it. The totals are reported
separately from run time. The adapter will pay the same reset cost.

Timing: each task records wall-clock time from the first step to the goal (or
to the stop rule) as `seconds`. Stop rule: the held phase ends when the goal is
reached or when 20 seconds pass with no change on the page.

Retries: one measured run per task (attempt 1). Any retry is a separate recorded
run and does not count.

## Apps and realism

Real upstream software: Vikunja v2.8.0 (records) and Mailpit v1.33.1 (the mail
server behind the webmail stub). Ours: the webmail stub, the checkout store and
the payment provider. These are stand-ins, not products. Start commands are in
`probe/apps/*/NOTES.md`.

| Feature | Vikunja (records) | Webmail stub (ours) | Checkout store (ours) |
| --- | --- | --- | --- |
| Login session | Bearer JWT, short token lifetime 600 s (our config); refreshed on page load | Session id rotated at login | Session id rotated at login |
| CSRF token on unsafe forms | Not applicable: the credential is a Bearer header, not a cookie | Yes, every form | Yes, every form; the admin JSON API needs `x-csrf-token` |
| Version field in forms | No | `draft_version`, `settings_version` (409 on stale) | `cart_version`, `address_version`, product `version` (409 on stale) |
| ETag and If-Match | ETag on single-resource GET (`"<UnixNano of updated>-<permission>"`); If-Match not enforced on PATCH (checked live) | No | Admin JSON API only (428 without If-Match, 412 on mismatch) |
| Idempotency-Key | No handling in the v2.8.0 backend (source search) | No | On order creation and on payment and refund calls |
| Server-generated ids | Yes | Yes (Mailpit ids) | Yes |
| Validation errors | 422 with an `errors` list (documented) | 422 page | 422 page |
| GET that changes state | None of 158 measured (Vikunja) | Measure: opening a message, opening a reply | Yes: the payment return |
| Payment by redirect | No | No | Yes, to the provider's hosted page |
| Sends mail | No | Yes, by SMTP to Mailpit | No |

What each app lacks:

- Vikunja: no version counter (the ETag and the `updated` time are the only
  version tokens). The server does not enforce If-Match on PATCH, and the UI sends
  no token. No idempotency key. Session expiry, rate limits and HTTPS are not
  exercised here.
- Webmail stub: no IMAP, attachments, HTML mail, push or filters. Moves and
  archive carry no version token, so concurrent edits are not detected for
  them. Sending has no idempotency key.
- Checkout store: no card processing, webhooks, tax, shipping rules, receipts or
  inventory. The promo form carries no version token. No session expiry or rate
  limits.
- Payment provider: no card network, 3-D Secure or webhooks. It does have bearer
  keys, idempotency keys with conflict checks, a hosted page token, a Luhn check
  and a decline card (ending 0002).

## Frozen task list

Full text, setup, steps and intended effects are in `probe/tasks.json`. Eight
tasks per app. Irreversible writes (mail sent, payment taken) are HOLD by
default and are marked here.

| ID | App | Task | Irreversible | native_draft available | native_draft required |
| --- | --- | --- | --- | --- | --- |
| R1 | Vikunja | Create a task in Inbox | no | no | no |
| R2 | Vikunja | Mark a task done | no | no | no |
| R3 | Vikunja | Rename a task | no | no | no |
| R4 | Vikunja | Add a label to a task | no | no | no |
| R5 | Vikunja | Create a project | no | no | no |
| R6 | Vikunja | Comment on a task | no | no | no |
| R7 | Vikunja | Delete a task | no | no | no |
| R8 | Vikunja | Move a task to another project | no | no | no |
| M1 | Webmail | Send a new message | yes | yes | no |
| M2 | Webmail | Reply to a message | yes | yes | no |
| M3 | Webmail | Save a new draft | no | yes | yes |
| M4 | Webmail | Update a saved draft | no | yes | yes |
| M5 | Webmail | Archive a message | no | no | no |
| M6 | Webmail | Create a folder | no | no | no |
| M7 | Webmail | Add a contact | no | no | no |
| M8 | Webmail | Change the display name | no | no | no |
| S1 | Checkout | Add an item to the cart | no | no | no |
| S2 | Checkout | Change an item quantity | no | no | no |
| S3 | Checkout | Apply a promo code | no | no | no |
| S4 | Checkout | Remove an item | no | no | no |
| S5 | Checkout | Change the shipping address | no | no | no |
| S6 | Checkout | Save the cart as a quote | no | yes | yes |
| S7 | Checkout | Place an order and pay | yes | no | no |
| S8 | Checkout | Admin changes a product price | no | no | no |

Eligible for K1: 21 tasks. Not eligible by construction: M3, M4, S6.

## Results

### Records (Vikunja): block run

Status: the held rows are superseded. They were released before the read-compare existed, and that release compared nothing. A held write with no version token passed a check of None against None and was reported as "checks ok". So the release statuses are server answers, not verified releases. The held rows stay in the record and are not deleted. The baseline rows stand, since a baseline run makes no release. The held runs will be rerun under the read-compare after the go-ahead. The bug and the fix are in "Release precondition for records".

One reset to seed before every run. Each task has a baseline run (holds off) and a primary held run. Policy commit c393905, working copy clean, stamped in every record. The final harness was run twice and gave the same outcomes. Raw rows are in `probe/results/raw/records/` (git-ignored): `baseline.json`, `held.json`, `summary.json`, `get-measure.json`, the edge logs, and before-release screenshots.

| Task | Baseline (holds off) | Held (primary, superseded) | Requests left pending while held | Release statuses (superseded, unchecked) | Read-back | Unsafe before release | Held left after release |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R1 create task | completes | needs_response | refresh POST, bulk create | 200, 201 | match (1 task, due 2026-11-20) | 0 | 0 |
| R2 mark done | completes | needs_response | refresh POST, PATCH task 1 | 200, 200 | match (done) | 0 | 0 |
| R3 rename | completes | completes | refresh POST, PATCH task 4 | 200, 200 | match (new title) | 0 | 0 |
| R4 add label | completes | completes | refresh POST, label POST | 200, 201 | match (urgent) | 0 | 0 |
| R5 create project | completes | needs_response | refresh POST, project POST | 200, 201 | match (1 project) | 0 | 0 |
| R6 comment | completes | needs_response | refresh POST, comment POST | 200, 201 | match (1 comment) | 0 | 0 |
| R7 delete | completes | needs_response | refresh POST, DELETE task 6 | 200, 204 | match (0 left in Inbox) | 0 | 0 |
| R8 move | completes | needs_response | refresh POST, PATCH task 5 | 200, 200 | match (project 3) | 0 | 0 |

Points to note:

- Baseline: 8 of 8 complete, and every read-back matches. Each baseline run had two unsafe requests in its step window: the page-load refresh POST and the task write. That is what the page sends. It is not a held-run count.
- Held (superseded): each held request was sent in order after release and got the server's own answer. No response was faked and no draft feature was used. Nothing was left held after release. But the release compared nothing, so these releases are not verified, and the read-backs above do not make them verified.
- The six needs_response runs ended on the 20-second no-change stop rule (about 25 s each).
- The `needs_response` kinds in the JSON (`server_id`, `other`) come from every request left pending, including the refresh. They do not show what the page waited for. The next section does.
- Phase counts (pass, hold, block per run) are in `held.json` under `counts_during_steps`.

Records numbers. Both are superseded for K1 purposes, and both wait for the rerun:

- Held phase completes, from the superseded run: 2 of 8 (R3 and R4). The page reached its goal with everything held. This does not depend on the release, so it is recorded as observed. It is not a K1 count.
- K1, from the superseded run: 2 of 8 counted (R3 and R4), and 2 of 8 for sensitivity (no scope tasks, all rows copied from primary). These counts depend on releases that compared nothing. They stay as the record of that run, not as K1 evidence.
- Expected under the read-compare, from the code, not run: every records unit is refused, so R3 and R4 fail at read-back and the K1 count is 0 of 8. The cause is the session refresh POST, which names no task and so has no precondition (see "Release precondition for records"). Held phase completes should stay 2 of 8, since holding does not change with the release check.
- K1 is defined over 24 write tasks, with the trigger below 12. Records is one app of three. It does not decide K1.

GET measurement (Vikunja):

- 158 distinct GETs in the baseline and held logs. Each was measured from a fresh reset. None changed a table or a file.
- Control (no request): no change.
- Positive control: one `POST /api/v2/labels` changed the `labels` table with the same detector. That check was a scratch script in `probe/state/` and is not committed.
- No Vikunja GET rule is needed, so `GET_RULES` is unchanged.

Timing (16 task runs, 8 baseline and 8 held):

- Reset: 18.1 s in total, 0.97 to 1.5 s per run.
- Run: 196.5 s in total. The run includes the held phase.
- Reset and run times are reported separately.

Harness fixes made before the final run (earlier attempts were overwritten and are not counted):

- The project and label pickers open only on typed keys. The steps now type, then click the result.
- Network-idle waits never finish while requests are held. Steps wait for `domcontentloaded`.
- The R8 goal could pass on the sidebar Home link. It now checks the breadcrumb.
- A read-back crashed on `labels: null`. Fixed.
- Bulk create was counted as another request kind. Fixed.
- The baseline unsafe window included the read-back login. Fixed.

Not run yet: mail, checkout, the release demo, and the release gap measurement (below).

## What each needs_response page waited for

Sources: the held-run records (pending requests, release statuses, goal state), the before-release screenshots, and the Vikunja v2.8.0 frontend source (tag v2.8.0). "Observed" means the run record or a screenshot shows it. "Source" means the code shows it. No answer was faked. The consequences marked source were read from code and not run.

| Task | What the page waited for | Basis | Could the harness continue without it? |
| --- | --- | --- | --- |
| R1 create | The created task, echoed back in a list of the same length as the request. The page adds the task from that list. | Observed: add button spinning, new task not listed. Source: the bulk create checks the list length, and the caller reads each task from it. | No. A body-less 2xx fails the length check, and the caller restores the typed title (source). |
| R2 mark done | The updated task, echoed back. The done control reads the merged response. | Observed: no undone control while held. Source: `toggleTaskDone` calls `saveTask`, which merges the response. | No. A body-less 2xx keeps done false on screen (source). |
| R5 create project | The created project. The page navigates to its id and adds it to the project list. | Observed: New project dialog open, spinner on Create. Source: `NewProject.vue` routes to `created.id` after the call. | No. Navigation needs the id, and the list needs the object (source). |
| R6 comment | The created comment, echoed back. The editor clears and the comment joins the list only after the response. | Observed: "Creating comment..." with the text still in the editor. Source: `addComment` clears after the call, and the success handler reads the response. | No. A body-less success fails in the success handler, so the editor keeps the text (source). |
| R7 delete | Success status only. The page routes away after any 2xx and does not read the body. | Observed: the URL stayed on `/tasks/6` while held. Source: `deleteTask` awaits the call, then routes. | Status only. A 202 "accepted, pending" would unblock the page, but the task would show as gone before the server removed it. |
| R8 move | The updated task, echoed back. The project shown in the breadcrumb and page state comes from the response. | Observed: breadcrumb still "Work" while held. Source: `changeProject` calls `saveTask`, which merges the response. | No. A body-less 2xx keeps the old project on screen (source). |

What this means for adapter design. A bare pending answer with no body would not unblock R1, R2, R5, R6 or R8. R1, R5 and R6 would fail, and R2 and R8 would resolve but show the old state. Only R7 would unblock on a pending 202, and the page would then show a deletion the server had not made. The contract therefore needs the echoed object for creates, comments, done and moves. A pending state the page can show is a different design. The probe has not tested one. None of these six counts toward K1.

## Release precondition for records (Vikunja)

Verified facts:

- The server does not enforce If-Match on task writes. Live: a PATCH with a stale If-Match returned 200 and applied the change. Source: the v2.8.0 backend has no If-Match handler.
- The UI sends no version token. Source: no non-generated frontend code sets If-Match, and `taskWriteBody` has no version field. Observed: none of the 16 held writes carried a token.
- The usable token is `updated`. It is in the task's GET body and inside the ETag, `"<UnixNano of updated>-<permission>"`. The API marks `updated` read-only, so the server ignores it on write.

So the only check is a read. The release reads the task's `updated` just before it sends the held write, and compares it with the value the page read for that task. If they differ, the release refuses. This is built offline (see below). The live check is pending.

The window. The check answers at time C, and the server applies the write at time A. A write by another client that lands between C and A is overwritten, and the release does not detect it. This is a check-then-replace race. It is the same class as the file adapter's preflight-to-replace window (see the race section of the shared windows-results document). On one machine the window is short. Over a network it grows by the round trip.

What the overwrite covers. The UI's PATCH carries every writable field the page loaded. `taskPatchBody` turns all of `taskWriteBody` into JSON Patch `add` operations. So a lost race reverts every writable field to the page's copy, not only the field the user changed. An adapter can send only the changed operations, which narrows the overwrite. Not tested.

What the records release did, and the bug. The check compared a held write's token with the current version. A write with no token had nothing to compare, and the check passed it with expected None and current None. So the first records release reported "checks ok" with nothing compared. The statuses in the Results table come from that release. They are server answers, not verified releases.

The fix (offline, test first). A held request with no token is refused with "no precondition available". A token that differs from the current version is refused with "version moved". A current version that cannot be read is refused with "current version unreadable". Any refusal refuses the whole unit, and nothing is sent. The held requests stay pending, so the page gets no answer. The tests were written first: five failed on the old code. The suite now has 106 Python tests, all passing, including one that drives the workspace release with a Vikunja-shaped write and checks that nothing is sent. The Node tests were not affected (13 of 13 pass).

What this changes for records. Vikunja writes carry no token, so the fixed release refuses every held Vikunja write. A records re-run under the fix would show refused releases, and R3 and R4 would fail at read-back. That follows from the code and the observed token count. It was not run. Records numbers wait for an adapter-side read-compare (see the next paragraph) and a re-run, which needs Vikunja and so waits for the go-ahead.

The read-compare, built offline (`probe/harness/version_read.py`, `release.py`, `intercept.py`, `run_records.py`; tests written first, 131 of 131 Python tests pass):

- Page read. The harness watches the page's responses. A GET of one task with status 200 counts, and the body is read at release, not when it arrives. A held write's token is the `updated` of the last such read for its task that arrived before the write was held. If that read cannot be read, there is no token. The harness never falls back to an earlier read.
- Fresh read. Before the sends, the task is read again through the adapter's own request context, which the workspace does not route. The two `updated` strings are compared as strings. A failed or unreadable fresh read refuses.
- Gap. Each release records, per sent request, `check_to_send_s` and `check_to_response_s`. Together with the edge log's times, these bound the window from the fresh read (time C) to the server's apply (time A, between the send and the response). The exact A comes from the edge log in the live gap measurement.
- Coverage from the records data. The page made a single-task GET of every task that a held write acted on: R2, R3, R4, R6, R7, R8. The live check must show that this GET comes before the write in each run.

Not covered, and why:

- R1 (bulk create) and R5 (project create) name no existing task. Their held writes are refused ("no precondition available"). A create has no version to compare, so its precondition needs a different design, such as a parent's version or a read-back key. Not decided.
- The session refresh, `POST /api/v2/user/token/refresh`, names no task. It is pending in every held run, and it refuses the whole unit. This blocks every records release, not only the creates. It needs a decision before the rerun: (a) let the session refresh go outside the business precondition rule, which changes the release rule and needs approval; (b) let it pass the hold, which changes the hold policy; or (c) discard it at release, which changes what the page sees. None is chosen here.

Live check still to do (after the go-ahead): the single-task GET carries `updated`; a fresh read returns the same string for an unchanged task; a change made after the fresh read and before the server applies the write is not detected, so the live gap measurement measures that window rather than closing it; and the gap values line up with the edge log's times.

Gap measurement (method only, not run; it starts Vikunja, so it waits for the go-ahead):

1. Restore Vikunja from the seed (`reset.mjs restore`), start the edge and the app, and log in as alex.
2. Set up R3 (rename task 4) and run the held phase up to release. Record the `updated` value the page reads (U0) from the page's own GET response, through a response listener. Do not route the response.
3. Release. The check is a GET of task 4 through the adapter's own request context, not held. It returns U1. Its edge `done` line gives the time C. Compare U1 with U0.
4. Send the held PATCH. Its edge `arrival` line gives the time A1, and its `done` line gives the time A2 and the status.
5. Report two numbers, both from the edge `ts` field on one clock: the gap (A1 minus C, from the check answer to the write's arrival) and the window (A2 minus C, an upper bound on the apply time).

Two extra runs, labelled as beyond the brief:

6. Resolution. Send two direct PATCHes to one task 200 ms apart and read `updated` after each. The values must differ, or the check cannot see a change within a second.
7. Injected write. After step 3, another session writes a different field of task 4 before step 4. Read that field back after release. The expected result is that the page's copy wins. Control: the same write lands before step 3. The check must refuse and send nothing.

Measured values: not yet. They will go in this section after the run.

## Release demo (planned)

Two tasks, each with a version token (Vikunja is not one of them, see the release precondition section):

- S8, admin price change. Scenario 1: release with no concurrent edit, read-back
  matches. Scenario 2: a second session changes the price before release.
  Release is refused, nothing is sent, and the held request is discarded.
- M4, draft update. Scenario 1: release with no concurrent edit, read-back
  matches. Scenario 2: a second window saves the draft first. Release is refused
  at the check. If the check is skipped, the server's own 409 must make the
  release report partial.

## Adapter contract mismatches (roadmap section 3.2)

These are expectations from the design. The run confirms or changes each one.

1. Workspace: the workspace is a hold layer over the live server, not a fork of
   its state. Reads inside the workspace see live server state.
2. Snapshot and diff: no private copy of server state exists, so there is no
   state diff. The held request list is the only diff, and it is not semantic.
   The GET measurement uses table hashes outside the workspace, for measurement
   only.
3. Anchor and resolve: form fields are anchored by label, which can change. Records
   are anchored by server id, which exists only after a create.
4. Read set: the page reads what it displays, but the server validates version
   tokens the page may not display. The read set has to include those tokens.
   Vikunja confirms this: the page never displays `updated`, the UI never sends
   it, so the adapter must read it on its own.
5. Apply with precondition: a precondition exists for some writes only (If-Match
   or version fields). Moves, archive, promo and sends have none. Vikunja has no
   precondition that the server enforces. Its PATCH accepts a stale If-Match, so
   the only check is a read before the send, with the window described in the
   release precondition section.
6. Read back: a GET after release may itself change state (webmail reads). A
   read cannot always be used to check a write. The GET measurement finds which
   GETs do this.
7. Revert: no revert exists for held requests before release, and discard is an
   abort, not a revert. Email cannot be recalled. A payment needs a separate
   refund write.
8. Effects (held, release, landed): held and landed are measurable from the edge
   log. A release can be partial, and the contract has no step for that yet.
9. Reconcile: needed after a partial release. The probe has no automatic
   reconcile.
10. Multi-step flows: a held response stalls the page. The contract assumes the
    agent can continue on local state, which these apps often do not allow. The
    held GETs in M2, M5 and S7 are the first test of this, if the measurement
    shows they change state. Vikunja confirms the stall: six of eight records
    tasks (R1, R2, R5, R6, R7, R8) waited for a server answer and did not finish
    with requests held. R3 and R4 continued on local state.
11. Reset cost: the adapter needs a fresh state for each attempt. The run records
    the reset time separately, so the cost is visible. Vikunja resets in 1.0 to
    1.5 s per run.
12. Accepted-pending answers: a bare pending answer would not unblock the records
    tasks that need an echoed object (R1, R2, R5, R6, R8). It would unblock R7 at
    the status level, but the page would then show the deletion before the server
    made it. Source-based; not run. See the needs_response section.
13. Release check on a request with no token: the check compared None with None
    and passed, so the records release reported "checks ok" with nothing compared.
    Found in the records run. Fixed offline: such a request is refused with "no
    precondition available", and the held requests stay pending. The records
    numbers from before the fix are pre-fix (see the Results section).
14. Scope of an overwrite: the UI's PATCH carries every writable field the page
    loaded. A release that loses a race therefore reverts every writable field, not
    only the one the user changed. The adapter can send only the changed fields.
    Source-based; not run.
15. Long holds and the session: the page-load token refresh is a non-GET request,
    and the policy holds it. A hold longer than the token lifetime (600 s in our
    config) could let the session lapse. Our holds lasted under 30 s. Longer holds
    are not measured.

## Stand-ins and limits

- The webmail client is ours and is labelled as a stub in every result.
- The checkout store and the payment provider are ours. They are not production
  software and move no money.
- Mailpit and Vikunja are unmodified upstream builds.
- One machine, one browser, one user. Concurrency is out of scope; roadmap unit 7
  covers it separately.
- Localhost only. No third-party service is contacted, and no mail leaves the
  machine.

## Verification so far

Offline checks, plus the records block run against the live Vikunja app. Mail and
checkout have not run.

- `node --check` passes on the Node app files, the edge logger and the Vikunja seed.
- `node --test probe/tests/smtp-client.test.mjs`: 6 of 6 pass (SMTP client against
  an in-process fake SMTP server).
- `node --test probe/tests/edge-log.test.mjs`: 1 of 1 passes. It runs the real edge
  logger against a small upstream. It checks arrival and done lines, that no query
  value, cookie or body is logged, and that markers split the phases and count one
  unsafe arrival.
- `node --test probe/tests/vikunja-seed.test.mjs`: 6 of 6 pass. The seed runs against
  an in-process fake of the v2 routes it uses. It is not tested against Vikunja.
- `python -m unittest discover -s probe/tests -p "test_*.py"`: 131 of 131 pass.
  Harness (65: 45 in `test_harness.py`, 20 in `test_version_read.py`): the hold
  policy in both modes, version tokens, the page's read and the fresh read
  (a missing precondition, a moved version and an unreadable version are each
  refused with their own reason), read-to-apply gaps recorded for every release,
  ordered release,
  refusal (including a request with no token, which is refused and sends
  nothing, both at the release step and through the workspace), partial release,
  read-back, a guard that the harness never fulfils a
  route, the rule that the payment return never passes, the rule name recorded for
  each held GET, and that a held request gets no answer until release. Classifier
  (49, including 3 for the held phase number): the K1 and exclusion rules, the 11 and 12 thresholds, both policies, the
  sensitivity scope (only scope tasks run, the others are copied and marked, a
  scope task without a run is an error, a sensitivity run outside scope is an
  error, a sensitivity run cannot hold a rule it passes), GET record checks, timing
  totals, and the command line. Snapshots (12): table hashing, exclusions, reset
  before measurement, and the rule that a GET is state-changing only when a
  business table changes. The snapshot tests use synthetic SQLite files.
  Records runner (5): the kind mapping and the policy commit stamp, and a guard
  that refuses to summarise a held run made before the read-compare, naming it.
- Downloads: Vikunja and Mailpit archives match their recorded SHA-256 values, and
  the Vikunja exe matches its own `.sha256` file. Binaries are not committed.
- Live, records only: the Vikunja seed and reset (`reset.mjs build` and
  `restore`, seed hash checked), baseline and held runs for R1 to R8, the GET
  measurement for 158 GETs, and the ETag and If-Match check. The held-run releases
  were made before the fix: they sent every held write with no comparable token,
  so they are not verified releases (see the release precondition section).
- Not run: mail, checkout, the release gap measurement, the read-compare live check,
  the rerun of the records held runs, and the release demo.

## Run plan after the go-ahead

Done: Vikunja (the records block, its held runs superseded). Next, after the go-ahead: the Vikunja read-compare live check, the rerun of the records held runs (once the refresh decision is made), and the release gap measurement (see the release precondition section). Then Mailpit with the webmail stub,
then the checkout store with the payment provider. Run one app at a time. Check
free memory (at least 600 MB) before each start.

For each app:

1. Start it as its `NOTES.md` describes.
2. Baseline: for each task, reset to seed state (timed as `reset_seconds`), run
   the setup (not measured), run the baseline with holds off (timed as `seconds`).
3. GET measurement: for each distinct GET in the baseline edge log, measure it from
   a fresh reset as described above. Set each rule's flags from the result, with
   the evidence written into the rule.
4. Primary held runs: for each task, reset, setup, held phase with edge markers,
   release, read back, record the row.
5. Sensitivity held runs: for the scope tasks only (those whose primary held run
   recorded a GET the sensitivity policy passes), reset, setup, held phase under
   the sensitivity policy, release, read back, record the row. Every other task
   copies its primary row, marked `copied_from_primary`.
6. Run the two release demos (S8 and M4) after their held runs.
7. Stop the app.

Then classify the runs, record both K1 numbers, and report the timing totals
separately. Pause immediately if the orchestrator says so.

The Vikunja seed and reset were tested on the live app (`reset.mjs build`, then
`restore` before every run). A restore takes 1.0 to 1.5 s.
