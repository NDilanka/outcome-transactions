# Checkout app: store and payment provider (ours, not run)

Status: written and syntax-checked. Nothing has started. The run needs the
orchestrator's go-ahead.

Both programs are stand-ins we wrote. They are not production software and move
no money. The payment provider is a test double with a decline card (ending 0002).

## Start order (after go-ahead)

The order matters. The payment provider reads the key that the store's seed
writes into `state/secrets.json`.

1. `node probe/apps/checkout/server.mjs --seed`: resets the store database and
   writes the shopper and admin logins and the provider key to
   `state/secrets.json`. Secrets are not printed.
2. `node probe/apps/checkout/psp.mjs --seed`: resets the provider database.
3. `node probe/apps/checkout/psp.mjs`: listens on 127.0.0.1:8102 and [::1]:8102.
4. `node probe/apps/checkout/server.mjs`: listens on 127.0.0.1:8101. Reads the
   provider key from `state/secrets.json`.
5. Edge logger for the store:
   `EDGE_NAME=checkout EDGE_LISTEN=8100 EDGE_UPSTREAM=8101 EDGE_CONTROL=8110 EDGE_LOG=probe/apps/checkout/logs/edge.jsonl node probe/apps/common/edge-log.mjs`

The provider's hosted page is reached on localhost:8102 and 127.0.0.1:8102. The
browser policy allows both. There is no edge in front of the provider.

Stop in reverse order. Delete nothing that is not under `data/` or `logs/`.
