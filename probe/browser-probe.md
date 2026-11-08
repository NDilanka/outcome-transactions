# Browser feasibility probe

Status: the Vikunja (records) block ran live on the orchestrator's go-ahead. Amendment A1 applied on its live gates, and the records runs were repeated on the current code. Vikunja is stopped and its runtime data is removed. Under the registered hold policy, no records task counts: every release is refused, because the session refresh request has no precondition. Under A1, two of eight count (R3 and R4). The read-compare precondition cannot detect an edit made in the same second as the task's last write (see "Same-second edits"). The injected-write test that checks this moves to the next Vikunja window, with a same-second case and predictions written in advance. Mail (Mailpit with the webmail stub) and checkout (with the payment provider) have not run. They wait for a go-ahead. Nothing is running now. The K1 rule and the task list are unchanged from the frozen version.

## Question

Can real web write tasks finish inside a private browser workspace while every state-changing request is held, and then be released as one verified unit?

The answer decides kill criterion K1.

## Kill criterion K1

Roadmap text: "If fewer than half of the probe's write tasks finish with requests held (no faked responses, no drafts), drop generic browser writes."

How this probe applies it. The orchestrator fixed the counting rule before any run:

- Denominator: the 24 write tasks in `probe/tasks.json`.
- A task counts in the numerator only when its measured held run meets every condition below:
  - `held_outcome` is `completes`
  - `faked_response` is false (the harness did not answer a page itself)
  - `native_draft_used` is false (the saved draft or quote was not used)
  - the task is not `native_draft_required`
  - `unsafe_before_release` is 0 (no unsafe request reached the server early)
  - `read_back_match` is true
- K1 triggers when the numerator is below 12, which is half of 24. Twelve of 24 does not trigger it.
- The highest possible numerator is 21. M3, M4 and S6 are `native_draft_required`: their goal is the saved draft or quote itself, so they cannot count.
- Each task row lists every condition that failed. `faked_response` and `native_draft_used` are separate fields, and each one also appears in the exclusion list when it is true.
- Attempt 1 is the measured held run and the only one that counts. A retry is recorded in the output and never changes the numerator.
- Baseline runs (holds off) cover all 24 tasks. They do not change the numerator.
- Held phase completes is a second number, labelled, reported beside K1. It counts the tasks whose page reached its goal with every unsafe request held, before release. It separates whether holding works from whether release can be verified. It does not change K1: a task whose release is refused, or whose read-back does not match, still fails K1 when its held phase completes.

Reported numbers. Each is labelled, and none replaces another (see "GET policy" below and "Amendment A1"):

- Registered K1, the K1 reading: the registered hold policy. Every GET measured to change state is held, and so is every GET the registered policy holds until it is measured.
- Amended K1 (A1): the same, except that the one refresh request in Amendment A1 passes. It passes only in an amended run, and only when A1 applies. Reported beside the registered number.
- Sensitivity: the registered policy, except GETs whose measured effect is reversible and low-stakes may pass. Reported beside the registered number. The payment return never passes in either.
- Held phase completes: the tasks whose page reached its goal with every unsafe request held. It is a separate count, not K1.
- Creates: the tasks whose held requests add an object. They are counted by the same rule and reported as their own category.

Sensitivity scope: the two policies differ only on GETs that the sensitivity policy passes. So a sensitivity held run is needed only for the tasks whose primary held run recorded such a GET in `gets_held`. Those are the scope tasks. Every other task copies its primary row into the sensitivity table, marked `copied_from_primary`. Its counted result is therefore the primary result, not a second measurement. Copied rows add no time to the timing totals.

This text replaces an earlier reading that counted tasks which completed by saving a draft. That reading is withdrawn.

Change to the numerator rule (labelled). A task counts as `completes` only when its release is `released` (every held request sent, none refused or rejected) and its read-back matches. Before this change the release status was not part of the rule. Records rows made under the earlier read-compare check are superseded (see Results).

What the records numbers can reach. Records adds 0 under the registered policy, because every records release is refused on the refresh request. Under A1 it adds at most 2, R3 and R4. The other six records tasks need a server response before the page can finish (see "What each needs_response page waited for"), so no release check can add them. So K1 needs at least 12 of the 13 eligible mail and checkout tasks under the registered policy, or at least 10 of 13 under A1. The consequence, if K1 triggers, is set out in "Consequence for K1 and connector design".

Calculation: `python probe/harness/classify.py --runs <runs.json>` prints the per-task rows, the K1 summaries (registered, amended when A1 applies, and sensitivity), the creates summary, and the timing totals. It stops with an error on incomplete input: a missing measured run, a missing baseline, a missing sensitivity run for a scope task, a sensitivity run for a task outside the scope, an unknown task, a GET rule name that is unknown or belongs to another app, or a field with a bad value.

## Definitions

Each task gets these fields for its measured held run.

`held_outcome`, one of:

- completes: the goal is reached on the page while every unsafe request is still held and no server response has reached the page. The release must then be `released`, and the release read-back must match the intended effect. A refused or partial release fails, even when the read-back matches.
- needs_response: the page cannot reach the goal without a server response. The run records each response it needed, from this list: `server_id`, `csrf_rotation`, `validation_result`, `payment_redirect`, `held_get_content`, `other`.
- fails: the goal is not reached, and the cause is not a missing response (a selector that cannot be found, an app error that also appears with holds off). Each fail gets a reason.

`native_draft_available`: yes when the app offers a saved, not-final record of the write (a draft message or a saved quote). Carts and orders are not drafts.

`native_draft_required`: yes when the goal cannot be reached without that saved record. Such a task cannot count for K1.

`native_draft_used`: recorded per run. Yes when the run touched the draft or quote feature at any point. Such a run cannot count for K1.

`category`: `create` when the task's held requests add an object (`creates.py`), otherwise `write`. Reported as its own category.

`release_status`: `released`, `partial` or `refused` (none for a baseline run, which has no release). `creates_held` counts held requests that add an object. Both are recorded per held run.

`gets_held`: recorded per held run. The names of the GET rules that held a request during that run. It sets the sensitivity scope, and the classifier checks each name against the rule's app.

`faked_response`: yes when the harness answered a page with a response the server did not send. The harness never does this. No code in `probe/harness` calls `route.fulfill`, and a unit test checks that. The field is still recorded for every run.

Baseline: each task also runs once with holds off. The baseline tells a fail apart from a task the app cannot do at all.

## Method

Workspace: one Playwright Chromium context per task. Each context has a fresh profile with no saved logins. The user's browser profiles are not used.

Origins: the browser may reach only the probe's own origins: the checkout edge (127.0.0.1:8100), the webmail edge (127.0.0.1:8200), the records edge (127.0.0.1:8300), and the payment provider page (127.0.0.1 and localhost on port 8102). Any other origin is blocked. The Mailpit UI is not a browser origin.

Holds (`probe/harness/policy.py`):

- Every non-GET request to a probe origin is held. HEAD and OPTIONS pass.
- GETs are held only through `GET_RULES`. Each rule has a name, the app it applies to, a path and query predicate, and two flags: `primary_hold` and `sensitivity_pass`. A held request gets no response. The page waits. Release relays the server's own response. Discard aborts the request, which the page sees as a network error.
- One non-GET request can pass, and only in an amended run: the records session refresh, `POST /api/v2/user/token/refresh`, under Amendment A1. Nothing else is allowlisted.

GET policy (set from measurement, not from guesses):

- Before measurement, the three registered GETs stay held in both policies: webmail opening a message (`/message/<id>`), webmail reply compose (`/compose?reply=`), and the checkout payment return (`/checkout/return`).
- Each GET that the baseline edge log shows is measured (see "GET measurement"). A GET that measures state-changing is held in the primary policy. A registered GET that measures unchanged passes in both policies.
- The sensitivity policy passes only GETs whose changed tables are reversible and low-stakes, for example a read flag. The rule records the evidence.
- The payment return (S7) stays held in both policies. Code enforces this, because it finalises a payment.

Consequence for the numbers: opening a message (M2, M5) and the reply compose page (M2) are held GETs under the registered policy. If they change state, the page stalls until release, which is the probe's test of GET side effects. If they do not change state, they pass in both policies and the task runs normally. The measurement decides which case applies.

GET measurement (`probe/harness/state_snapshot.py`, `measure_get`):

1. Every distinct GET in the baseline edge log is listed (path and query key names).
2. Each GET is measured from a freshly reset database, never from the state left by an earlier GET. Otherwise a GET that marks a message read would look harmless on the second measurement.
3. Snapshot: every table in the app's SQLite database is hashed (rows read in full and sorted). Housekeeping tables are excluded: `sessions` for webmail and checkout. The Vikunja list is set from the live database before the first measurement.
4. The GET is replayed with the baseline session. The status is recorded.
5. Snapshot again. The GET is state-changing when any non-excluded table differs. The result names the changed tables.

Server-side evidence: each app sits behind a logging edge (`probe/apps/common/edge-log.mjs`). The edge writes an `arrival` line when a request reaches it and a `done` line when the app has answered. Lines carry method, path, query key names, the unsafe flag, and for `done` the status and duration. No cookies, tokens or bodies are logged. The run writes phase markers (setup, held, release) to a control port. A held request never reaches the edge, so every unsafe arrival is a request the browser policy let through. The held phase passes only when the edge shows zero unsafe arrivals between the held and release markers. That count is `unsafe_before_release`.

Release (`probe/harness/release.py`, `probe/harness/intercept.py`):

1. Check: each held request must carry a version token, and that token is compared with the current server version. The token is an If-Match header or a version form field in the request, or else the `updated` value the page itself read for the request's task (`probe/harness/version_read.py`). For a create, the check is on its parent, and a duplicate guard runs too (see "Creates"). The current version is read fresh, through the adapter's own request context (not routed), just before the sends. A request with no token is refused ("no precondition available"), so it never passes silently. A mismatch ("version moved") or an unreadable version ("current version unreadable") is refused too. Any refusal refuses the whole unit. Nothing is sent, and the held requests stay pending.
2. Send: held requests are continued in their original order. The first rejection (status 400 or more, or no status) stops the release. The unit is then partial. For each sent request the release records the read-to-apply gap: `check_to_send_s`, the time from its check to the start of its send, and `check_to_response_s`, the time from its check to its response. The checks of a unit all run before its first send, so a later request's gap includes the sends before it. Every release record has a `gaps` list, empty when refused.
3. Read back: a GET after release compares the server state with the intended effect. The unit is verified only when they match. A create must find exactly one matching object, so a duplicate that slipped past the guard fails it. The read-back runs outside the hold workspace (a separate request context, not routed), so it is never held and never appears in `gets_held`.

The server still applies its own checks when a request is sent. The check in step 1 runs first, so a concurrent edit is refused before anything is sent. A small gap remains between step 1 and the server check. The run reports it.

Reset between runs: every run, baseline and held, starts from the seed state. The baseline writes change what a held run would see. Each run records `reset_seconds`, the time to reset the app and seed it. The totals are reported separately from run time. The adapter will pay the same reset cost.

Timing: each task records wall-clock time from the first step to the goal (or to the stop rule) as `seconds`. Stop rule: the held phase ends when the goal is reached or when 20 seconds pass with no change on the page.

Retries: one measured run per task (attempt 1). Any retry is a separate recorded run and does not count.

## Apps and realism

Real upstream software: Vikunja v2.8.0 (records) and Mailpit v1.33.1 (the mail server behind the webmail stub). Ours: the webmail stub, the checkout store and the payment provider. These are stand-ins, not products. Start commands are in `probe/apps/*/NOTES.md`.

| Feature | Vikunja (records) | Webmail stub (ours) | Checkout store (ours) |
| --- | --- | --- | --- |
| Login session | Bearer JWT, short token lifetime 600 s (our config); refreshed on page load by `POST /api/v2/user/token/refresh` (allowed by A1 in amended runs only) | Session id rotated at login | Session id rotated at login |
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

- Vikunja: no version counter (the ETag and the `updated` time are the only version tokens). The `updated` time has one-second resolution. The server does not enforce If-Match on PATCH, and the UI sends no token. No idempotency key. Session expiry, rate limits and HTTPS are not exercised here.
- Webmail stub: no IMAP, attachments, HTML mail, push or filters. Moves and archive carry no version token, so concurrent edits are not detected for them. Sending has no idempotency key.
- Checkout store: no card processing, webhooks, tax, shipping rules, receipts or inventory. The promo form carries no version token. No session expiry or rate limits.
- Payment provider: no card network, 3-D Secure or webhooks. It does have bearer keys, idempotency keys with conflict checks, a hosted page token, a Luhn check and a decline card (ending 0002).

## Frozen task list

Full text, setup, steps and intended effects are in `probe/tasks.json`. Eight tasks per app. Irreversible writes (mail sent, payment taken) are HOLD by default and are marked here.

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

### Records (Vikunja): live block, current code

Setup. One reset to seed before every run. Policy commit 2e6031c, working copy clean, stamped in every record. The seed was built with `reset.mjs build` and restored before each run (restore took 0.8 to 1.4 s). The build hash this time was `c1e78b51...` (3 projects, 6 tasks, 1 label). Free memory before each app start was 882 to 1080 MB.

Seed hash. The hash in `probe/apps/vikunja/NOTES.md` (`bb607...`) came from the first build. The second build gave `c1e78b51...` with the same row counts, but the two files differ, so a build is not byte-for-byte repeatable. The build code points to the causes. The file holds the times the server writes on insert and update. It holds a bcrypt hash of alex's password, and bcrypt picks a new random salt on each hash (the binary links bcrypt's password hashing). It also holds the session rows that the seed logins write. Each hash therefore names one built snapshot. `restore` checks the snapshot against its own manifest, and the restored file against the snapshot. It does not check against the old NOTES.md value. The two files were not compared field by field. The first snapshot was overwritten by the second build, and the second was removed at the yield. The run records do not store the seed hash. Every restore in the live block used the `c1e78b51...` snapshot. The next Vikunja window needs a new build, and its hash will go into NOTES.md. Two fixes, neither done: record each build's hash with its date (now in NOTES.md), or compare logical content (row counts and row digests, leaving out times, password hashes and session rows) when two builds must be shown equal.

Runs: a registered held set (primary, current code) and an amended held set (A1). Each has one run per task. The baseline set (holds off) is from the earlier session (09:22 local time, before this block). It was not repeated. A baseline makes no release, so the release changes do not affect it.

Files (git-ignored, in `probe/results/raw/records/`): `baseline.json`, `held.json` (registered), `held_amended.json` (A1), `amendment.json`, `logs/summary-run.log` (the current summary; `summary.json` predates this block and is stale), `edge.jsonl` (the edge log, 10,214 lines), app logs, and before-release screenshots. Superseded held sets are kept: `held_superseded_pre_a1.json` (before A1) and `held_superseded_pre_listing_fix.json` (before the paginated-listing fix).

| Task | Baseline (holds off) | Registered held (primary) | Amended held (A1) | Release, amended | Read-back, amended |
| --- | --- | --- | --- | --- | --- |
| R1 create task | completes | needs_response, release refused | needs_response (server id), released | released | match |
| R2 mark done | completes | needs_response, release refused | needs_response (echoed task), released | released | match |
| R3 rename | completes | fails (release refused), held phase completes | completes, released | released | match |
| R4 add label | completes | fails (release refused), held phase completes | completes, released | released | match |
| R5 create project | completes | needs_response, release refused | needs_response (server id), released | released | match |
| R6 comment | completes | needs_response, release refused | needs_response (server id), released | released | match |
| R7 delete | completes | needs_response, release refused | needs_response (status only), released | released | match |
| R8 move | completes | needs_response, release refused | needs_response (echoed task), released | released | match |

Points to note:

- Unsafe requests before release: 0 in every held run, registered and amended.
- Allowlisted arrivals: one in each amended run, the session refresh (`POST /api/v2/user/token/refresh`). It is not counted as unsafe.
- Registered runs: all eight releases were refused, because the refresh request has no precondition. R3 and R4 reached their goal with every request held, so they fail at release. The other six need a server response (see "What each needs_response page waited for").
- Amended runs: each release sent its one held write after a fresh read of the target. All eight read back to the intended effect. Creates (R1, R5, R6) each found exactly one matching object.
- Each amended write was preceded in the held phase by the page's own read of its target (task or project). The fresh read happened before the write arrived in every release.
- The R5 row is from a rerun after the paginated-listing fix. The other amended rows are from the batch started at 10:49 local time. The first R1 attempt crashed before it saved a row (a start-marker bug, fixed test-first), so it is not counted.

Records numbers:

- Registered K1 (primary): 0 of 8. Triggered (threshold 4). Every release is refused on the refresh request.
- Amended K1 (A1): 2 of 8, R3 and R4. Triggered.
- Held phase completes: 2 of 8, R3 and R4, the same in both policies. Not K1.
- Sensitivity: no records GET was held by the registered policy (`gets_held` is empty for every row), so there are no scope tasks. Every row copies the primary row. Sensitivity: 0 of 8.
- Creates (R1, R5, R6): 0 of 3 counted, under both policies. None of the three reached its goal with requests held.

Timing, 24 task runs (8 baseline, 8 registered held, 8 amended held):

- Reset: 24.6 s in total (baseline 9.3 s, registered 7.6 s, amended 7.7 s). Per run in the amended set: 0.8 to 1.4 s.
- Run: 351.0 s in total (baseline 35.4 s, registered 158.3 s, amended 157.3 s). The run includes the held phase and the 20-second stop rule.
- Reset and run times are reported separately.

Live checks (after `reset.mjs restore`, in `probe/state/live_checks.py`, not committed):

- The single-task GET `/api/v2/tasks/4` carried `updated` and an ETag (`"<UnixNano>-2"`). A second read with no write between returned the same `updated`.
- The project list digest matched on a second read of an unchanged list.
- A task marked done (task 6, sent as a full object) appears as done in its project's task listing, so the children listing includes done tasks.
- Create body shapes: the bulk task body (R1), the project body (R5) and the comment body (R6) each gave keys, passed the duplicate guard, and read back one match. All three creates were POST and returned 201.
- `updated` resolution (planned step 6, beyond the brief): two PATCHes 200 ms apart on one task gave the same `updated`. PATCHes 1.1 s apart gave different values. So a change inside the same second as an earlier write is not visible to the check. The planned expectation (values must differ at 200 ms) did not hold. The injected-write test (planned step 7) was not run. It moves to the next Vikunja window (see "Same-second edits").

Gap measurement. Times are from the edge log, one clock. C is the time the fresh read finished. A1 is the time the held write arrived. A2 is the time its response finished.

| Run | C (fresh read done) | A1 minus C | A2 minus C (upper bound on the apply time) | Harness check to response |
| --- | --- | --- | --- | --- |
| R3 rename | 05:19:57.302 UTC | 5 ms | 14 ms | 15.2 ms |
| R4 add label | 05:20:02.301 UTC | 8 ms | 17 ms | 18.4 ms |

Across all eight amended releases, one held write each, the harness measured check to response at 9.9 to 33.2 ms. Check to send was 0.0 s in every release, so each send started straight after its check.

Reading the window. A write by another client that reaches the server between C and the apply is overwritten by the held write, and the release does not detect it. The apply time lies between A1 and A2. On the edge clock, that bounds the window at 14 ms for R3 and 17 ms for R4. On the harness clock, the bound across the eight amended releases is 33.2 ms at most. The window is not closed. Over a network it grows by the round trip.

Adapter-context logins. Each release and each read-back logs in again through the adapter's own context (`POST /api/v2/login`). These requests are not held. They come after the release marker, so they are not counted as before-release arrivals.

### Records (Vikunja): first held run (superseded)

Superseded by the live block above. This was the first held run, made before the read-compare existed. Its releases compared nothing: a held write with no version token passed a check of None against None and was reported as "checks ok". So the release statuses in the table are server answers, not verified releases. The rows stay in the record and are not deleted. The baseline rows stand, since a baseline run makes no release.

Status of that run: one reset to seed before every run. Each task has a baseline run (holds off) and a primary held run. Policy commit c393905, working copy clean, stamped in every record. Raw rows are in `probe/results/raw/records/` (git-ignored): `baseline.json`, `held.json` (then superseded), `summary.json`, `get-measure.json`, the edge logs, and before-release screenshots.

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
- Held (superseded): each held request was sent in order after release and got the server's own answer. No response was faked and no draft feature was used. Nothing was left held after release. But the release compared nothing, so these releases are not verified.
- The six needs_response runs ended on the 20-second no-change stop rule (about 25 s each).
- The `needs_response` kinds in the JSON come from every request left pending, including the refresh. They do not show what the page waited for. The next section does.
- These K1 numbers are superseded. The live block above holds the current numbers.

GET measurement (Vikunja):

- 158 distinct GETs in the baseline and held logs. Each was measured from a fresh reset. None changed a table or a file.
- Control (no request): no change.
- Positive control: one `POST /api/v2/labels` changed the `labels` table with the same detector. That check was a scratch script in `probe/state/` and is not committed.
- No Vikunja GET rule is needed, so `GET_RULES` is unchanged.

Harness fixes made before the final run (earlier attempts were overwritten and are not counted):

- The project and label pickers open only on typed keys. The steps now type, then click the result.
- Network-idle waits never finish while requests are held. Steps wait for `domcontentloaded`.
- The R8 goal could pass on the sidebar Home link. It now checks the breadcrumb.
- A read-back crashed on `labels: null`. Fixed.
- Bulk create was counted as another request kind. Fixed.
- The baseline unsafe window included the read-back login. Fixed.

Mail and checkout were not run.

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

## Consequence for K1 and connector design

The number so far. Records is the only app run live. Registered K1 is 0 of 8. Amended K1 (A1) is 2 of 8. The held phase completes for 2 of 8 (R3 and R4) under both policies. The 24-task K1 cannot be computed yet, because mail and checkout have not run. Records caps the numerator at 0 (registered) or 2 (amended). K1 reaches 12 only if mail and checkout give at least 12 of their 13 eligible tasks under the registered policy, or at least 10 of 13 under A1.

The consequence, if K1 comes in under 12 of 24. The roadmap's K1 applies as written. Generic held browser writes are dropped. Server writes go through per-service connectors: an API-level adapter for each app, using that app's real version semantics, and a native draft where the app has one. Reads, navigation and draft-based flows stay in. This is what the number implies. The probe has not tested a connector, so it is not a result of this probe.

What the needs_response evidence means for connector design. In records, six of the eight write tasks (R1, R2, R5, R6, R7, R8) could not finish with requests held. The page needed the server's own answer to continue: the echoed object with its server id for the creates and the comment (R1, R5, R6), the updated object for done and move (R2, R8), and a status for delete (R7). A bare pending 202 would show the deletion before the server made it. A generic hold cannot supply these answers. It holds the request, does not know the object's shape or id, and cannot produce the server's echo before release. So a connector must return the object the server would return, with its server id, when the page needs it, and it must not report a change as done before the server has applied it. The connector also owns the version semantics a generic hold cannot see. In Vikunja the version is `updated`, the server does not enforce If-Match, and the page sends no token. The connector must therefore read `updated` itself before each write, and check the parent for a create. The live block shows this works for records: all eight amended writes passed the fresh read and read back to the intended effect. It also shows the limit. `updated` has one-second resolution, so the read cannot see a change inside that second, and the window between the fresh read and the apply stays open (measured at 33 ms at most).

## Release precondition for records (Vikunja)

Verified facts:

- The server does not enforce If-Match on task writes. Live: a PATCH with a stale If-Match returned 200 and applied the change. Source: the v2.8.0 backend has no If-Match handler.
- The UI sends no version token. Source: no non-generated frontend code sets If-Match, and `taskWriteBody` has no version field. Observed: none of the 16 held writes carried a token.
- The usable token is `updated`. It is in the task's GET body and inside the ETag, `"<UnixNano of updated>-<permission>"`. The API marks `updated` read-only, so the server ignores it on write.
- `updated` has one-second resolution (see the live block).

So the only check is a read. The release reads the task's `updated` just before it sends the held write, and compares it with the value the page read for that task. If they differ, the release refuses. This is built offline and was checked live (see the live block).

The window. The check answers at time C, and the server applies the write at time A. A write by another client that lands between C and A is overwritten, and the release does not detect it. This is a check-then-replace race. It is the same class as the file adapter's preflight-to-replace window (see the race section of the shared windows-results document). On one machine the window is short. Over a network it grows by the round trip.

What the overwrite covers. The UI's PATCH carries every writable field the page loaded. `taskPatchBody` turns all of `taskWriteBody` into JSON Patch `add` operations. So a lost race reverts every writable field to the page's copy, not only the field the user changed. An adapter can send only the changed operations, which narrows the overwrite. Not tested.

What the first records release did, and the bug. The check compared a held write's token with the current version. A write with no token had nothing to compare, and the check passed it with expected None and current None. So the first records release reported "checks ok" with nothing compared. The statuses in the first-run table come from that release. They are server answers, not verified releases.

The fix (offline, test first). A held request with no token is refused with "no precondition available". A token that differs from the current version is refused with "version moved". A current version that cannot be read is refused with "current version unreadable". Any refusal refuses the whole unit, and nothing is sent. The held requests stay pending, so the page gets no answer. The tests were written first: five failed on the old code. At that point the suite had 106 Python tests, all passing, including one that drives the workspace release with a Vikunja-shaped write and checks that nothing is sent. The Node tests were not affected (13 of 13 pass).

What this means for records. Vikunja writes carry no token, so the fixed release refuses every held Vikunja write unless the adapter reads the version itself. The records runs were repeated under the read-compare (see the live block).

The read-compare (`probe/harness/version_read.py`, `release.py`, `intercept.py`, `run_records.py`; tests written first; built offline, then checked live):

- Page read. The harness watches the page's responses. A GET of one task with status 200 counts, and the body is read at release, not when it arrives. A held write's token is the `updated` of the last such read for its task that arrived before the write was held. If that read cannot be read, there is no token. The harness never falls back to an earlier read.
- Fresh read. Before the sends, the task is read again through the adapter's own request context, which the workspace does not route. The two `updated` strings are compared as strings. A failed or unreadable fresh read refuses.
- Gap. Each release records, per sent request, `check_to_send_s` and `check_to_response_s`. Together with the edge log's times, these bound the window from the fresh read (time C) to the server's apply (time A, between the send and the response). The live gap measurement is in the live block.
- Coverage from the records data. The page made a single-task GET of every task that a held write acted on: R2, R3, R4, R6, R7, R8. The live check showed this GET comes before the write in each amended run.

Not covered by the task read-compare, and how each is now handled:

- Creates (R1 bulk create, R5 project create, R6 comment create). A create names no existing task, so the task read-compare cannot cover it. Its precondition is the parent's version plus a duplicate guard (see "Creates"). Checked live in the amended runs.
- The session refresh, `POST /api/v2/user/token/refresh`, names no task. It is pending in every held run, and it refuses the whole unit, so it blocks every records release. Amendment A1 lets only that request pass, in an amended run. Its two live gates passed, and it applied (see "Amendment A1").

Gap measurement (run live). Method: restore Vikunja from the seed, start the edge and the app, log in. Set up R3 (rename task 4) and run the held phase up to release, recording the `updated` the page read from its own GET. Release: the fresh read through the adapter's context (not held) gives C from its edge `done` line. The held PATCH gives A1 (arrival) and A2 (done). The results are in the live block. Two extra steps: step 6 (resolution) ran and showed the one-second limit. Step 7 (an injected write from another session) was not run. It moves to the next Vikunja window (see "Same-second edits").

## Amendment A1: the session refresh (records only, labelled)

This is a labelled amendment to the registered hold rule. It was written before any amended run. The registered number stays the K1 reading, and the amended number is reported beside it.

Why. The page refreshes its session on load with `POST /api/v2/user/token/refresh`. The registered policy holds that request. It names no task, so release has no version token for it, and the release refuses the whole unit. Every records release is refused for this reason alone.

What A1 allows. One request: method POST, path `/api/v2/user/token/refresh`, on the records origin, with no query string. There is no pattern. `probe/harness/amendment.py` holds the allowlist (`ALLOWLIST`), and `allows` checks the method, the app, the path and the query exactly. Only the `held-amended` runs use it. The registered runs hold every request.

Conditions. A1 applies only when both live gates pass. Both are measured from a fresh reset (`python probe/harness/run_records.py amend`):

1. State gate. The refresh returns a 2xx status, and every table it changes is one of the excluded housekeeping tables, `sessions` (`state_snapshot.EXCLUDED_TABLES`). A change to any other table refuses A1.
2. Real-user gate. A second session for the same user, logged in beside the workspace session, returns 200 before the refresh and 200 after it. If the refresh signs that session out, A1 is void.

Procedure. The measurement resets the app, logs in the workspace session and the real-user session, checks the real-user session, takes a table snapshot, refreshes the workspace session, takes a second snapshot, then checks both sessions again. The snapshot excludes nothing, so the record lists every table the refresh changed. The verdict applies the exclusion. The result goes to `probe/results/raw/records/amendment.json` with `applied`, `reasons`, the status, the changed tables, the real-user statuses and the policy commit. `held-amended` refuses to run unless that file records A1 as applied.

Result (live, measured once). `amendment.json` records `applied: true` with no reasons:

- Refresh status: 200.
- Changed tables: `sessions` only, which is excluded.
- Real-user session: 200 before the refresh, 200 after it.
- Workspace session after the refresh: 200.
- Policy commit 2e6031c, working copy clean.

The gates were measured once. They were not repeated.

Scope. In an amended run, an arrival of the allowlisted request is reported as `allowlisted_arrivals_before_release`. It is not counted in `unsafe_before_release`. Every other unsafe arrival counts as before. Each amended run recorded one allowlisted arrival, and no other allowlisted request exists.

What A1 does not change. Whether a task's held phase completes depends on what the page does while requests are held. The refresh does not decide that. A1 changes only whether a release is refused. So amended K1 can differ from registered K1 only for tasks whose held phase completes (R3 and R4 in records).

Void path. If either gate fails, `amendment.json` records `applied: false` with the reasons. The amended phase then refuses to run, and no amended number is reported. The registered number is then the only K1 number for records.

Status: built offline with tests (`probe/tests/test_amendment.py`, 29 tests). Applied on the live gates (see Result above).

## Creates (records): parent version and duplicate guard

A create adds an object, so it has no version of its own. Its release check reads two things before anything is sent (`probe/harness/creates.py`). Creates are a category of their own in the results.

Covered requests. A POST or PUT to:

- a project's task collection, single or bulk (R1). Parent: the project.
- the project collection (R5). Parent: the project the new project goes under, if it has a parent. A top-level project takes the project list as its parent.
- a task's comments (R6). Parent: the task. R6 is a create, so it is in the create category. The orchestrator confirmed this classification.

Checks, all before the first send:

1. Parent version. The parent's version is read the way a task's version is read (`version_read.py`). A task or a project uses its `updated` value. The project list uses a digest of the sorted `id:updated` pairs of the list the page read, with the same query. A moved parent refuses. An unreadable parent refuses.
2. Duplicate guard. The parent's children are read again, through the adapter's own context, from one page of 100. The keys are the task title (within the project), the project title (within its parent), or the comment's plain text (within the task). A key already present refuses. Two creates in one unit with the same key refuse the second. A listing that cannot be read refuses. So does a listing with more pages, since a duplicate may sit on the next page.
3. Fail closed. A body with no usable key (not JSON, or no title or comment text) gives no key, and the create refuses.

After release, the read-back must find exactly one matching object. Zero matches or two refuse the read-back.

Listing shape (found live). Vikunja's listings are paginated objects (`items`, `total`, `page`, `per_page`, `total_pages`), not bare lists. The first live run refused the children reads for the wrong reason, because the parser expected a bare list. The parser was fixed test-first. Completeness is the server's own paging: the read is complete only when `page >= total_pages`. The project list total leaves out the pseudo-project "My Open Tasks" (id -2), so a test of items against total is wrong. The server caps comment listings at 50 per page (the guard asks for 100), so a task with more than 50 comments refuses as incomplete.

Checked live (amended runs R1, R5, R6):

- Body shapes: the bulk task body (R1), the project body (R5) and the comment body (R6) each gave keys. Each create passed the guard and read back one match.
- Children listings return done tasks: a task marked done appears as done in the project listing.
- Method: all three creates were POST (`POST /api/v2/projects/1/tasks/bulk`, `POST /api/v2/projects`, `POST /api/v2/tasks/1/comments`), each returned 201.
- No listing hit the full-page refusal in the seed.

Limits of the guard. A task with the same title as an existing task in the same project refuses, including a second task the user meant to add. That is the safe failure. The same check-then-replace window as for writes applies to the parent and the children read. `updated` has one-second resolution, so the parent's version cannot see a change inside the same second as its last write (see "Same-second edits"). The gap measurement covers the window. It is not closed.

Status: checked live in the amended runs (R1, R5, R6), after the listing fix. 233 Python tests pass.

## Same-second edits (records)

Every records version check compares `updated`, which has one-second resolution. That covers the task read-compare, the project read-compare, the project list digest (built from `id:updated` pairs) and the create parent check.

What the check cannot see. A write by another client is invisible to the check when both of these hold:

- it lands after the page read the task, and
- it lands in the same second as the last write the page saw.

The stored `updated` string does not change, so the token still matches. The release passes and sends the page's write, which overwrites the other client's edit. The read-back still matches, because it checks only the intended effect.

Size of the blind spot. This is not the few milliseconds of the gap. It covers the rest of the second in which the task's last write landed. The resolution was measured: two PATCHes 200 ms apart gave one `updated`, and two PATCHes 1.1 s apart gave two (see the live block). The gap after the check is a separate window, and the check cannot see a write in it at any resolution.

The duplicate guard reads the children at check time and does not use `updated`, so resolution does not limit it. It has the same check-then-send window.

Mitigations, none tested:

1. A version that changes on every write. Vikunja v2.8.0 has none. The ETag is built from `updated`, so it has the same resolution.
2. A digest of the whole task body, taken at the page's read and again at the check. A same-second edit to any field the GET returns would change the digest. A change to a field the GET does not return would still pass, and the check-then-send window stays.
3. Sending only the changed fields. This does not detect an edit. It narrows what an overwrite can revert, because the UI's PATCH carries every writable field.

Planned test: injected writes, next Vikunja window. Not run. The predictions below were written before any run of this test. The test script is not written yet. It will be written test first and checked offline before that window.

Setup: task 4 (Quarterly report draft). The page's goal is to rename it to "Renamed by page". Restore the seed, start the edge and the app, log in the workspace session through the adapter's own context, and log in a second session for the injector (not held, not routed). After release, a GET outside the workspace records `final_title`.

Case A, control (different second, before the fresh read). The page reads the task. At least 2 s later, the injector renames it to "Injected A". The page's rename is then held and released.

Case B, same second, after the page's read (the blind spot). The harness waits until the server's `Date` header shows a new second. In that second the injector renames the task to "Injected B" (write W0). The page loads the task, and its token is W0's `updated`. As soon as the page's GET arrives, the injector renames the task to "Injected C" (write W1). A sample counts only when W1's response `updated` equals the token, which means W1 landed in the same second as W0. Each attempt is recorded, and a missed attempt is not counted. There are up to three attempts. Then the page's rename is held and released.

Case C, the window (after the check, before the send). A test-only hook in the release runs the injector after the fresh read passes and before the held write is sent. The injector renames the task to "Injected D", in a different second from the token, so the check would have refused that write had it landed before the fresh read. No run calls the hook.

| Case | Injected write | Predicted release | Predicted `final_title` | What it shows |
| --- | --- | --- | --- | --- |
| A | different second, before the fresh read | refused ("version moved"), nothing sent, held write stays pending | Injected A | the check works when the second differs |
| B | same second, after the page's read | released, read-back matches | Renamed by page | the same-second blind spot |
| C | after the fresh read, before the send | released, read-back matches | Renamed by page | the window, at any resolution |

If B refuses, the blind spot is not real on this build, and the resolution finding needs a closer look. If C refuses, the hook did not run after the check, and the run is not valid. Results that differ from these predictions will be reported as found, with the predictions kept beside them. Each run records the release status, the read-back, `final_title`, `unsafe_before_release` and the server seconds of each write.

What a confirmed B means for records. The check cannot show that no same-second edit happened. A records adapter needs one of the mitigations above before it can claim a checked write against concurrent edits within one second.

## Release demo (planned)

Two tasks, each with a version token (Vikunja is not one of them, see the release precondition section):

- S8, admin price change. Scenario 1: release with no concurrent edit, read-back matches. Scenario 2: a second session changes the price before release. Release is refused, nothing is sent, and the held request is discarded.
- M4, draft update. Scenario 1: release with no concurrent edit, read-back matches. Scenario 2: a second window saves the draft first. Release is refused at the check. If the check is skipped, the server's own 409 must make the release report partial.

## Adapter contract mismatches (roadmap section 3.2)

These are expectations from the design. The run confirms or changes each one.

1. Workspace: the workspace is a hold layer over the live server, not a fork of its state. Reads inside the workspace see live server state.
2. Snapshot and diff: no private copy of server state exists, so there is no state diff. The held request list is the only diff, and it is not semantic. The GET measurement uses table hashes outside the workspace, for measurement only.
3. Anchor and resolve: form fields are anchored by label, which can change. Records are anchored by server id, which exists only after a create.
4. Read set: the page reads what it displays, but the server validates version tokens the page may not display. The read set has to include those tokens. Vikunja confirms this: the page never displays `updated`, the UI never sends it, so the adapter must read it on its own.
5. Apply with precondition: a precondition exists for some writes only (If-Match or version fields). Moves, archive, promo and sends have none. Vikunja has no precondition that the server enforces. Its PATCH accepts a stale If-Match, so the only check is a read before the send, with the window described in the release precondition section.
6. Read back: a GET after release may itself change state (webmail reads). A read cannot always be used to check a write. The GET measurement finds which GETs do this.
7. Revert: no revert exists for held requests before release, and discard is an abort, not a revert. Email cannot be recalled. A payment needs a separate refund write.
8. Effects (held, release, landed): held and landed are measurable from the edge log. A release can be partial, and the contract has no step for that yet.
9. Reconcile: needed after a partial release. The probe has no automatic reconcile.
10. Multi-step flows: a held response stalls the page. The contract assumes the agent can continue on local state, which these apps often do not allow. The held GETs in M2, M5 and S7 are the first test of this, if the measurement shows they change state. Vikunja confirms the stall: six of eight records tasks (R1, R2, R5, R6, R7, R8) waited for a server answer and did not finish with requests held. R3 and R4 continued on local state.
11. Reset cost: the adapter needs a fresh state for each attempt. The run records the reset time separately, so the cost is visible. Vikunja resets in 0.8 to 1.4 s per run in the live block.
12. Accepted-pending answers: a bare pending answer would not unblock the records tasks that need an echoed object (R1, R2, R5, R6, R8). It would unblock R7 at the status level, but the page would then show the deletion before the server made it. Source-based; not run. See the needs_response section.
13. Release check on a request with no token: the check compared None with None and passed, so the first records release reported "checks ok" with nothing compared. Found in the records run. Fixed offline: such a request is refused with "no precondition available", and the held requests stay pending. The first-run records numbers are pre-fix (see the Results section).
14. Scope of an overwrite: the UI's PATCH carries every writable field the page loaded. A release that loses a race therefore reverts every writable field, not only the one the user changed. The adapter can send only the changed fields. Source-based; not run.
15. Long holds and the session: the page-load token refresh is a non-GET request, and the policy holds it. A hold longer than the token lifetime (600 s in our config) could let the session lapse. Our holds lasted under 30 s. Longer holds are not measured.
16. Requests that name no object: the session refresh adds to no task, so the per-write precondition cannot cover it, and the registered policy refuses every records release for it. Labelled amendment A1 allows only this request, in an amended run. Its two live gates passed and it applied (see "Amendment A1"). The contract has no rule for session requests of this kind.
17. Creates: an add has no version of its own. The contract's precondition is a version of the parent, plus a duplicate guard read from the parent's children. Built and checked live in the amended runs (R1, R5, R6 released with matching read-backs; see "Creates").
18. Paginated listings: Vikunja's listings are paged objects. A complete read needs the server's own paging, and the project list total leaves out a pseudo-project. The adapter must page to completion or refuse. Found live.
19. Version resolution: `updated` has one-second resolution. Two writes in the same second give one value, so the read-compare cannot see a write by another client that lands in the same second as the last write the page saw. The contract must state the resolution of each version token. Found live (see "Same-second edits").
20. Adapter logins: each release and each read-back logs in again through the adapter's own context. These logins are logged by the edge but are not held and do not affect the counts.

## Stand-ins and limits

- The webmail client is ours and is labelled as a stub in every result.
- The checkout store and the payment provider are ours. They are not production software and move no money.
- Mailpit and Vikunja are unmodified upstream builds.
- One machine, one browser, one user. Concurrency is out of scope; roadmap unit 7 covers it separately.
- Localhost only. No third-party service is contacted, and no mail leaves the machine.

## Verification so far

Offline checks, plus the records block run live against Vikunja. Mail and checkout have not run.

- `python -m unittest discover -s tests -p "test_*.py"` (from `probe/`): 233 of 233 pass. By file:
  - `test_harness.py` (45): the hold policy in both modes, version tokens, the page read and the fresh read (a missing precondition, a moved version and an unreadable version are each refused with their own reason), read-to-apply gaps for every release, ordered release, refusal (including a request with no token, which is refused and sends nothing, both at the release step and through the workspace), partial release, read-back, a guard that the harness never fulfils a route, the rule that the payment return never passes, the rule name recorded for each held GET, and that a held request gets no answer until release.
  - `test_classify.py` (66): the K1 and exclusion rules, the 11 and 12 thresholds, both policies, the sensitivity scope (only scope tasks run, the others are copied and marked, a scope task without a run is an error, a sensitivity run outside scope is an error, a sensitivity run cannot hold a rule it passes), GET record checks, timing totals, the held phase number, the create summary, the refusal of amended numbers without an applied A1, and the command line.
  - `test_version_read.py` (28): the version targets (task, project, project list), the page read and fresh read for each, and listing completeness (paged objects are read; bare lists, incomplete pages and malformed paging fields are refused; the live project list shape with the pseudo-project is complete).
  - `test_state_snapshot.py` (12): table hashing, exclusions, reset before measurement, and the rule that a GET is state-changing only when a business table changes. The snapshot tests use synthetic SQLite files.
  - `test_run_records.py` (18): the kind mapping and the policy commit stamp, the refusal to summarise a held run made before the current release check, the outcome rule (`completes` needs a released unit and a matching read-back), phase files, the start marker for each phase (held and held-amended), the live operations contract (reset, login, refresh, snapshot), the amendment guard, and the create counts.
  - `test_amendment.py` (29): the exact allowlist, the policy hook, the verdict gates (status, excluded tables, real-user session, missing measurements), measurement order with fake operations, the arrival split, and the amended workspace pass.
  - `test_creates.py` (35): create recognition, parent, keys, fail-closed keys, the children listing (including paged listings and the refusal of incomplete pages), the check outcomes (moved, unreadable, duplicate, repeated in a unit), and an end-to-end release through the workspace with a fake adapter.
- `python -m py_compile` passes on every harness module.
- `node --test` (from `probe/`): `edge-log.test.mjs` 1 of 1, `smtp-client.test.mjs` 6 of 6, `vikunja-seed.test.mjs` 6 of 6 (13 of 13).
- Downloads: Vikunja and Mailpit archives match their recorded SHA-256 values, and the Vikunja exe matches its own `.sha256` file. Binaries are not committed.
- Live, records (done): the seed build and restore, memory checks, the A1 gates, the registered and amended runs for R1 to R8, the GET measurement (158 GETs, earlier), the live checks (`updated` presence and stability, the project list digest, done tasks in the listing, the create shapes, the resolution test), and the gap measurement.
- Not run: mail, checkout, the release demo, and the injected-write test (planned step 7 of the gap measurement, moved to the next Vikunja window; see "Same-second edits").

## Run plan

Done: Vikunja. Baseline runs, registered held runs, amendment A1 gates, amended held runs, live checks, gap measurement and summary. Vikunja is stopped, its runtime data is removed, the edge is stopped and the browser is closed.

Vikunja, next window: the injected-write test (see "Same-second edits"), then stop and remove Vikunja again. It needs the same gates as any Vikunja start: a memory check of at least 600 MB, one app at a time, and the orchestrator's go-ahead. The seed is built again first (`reset.mjs build`).

Next, only on the orchestrator's go-ahead: Mailpit with the webmail stub, and then the checkout store with the payment provider. Run one app at a time. Check free memory (at least 600 MB) before each start.

For each app:

1. Start it as its `NOTES.md` describes.
2. Baseline: for each task, reset to seed state (timed as `reset_seconds`), run the setup (not measured), run the baseline with holds off (timed as `seconds`).
3. GET measurement: for each distinct GET in the baseline edge log, measure it from a fresh reset as described above. Set each rule's flags from the result, with the evidence written into the rule.
4. Primary held runs: for each task, reset, setup, held phase with edge markers, release, read back, record the row.
5. Sensitivity held runs: for the scope tasks only (those whose primary held run recorded a GET the sensitivity policy passes), reset, setup, held phase under the sensitivity policy, release, read back, record the row. Every other task copies its primary row, marked `copied_from_primary`.
6. Run the two release demos (S8 and M4) after their held runs.
7. Stop the app.

Then classify the runs. Record the registered K1 number, with the amended number, the sensitivity number and the held phase number beside it, each labelled. Report the creates category and the timing totals separately. Pause immediately if the orchestrator says so.
