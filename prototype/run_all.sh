#!/bin/bash
# Runs every prototype scenario and prints a one-line summary of each; exits 1 if any fails.
cd "$(dirname "$0")"
status=0
for m in normal conflict same_cell clear_cell fault_postcommit race_commit race_rollback insert_row insert_row_same_b2 dup_label; do
  rm -f run_report_$m.json
  timeout 600 python3 otx.py run_report_$m.json $m > run_log_$m.jsonl 2>&1 || status=1
  python3 - "$m" <<'PY' || status=1
import json, sys
m = sys.argv[1]; r = json.load(open(f"run_report_{m}.json"))
ev = {e["msg"]: e for e in r.get("log", [])}
if "transplanted" not in ev:
    # Refused before the commit: say what was refused and what the user's cells hold.
    print(m, "-> refused:", r.get("outcome"), "| committed", r.get("committed"), "| released", r.get("released"),
          "| detail", {k: r[k] for k in ("overlap", "anchor", "base_address", "now_address", "real_b2", "error") if k in r})
else:
    print(m, "-> winner", r["winner"], "| agreement", r["level"], "| replays", r["replays"],
          "| post-commit verified", ev["transplanted"]["post_commit_verified"], "| notes kept", r["real_notes_preserved"],
          "| user cell kept", r["user_c3_kept"], "| search s", r["search_seconds"], "| total s", r["total_seconds"],
          "| released", ev["effects released"]["released"], "| discarded", ev["effects released"]["discarded"], "| rolled back", r["rolled_back"],
          "| noise", r["null_control"]["noise"],
          "| fork divergence KB", {k: round(v["divergence_bytes"]/1024) for k, v in r["forks"].items()})
PY
done
exit $status
