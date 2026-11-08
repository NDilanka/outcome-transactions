# Records app: Vikunja (run for R1-R8; stopped, runtime data removed)

Status: the records block ran (baseline and held, R1-R8). The app and its edge
were stopped and their runtime data removed at the yield. The binary stays in
`bin/`. To run again, follow "Start" below.

## What it is

Vikunja is an open-source task manager (AGPL). We use the upstream release
binary, not a container and not Docker Desktop.

- Version: v2.8.0, Windows amd64 build (single executable, SQLite).
- Archive on disk: `bin/vikunja-v2.8.0-windows-amd64.zip` (38,647,341 bytes).
  SHA-256 `a65637c960b5c88fc3be3fa26a1a96626285e32a0d6abdefb869c8e3c26096db`,
  the value recorded from the release page.
- Unpacked: `bin/vikunja-v2.8.0-windows-4.0-amd64.exe`. SHA-256
  `37be525710b74c2b03f116828334f060c24a50b03a11a3455aa784f07ee7463f`, which matches
  the `.sha256` file shipped beside it.
- `bin/` is ignored by git. Do not commit binaries.

## Files

- `setup-secrets.mjs`: creates `probe/state/secrets.json` only if it is missing
  (JWT secret and alex's password). Prints key names only.
- `write-config.mjs`: writes `data/config.yml` from the keys below. Reads the JWT
  secret from the secrets file and never prints it.
- `reset.mjs`: `build` (once), `restore` (before every run, timed), `stop`.
- `seed.mjs`: seeds the app through its own API as alex.

## Config

`data/config.yml`, written by `write-config.mjs`:

- `interface: 127.0.0.1:3456` (the sample default binds every interface).
- `publicurl: http://127.0.0.1:8300/`.
- `enableregistration: false`, `enablelinksharing: false`,
  `enableemailreminders: false`, `mailer.enabled: false`. Nothing leaves the machine.
- `jwtttlshort: 600`.
- SQLite at `data/vikunja.db`; files at `data/files`.

## Start

Run from `probe/`.

1. `node apps/vikunja/setup-secrets.mjs` (only if the secrets file is missing).
2. `node apps/vikunja/write-config.mjs`.
3. `mkdir apps/vikunja/logs`, then start the records edge (it logs every request
   and holds the phase markers):
   `EDGE_NAME=records EDGE_LISTEN=8300 EDGE_UPSTREAM=3456 EDGE_CONTROL=8310 EDGE_LOG=apps/vikunja/logs/edge.jsonl node apps/common/edge-log.mjs`
4. `node apps/vikunja/reset.mjs build`. It stops the app, removes the database,
   migrates, registers alex with registration on, restarts with registration off,
   seeds through the edge, checkpoints the WAL, and writes `data/seed/` with the
   SHA-256 and row counts. The build seeds through the edge, so the edge must run first.
5. The harness runs `reset.mjs restore` before every run.
6. Stop: `node apps/vikunja/reset.mjs stop`, then stop the edge.

Why the registration step: `vikunja user create` reads its password from a
console prompt and cannot take it from a pipe. The build uses the API instead,
with registration turned on only for that one request.

## Seed (frozen)

User `alex`. Projects Inbox (default), Work, Home. Tasks: 1 "Renew passport"
(Home), 2 "Pay council tax" (Home), 3 "Call dentist" (Home), 4 "Quarterly report
draft" (Work), 5 "Book venue" (Work), 6 "Old test item" (Inbox). Label "urgent".
Build result: `seed_sha256` `bb607bdef15115e25db529df254b81df60e389d770225fa5d42db0e05a664355`,
3 projects, 6 tasks, 1 label. Live seed test passed on the first live build.

Excluded from the GET measurement: `sessions` (login state). The other 43 tables,
including `api_tokens` and `user_tokens` (empty at seed time), are measured.

## Realism, observed on the running app

| Feature | Status | How it was checked |
| --- | --- | --- |
| Bearer JWT in the Authorization header | present | login returns a token; the page sends it |
| Token refresh on page load (`POST /api/v2/user/token/refresh`) | present; a POST on every load | edge log, every run |
| Refresh cookie rotation | not checked | no test run |
| ETag on a task GET | present: `"<UnixNano of updated>-<permission>"`; changes after an update | live check before and after a PATCH; format in `pkg/routes/api/v2/types.go` (source) |
| If-Match on PATCH | not enforced | live check: a stale If-Match got 200 and the change was applied; no If-Match handler in `pkg/` (source) |
| The UI sends If-Match or a version field | no | 0 of 16 held writes carried a token; no non-generated frontend code sets If-Match (source) |
| Server-generated ids on create | present (201) | held and baseline runs |
| CSRF token | not applicable: the credential is a Bearer header | auth model |
| Version counter field | absent (the ETag is the only version token) | live check |
| Idempotency-Key | no handling in the v2.8.0 backend | source search of `pkg/` |
| 422 validation with an `errors` list | documented, not exercised | not run |
| GET with a server-side effect | none of 158 measured GETs | `results/raw/records/get-measure.json` |
| Outbound requests | not checked at the network level; mailer and link sharing are off | config only |

## What Vikunja lacks, for the probe

- If-Match is not enforced on PATCH, so a stale write goes through. The probe's
  release check is the only precondition for records, and the UI sends no token
  for it to compare.
- No version counter. The ETag changes after each update, but it is a timestamp,
  not a counter.
- No idempotency key handling in the v2.8.0 backend (source search of `pkg/`).
- Session expiry, rate limits and HTTPS are not exercised.

## UI behavior that matters for the probe

- The project picker (move a task) and the label picker open only on typed keys.
  `fill()` leaves them closed. The steps use `press_sequentially`, then click the
  result (`button.search-result-button`).
- Most writes wait for the server answer before the page shows the result. Two
  writes update the page first: rename a task (R3) and add a label (R4). Create
  task, create project, comment, mark done and move wait for the echoed object.
  Delete waits only for the status (source: `frontend/src/client/queries/taskMutations.ts`,
  `comments.ts`, `frontend/src/views/tasks/TaskDetailView.vue`, v2.8.0). See
  `probe/browser-probe.md`, section "What each needs_response page waited for".
- The page-load refresh POST is held by policy, like any non-GET. The page did not
  wait for it: R3 and R4 completed with it pending.

## Results

See `probe/browser-probe.md`, section Results. Raw rows are in `probe/results/raw/records/`
(git-ignored). The edge logs and the app's stdout logs are copied there too.
