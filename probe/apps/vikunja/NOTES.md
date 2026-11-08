# Records app: Vikunja (downloaded and hash-checked, not run)

Status: the binary is on disk and its hashes match. Nothing has started. The run
needs the orchestrator's go-ahead.

## What it is

Vikunja is an open-source task manager (AGPL). We use the upstream release
binary, not a container and not Docker Desktop.

- Version: v2.8.0, Windows amd64 build (single executable, SQLite).
- Archive on disk: `bin/vikunja-v2.8.0-windows-amd64.zip` (38,647,341 bytes).
  SHA-256 `a65637c960b5c88fc3be3fa26a1a96626285e32a0d6abdefb869c8e3c26096db`,
  the value recorded from the release page. The archive name in the earlier plan
  was not used.
- Unpacked: `bin/vikunja-v2.8.0-windows-4.0-amd64.exe` (45,748,854 bytes). SHA-256
  `37be525710b74c2b03f116828334f060c24a50b03a11a3455aa784f07ee7463f`, which matches
  the `.sha256` file shipped beside it.
- `bin/` is ignored by git. Do not commit binaries.

## Config

Keys are taken from the upstream `bin/config.yml.sample` for v2.8.0. Write this
file to `data/config.yml` before the first start. Paths are absolute.

```yaml
service:
  interface: "127.0.0.1:3456"
  publicurl: "http://127.0.0.1:8300/"
  secret: "<random, generated once, stored in state/secrets.json, never printed>"
  jwtttlshort: 600
  rootpath: "<probe>/apps/vikunja/data"
  enableregistration: false
  enablelinksharing: false
  enableemailreminders: false
database:
  type: "sqlite"
  path: "<probe>/apps/vikunja/data/vikunja.db"
files:
  basepath: "<probe>/apps/vikunja/data/files"
mailer:
  enabled: false
```

Why these values:

- `interface` pins the server to loopback. The sample default `:3456` binds every
  interface.
- `enableregistration: false` keeps the probe user as the only account.
- `enablelinksharing` and `enableemailreminders` are off, so the app does not
  send or share anything outside the machine.
- `mailer.enabled: false` means no mail leaves the machine.

## Start order (after go-ahead)

1. Check free memory (at least 600 MB) and that no other app is running.
2. Generate the JWT secret and merge it into `state/secrets.json` under the key
   `records.jwt_secret`. Do not print it.
3. Write `data/config.yml` as above.
4. Run `bin/vikunja-v2.8.0-windows-4.0-amd64.exe --help`. Confirm the config-file
   flag. If the binary has none, set the same keys as `VIKUNJA_SERVICE_*`
   environment variables. Confirm the names with `--help` first.
5. Migrate: `vikunja migrate`.
6. Create the probe user: `vikunja user create -u alex -e alex@local.test`. Omit
   `-p` and type the password from `state/secrets.json` at the prompt, so the
   password does not appear on the command line.
7. Start the app: `vikunja web`. It binds 127.0.0.1:3456.
8. Start the edge logger:
   `EDGE_NAME=records EDGE_LISTEN=8300 EDGE_UPSTREAM=3456 EDGE_CONTROL=8310 EDGE_LOG=probe/apps/vikunja/logs/edge.jsonl node probe/apps/common/edge-log.mjs`
9. Seed through the app's own API as `alex` (setup, not measured). A seed script
   is not written yet. Write it and test it against the running app before the
   first run.
10. Run the records tasks and the baseline. Stop the edge and the app when done.

Seed (frozen): user `alex`; projects Inbox (default), Work, Home; tasks "Renew
passport" (Home), "Quarterly report draft" (Work), "Pay council tax" (Home), "Book
venue" (Work), "Old test item" (Inbox), "Call dentist" (Home); label "urgent".

## Realism features (from upstream docs, to verify on the running app)

| Feature | Status | Source |
| --- | --- | --- |
| Bearer JWT for API calls, short TTL (600 s from `jwtttlshort`) | present (documented) | API login session migration page |
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
its credential is not sent by the browser automatically. The probe records this
as a different model, not as a missing feature.

## Hold policy for this app

- Every non-GET request to the records origin is held (`probe/harness/policy.py`).
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
5. Confirm the config-file flag with `--help` (step 4 above). The user command
   flags (`-u`, `-p`, `-e`) are taken from the upstream CLI docs.
