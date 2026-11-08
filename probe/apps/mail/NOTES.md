# Mail: Mailpit and the webmail stub (downloaded, not run)

Status: Mailpit is on disk and its archive hash matches. The webmail stub is ours
and has not run. Nothing has started. The run needs the orchestrator's go-ahead.

## Mailpit v1.33.1 (upstream, unmodified)

- Archive on disk: `bin/mailpit-v1.33.1-windows-amd64.zip` (11,186,131 bytes).
  SHA-256 `0bcf8f1e7c21005b30c206064ff2f37dac602ef66774e558379d326f5673d652`,
  the value recorded from the release page.
- Unpacked: `bin/mailpit.exe` (29,338,624 bytes). The zip hash is the check. The
  exe was not checked against a separate published hash.
- `bin/` is ignored by git.

Start (after go-ahead). Delete `data/mailpit.db` first, so every run starts with an
empty mail server:

```
bin\mailpit.exe --listen 127.0.0.1:8025 --smtp 127.0.0.1:1025 --database data\mailpit.db --disable-version-check --smtp-allowed-recipients '@(example\.test|local\.test)$'
```

- `--listen` and `--smtp` pin both ports to loopback. The defaults bind every
  interface.
- `--disable-version-check` stops Mailpit from contacting GitHub.
- `--smtp-allowed-recipients` accepts mail only for the probe's test domains.
  Quote the regex so the shell does not expand it.
- Save Mailpit's own log: redirect stdout and stderr to `logs/mailpit.log`.

## Webmail stub (ours)

This is a stand-in for a webmail client, not a real one. Every result labels it
as a stub.

- Seed (setup, not measured): `node probe/apps/mail/webmail.mjs --seed`. It needs
  Mailpit running on 127.0.0.1:1025. It resets the webmail database, creates the
  account alex@local.test, adds contact Bob Ng, saves draft "Agenda", and delivers
  three inbox messages through SMTP.
- Serve: `node probe/apps/mail/webmail.mjs` listens on 127.0.0.1:8201
  (`WEBMAIL_PORT`). It reads the Mailpit API at 127.0.0.1:8025.
- Edge logger:
  `EDGE_NAME=webmail EDGE_LISTEN=8200 EDGE_UPSTREAM=8201 EDGE_CONTROL=8210 EDGE_LOG=probe/apps/mail/logs/edge.jsonl node probe/apps/common/edge-log.mjs`
- The webmail seed writes its account password to `state/secrets.json` under the
  `webmail` key. Do not print it.

Order: start Mailpit, then seed the webmail stub, then serve, then start the edge.
Stop in reverse order.
