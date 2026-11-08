# Records app: Vikunja (plan, not yet run)

Status: planned. Nothing is downloaded or started. The run needs the
orchestrator's go-ahead.

## What it is

Vikunja is an open-source task manager (AGPL). We use the upstream release
binary, not a container and not Docker Desktop.

- Version: v2.8.0, Windows amd64 full build (single executable, SQLite).
- Archive: `vikunja-v2.8.0-windows-4.0-amd64.exe-full.zip`
- SHA-256 (from the release listing): `a65637c960b5c88fc3be3fa26a1a96626285e32a0d6abdefb869c8e3c26096db`
- Verify the hash before unpacking. Do not run the binary if the hash differs.

## Run plan (after go-ahead)

1. Check free memory (at least 600 MB) and that no other app is running.
2. Unpack into `probe/apps/vikunja/bin/` (ignored by git).
3. Write a config file under `probe/apps/vikunja/data/` with:
   - `service.publicurl` = `http://127.0.0.1:8300/`
   - `service.interface` = `127.0.0.1:3456`
   - `service.enableregistration` = `false`
   - SQLite database file under `probe/apps/vikunja/data/`
   - a random JWT secret, stored in `probe/state/secrets.json` (not printed)
   - mailer disabled (no mail leaves the machine)
   - no OpenID, LDAP or link-sharing configuration
4. Create the probe user and seed data with the binary's own CLI. Confirm
   the exact command and flags with `vikunja --help` before use.
5. Start the edge logger: `EDGE_NAME=records EDGE_LISTEN=8300 EDGE_UPSTREAM=3456`.
6. Run the records tasks. Stop the edge and the app when done.

Seed (frozen): user `alex`; projects Inbox (default), Work, Home; tasks
"Renew passport" (Home), "Quarterly report draft" (Work), "Pay council tax"
(Home), "Book venue" (Work), "Old test item" (Inbox), "Call dentist" (Home);
label "urgent".

## Realism features (from upstream docs, read 2026, verify on the running app)

| Feature | Status | Source |
| --- | --- | --- |
| Bearer JWT for API calls, short TTL (about 10 minutes) | present (documented) | API login session migration page |
| Refresh token in an HttpOnly cookie, SameSite=Strict, path limited to the refresh route | present (documented) | same page |
| Refresh token rotates on every use; replay returns 401 | present (documented) | same page |
| ETag on single-resource GET | present (documented, API v2) | API v2 page, "Conditional requests" |
| If-Match on writes (412 on mismatch) | documented, to verify on PUT and PATCH | API v2 page |
| Server-generated ids | present | API v2 model |
| Validation errors: 422 with an `errors` list | present (documented) | API v2 page |
| CSRF token on forms | not applicable: the browser sends a Bearer header, not a cookie | auth model |
| Version counter field on records | absent: ETag and `updated` timestamp are the only version tokens | API v2 page |
| Idempotency-Key on create | not documented: treat as absent unless the code shows it | none found |
| GET with a server-side effect | unknown: check the task and comment routes before the run | to verify |

The probe's standard realism list (CSRF on forms, sessions, version fields or
ETags) applies with one difference. Vikunja's model has no CSRF token, because
its credential is not sent by the browser automatically. The probe records
this as a different model, not as a missing feature.

## Hold policy for this app

- Every non-GET request to the records origin is held (policy.py).
- No GET route is known to change state. The run must verify this. If a GET
  changes state, add it to `STATE_CHANGING_GETS["records"]` and record it.
- The bearer token is sent by the page's JavaScript, not by the browser's cookie
  store. The workspace does not need to hold the token; it sees the request.

## Open items to verify before the measured run

1. Does the UI send `If-Match` on task updates? If not, the release layer's
   check is the only precondition for records writes.
2. Which verbs does the UI use for task updates (PUT, PATCH or POST)?
3. Does any single GET change state (task view, comment list, label list)?
4. Does the server make outbound requests (avatars, update checks)? If so,
   record them; the browser policy does not cover server egress.
5. Which CLI command creates the user, and which flags it takes.
