#!/bin/bash
# Runs the three prototype scenarios and prints a one-line summary of each.
cd "$(dirname "$0")"
for m in normal conflict same_cell; do
  timeout 600 python3 otx.py run_report_$m.json $m > run_log_$m.jsonl 2>&1
  python3 - "$m" <<'PY'
import json, sys
m = sys.argv[1]; r = json.load(open(f"run_report_{m}.json"))
if r.get("outcome") == "true_conflict":
    print(m, "-> true conflict on", r["overlap"], "; nothing committed, no effects released")
else:
    ev = {e["msg"]: e for e in r["log"]}
    print(m, "-> winner", r["winner"], "| agreement", r["agreement"], "| replays", r["replays"],
          "| post-commit verified", ev["committed"]["post_commit_verified"], "| notes kept", r["real_notes_preserved"],
          "| user cell kept", r["real_user_cell_preserved"], "| search s", r["search_seconds"], "| total s", r["total_seconds"],
          "| released", ev["effects released"]["released"], "| discarded", ev["effects released"]["discarded"],
          "| noise", r["null_control"]["noise"],
          "| fork divergence KB", {k: round(v["divergence_bytes"]/1024) for k, v in r["forks"].items()})
PY
done
