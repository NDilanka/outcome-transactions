# Browser feasibility probe

Status: DRAFT. The task list and method are frozen. No app or browser has run
yet. The run waits for the orchestrator's go-ahead.

## Question

Can real web write tasks finish inside a private browser workspace while every
state-changing request is held, and then be released as one verified unit?

The answer decides kill criterion K1.

## Kill criterion K1

Roadmap text: "If fewer than half of the probe's write tasks finish with requests
held (no faked responses, no drafts), drop generic browser writes."

How this probe applies it:

- Denominator: the 24 write tasks in `probe/tasks.json`.
- Numerator: tasks with `held_outcome = completes`.
- K1 triggers when the numerator is below 12. Twelve of 24 does not trigger it.
- `native_draft` is reported on its own. It does not change the numerator.

## Definitions

Each task gets two separate fields.

`held_outcome`, one of:

- completes: the goal is reached on the page while every unsafe request is still
  held and no server response has reached the page. The release read-back must
  also match the intended effect.
- needs_response: the page cannot reach the goal without a server response. The
  run records which response it needed: a server-generated id, a CSRF token
  rotation, a validation result, a payment redirect, page content from a held
  GET, or other.
- fails: the goal is not reached, and the cause is not a missing response (a
  selector that cannot be found, an app error that also appears with holds off).
  Each fail gets a reason.

`native_draft`: yes when the app offers a saved, not-final record of the write
(a draft message or a saved quote). Carts and orders are not drafts. The value
is fixed per task in the task list. The run records whether the draft path was
used.

Baseline: each task also runs once with holds off. The baseline tells a fail
apart from a task the app cannot do at all. It does not change the denominator.

## Method

Workspace: one Playwright Chromium context per task. Each context has a fresh
profile with no saved logins. The user's browser profiles are not used.

Origins: the browser may reach only the probe's own origins: the checkout edge
(127.0.0.1:8100), the webmail edge (127.0.0.1:8200), the records edge
(127.0.0.1:8300), and the payment provider page (127.0.0.1 and localhost on port
8102). Any other origin is blocked.

Holds (`probe/harness/policy.py`):

- Every non-GET request to a probe origin is held. HEAD and OPTIONS pass.
- These GET requests change server state and are held too: checkout
  `/checkout/return`, webmail `/message/<id>`, and webmail `/compose?reply=`.
- A held request gets no response. The page waits. Release relays the server's
  own response. Discard aborts the request, which the page sees as a network
  error.

Server-side evidence: each app sits behind a logging edge (`probe/apps/common/edge-log.mjs`).
The edge logs every unsafe request that reaches the app, with method, path and
query key names only. No cookies, tokens or bodies are logged. The run writes
phase markers (setup, held, release). A held phase passes only when the edge
shows zero unsafe requests between the held and release markers.

Release (`probe/harness/release.py`, `probe/harness/intercept.py`):

1. Check: each held request that carries a version token (an If-Match header or
   a version form field) is compared with the current server version. Any
   mismatch, or an unreadable version, refuses the whole unit. Nothing is sent.
2. Send: held requests are continued in their original order. The first
   rejection (status 400 or more, or no status) stops the release. The unit is
   then partial.
3. Read back: a GET after release compares the server state with the intended
   effect. The unit is verified only when they match.

The server still applies its own checks when a request is sent. The check in
step 1 runs first, so a concurrent edit is refused before anything is sent. A
small gap remains between step 1 and the server check. The run reports it.

Timing: each task records wall-clock time from the first step to the goal (or
to the stop rule). Stop rule: the held phase ends when the goal is reached or
when 20 seconds pass with no change on the page.

Retries: one measured run per task. Any retry is a separate recorded run.

## Apps and realism

Real upstream software: Vikunja v2.8.0 (records) and Mailpit v1.33.1 (the mail
server behind the webmail stub). Ours: the webmail stub, the checkout store and
the payment provider. These are stand-ins, not products.

| Feature | Vikunja (records) | Webmail stub (ours) | Checkout store (ours) |
| --- | --- | --- | --- |
| Login session | Bearer JWT, about 10 minutes, plus rotating refresh cookie (documented) | Session id rotated at login | Session id rotated at login |
| CSRF token on unsafe forms | Not applicable: the credential is a Bearer header, not a cookie | Yes, every form | Yes, every form; the admin JSON API needs `x-csrf-token` |
| Version field in forms | No | `draft_version`, `settings_version` (409 on stale) | `cart_version`, `address_version`, product `version` (409 on stale) |
| ETag and If-Match | ETag on single-resource GET; If-Match documented for v2, to verify | No | Admin JSON API only (428 without If-Match, 412 on mismatch) |
| Idempotency-Key | Not documented | No | On order creation and on payment and refund calls |
| Server-generated ids | Yes | Yes (Mailpit ids) | Yes |
| Validation errors | 422 with an `errors` list (documented) | 422 page | 422 page |
| GET that changes state | To verify | Yes: opening a message, opening a reply | Yes: the payment return |
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

| ID | App | Task | Irreversible | native_draft |
| --- | --- | --- | --- | --- |
| R1 | Vikunja | Create a task in Inbox | no | no |
| R2 | Vikunja | Mark a task done | no | no |
| R3 | Vikunja | Rename a task | no | no |
| R4 | Vikunja | Add a label to a task | no | no |
| R5 | Vikunja | Create a project | no | no |
| R6 | Vikunja | Comment on a task | no | no |
| R7 | Vikunja | Delete a task | no | no |
| R8 | Vikunja | Move a task to another project | no | no |
| M1 | Webmail | Send a new message | yes | yes |
| M2 | Webmail | Reply to a message | yes | yes |
| M3 | Webmail | Save a new draft | no | yes |
| M4 | Webmail | Update a saved draft | no | yes |
| M5 | Webmail | Archive a message | no | no |
| M6 | Webmail | Create a folder | no | no |
| M7 | Webmail | Add a contact | no | no |
| M8 | Webmail | Change the display name | no | no |
| S1 | Checkout | Add an item to the cart | no | no |
| S2 | Checkout | Change an item quantity | no | no |
| S3 | Checkout | Apply a promo code | no | no |
| S4 | Checkout | Remove an item | no | no |
| S5 | Checkout | Change the shipping address | no | no |
| S6 | Checkout | Save the cart as a quote | no | yes |
| S7 | Checkout | Place an order and pay | yes | no |
| S8 | Checkout | Admin changes a product price | no | no |

## Results

Not measured yet. Results will fill this section after the go-ahead:

- K1 numbers: completes over 24, with the per-task `held_outcome`, `native_draft`
  and needs_response records.
- Baseline results for each task.
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
3. Anchor and resolve: form fields are anchored by label, which can change. Records
   are anchored by server id, which exists only after a create.
4. Read set: the page reads what it displays, but the server validates version
   tokens the page may not display. The read set has to include those tokens.
5. Apply with precondition: a precondition exists for some writes only (If-Match
   or version fields). Moves, archive, promo and sends have none.
6. Read back: a GET after release may itself change state (webmail reads). A
   read cannot always be used to check a write.
7. Revert: no revert exists for held requests before release, and discard is an
   abort, not a revert. Email cannot be recalled. A payment needs a separate
   refund write.
8. Effects (held, release, landed): held and landed are measurable from the edge
   log. A release can be partial, and the contract has no step for that yet.
9. Reconcile: needed after a partial release. The probe has no automatic
   reconcile.
10. Multi-step flows: a held response stalls the page. The contract assumes the
    agent can continue on local state, which these apps often do not allow.

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

- `node --check` passes on the four Node app files.
- `node --test probe/tests/smtp-client.test.mjs`: 6 of 6 pass (SMTP client against
  an in-process fake SMTP server).
- `python -m unittest discover -s probe/tests -p "test_*.py"`: 22 of 22 pass (hold
  policy, version tokens, ordered release, refusal, partial release, read-back).
- Not run: any app, any browser, Playwright routing, or release against a live app.

## Run plan after the go-ahead

Run one app at a time. Check free memory (at least 600 MB) before each start. Run
order: Vikunja, then Mailpit with the webmail stub, then the checkout store with
the payment provider. For each app: start, seed, run the setup for each task,
measure the held phase, release, read back, run the baseline, stop. Pause
immediately if the orchestrator says so.
