# Browser feasibility probe

Status: DRAFT. The method, the K1 rule and the task list are frozen. Offline
checks pass. No app or browser has run yet. The run waits for the orchestrator's
go-ahead.

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

1. Check: each held request that carries a version token (an If-Match header or
   a version form field) is compared with the current server version. Any
   mismatch, or an unreadable version, refuses the whole unit. Nothing is sent.
2. Send: held requests are continued in their original order. The first
   rejection (status 400 or more, or no status) stops the release. The unit is
   then partial.
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
| Login session | Bearer JWT, 600 s, plus rotating refresh cookie (documented) | Session id rotated at login | Session id rotated at login |
| CSRF token on unsafe forms | Not applicable: the credential is a Bearer header, not a cookie | Yes, every form | Yes, every form; the admin JSON API needs `x-csrf-token` |
| Version field in forms | No | `draft_version`, `settings_version` (409 on stale) | `cart_version`, `address_version`, product `version` (409 on stale) |
| ETag and If-Match | ETag on single-resource GET; If-Match documented for v2, to verify | No | Admin JSON API only (428 without If-Match, 412 on mismatch) |
| Idempotency-Key | Not documented | No | On order creation and on payment and refund calls |
| Server-generated ids | Yes | Yes (Mailpit ids) | Yes |
| Validation errors | 422 with an `errors` list (documented) | 422 page | 422 page |
| GET that changes state | To measure | Measure: opening a message, opening a reply | Yes: the payment return |
| Payment by redirect | No | No | Yes, to the provider's hosted page |
| Sends mail | No | Yes, by SMTP to Mailpit | No |

What each app lacks:

- Vikunja: no version counter (the ETag and the `updated` time are the only
  version tokens). No documented idempotency key. Session expiry, rate limits
  and HTTPS are not exercised here.
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

Not measured yet. Results will fill this section after the go-ahead:

- K1, primary policy: numerator over 24, with the per-task rows from `classify.py`
  (`held_outcome`, `needs_response` kinds, `faked_response`, `native_draft_used`,
  `unsafe_before_release`, `read_back_match`, and the exclusion list).
- K1, sensitivity policy: the same. Labelled. The scope tasks come from their own
  sensitivity held runs. Every other row is copied from the primary run and marked
  `copied_from_primary`. The output lists the scope tasks and the copied tasks.
- GET measurement: one row per GET (URL, status, state-changing, changed tables),
  with the rule each GET ended under in each policy.
- Baseline result for each task.
- Timing: total reset time and total run time, reported separately.
- Release demo for two tasks (see below).
- Phase counts from the edge logs.

## Release demo (planned)

Two tasks, each with a version token:

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
5. Apply with precondition: a precondition exists for some writes only (If-Match
   or version fields). Moves, archive, promo and sends have none.
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
    shows they change state.
11. Reset cost: the adapter needs a fresh state for each attempt. The run records
    the reset time separately, so the cost is visible.

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

Offline only. Nothing has been started.

- `node --check` passes on the Node app files, the edge logger and the Vikunja seed.
- `node --test probe/tests/smtp-client.test.mjs`: 6 of 6 pass (SMTP client against
  an in-process fake SMTP server).
- `node --test probe/tests/edge-log.test.mjs`: 1 of 1 passes. It runs the real edge
  logger against a small upstream. It checks arrival and done lines, that no query
  value, cookie or body is logged, and that markers split the phases and count one
  unsafe arrival.
- `node --test probe/tests/vikunja-seed.test.mjs`: 6 of 6 pass. The seed runs against
  an in-process fake of the v2 routes it uses. It is not tested against Vikunja.
- `python -m unittest discover -s probe/tests -p "test_*.py"`: 97 of 97 pass.
  Harness (39): the hold policy in both modes, version tokens, ordered release,
  refusal, partial release, read-back, a guard that the harness never fulfils a
  route, the rule that the payment return never passes, the rule name recorded for
  each held GET, and that a held request gets no answer until release. Classifier
  (46): the K1 and exclusion rules, the 11 and 12 thresholds, both policies, the
  sensitivity scope (only scope tasks run, the others are copied and marked, a
  scope task without a run is an error, a sensitivity run outside scope is an
  error, a sensitivity run cannot hold a rule it passes), GET record checks, timing
  totals, and the command line. Snapshots (12): table hashing, exclusions, reset
  before measurement, and the rule that a GET is state-changing only when a
  business table changes. The snapshot tests use synthetic SQLite files.
- Downloads: Vikunja and Mailpit archives match their recorded SHA-256 values, and
  the Vikunja exe matches its own `.sha256` file. Binaries are not committed.
- Not run: any app, any browser, Playwright routing, the GET measurement, or
  release against a live app.

## Run plan after the go-ahead

Run one app at a time. Check free memory (at least 600 MB) before each start. Run
order: Vikunja, then Mailpit with the webmail stub, then the checkout store with
the payment provider.

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

Before the first run: the Vikunja seed script is tested only against a fake
server, so the live check is the first step after Vikunja starts. A reset
procedure for Vikunja (stop, delete the database, migrate, create the user, start,
seed) is written at that point and tested on the live app.
