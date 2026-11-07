#!/bin/bash
# Runs the prototype scenarios (all of them, or the ones named in MODES) and prints a one-line summary of
# each; exits 1 if any fails. OPEN names scenarios whose required outcome is not met yet (a known, unfixed
# bug). Their failure is printed as OPEN and does not fail the run. An OPEN scenario that starts meeting
# its outcome must leave OPEN, or the run fails.
cd "$(dirname "$0")"
OPEN="race_window dup_sheet dup_sheet_renamed"
status=0
for m in ${MODES:-normal conflict same_cell clear_cell fault_postcommit race_commit race_rollback race_window insert_row insert_row_same_b2 dup_label dup_cached dup_comment dup_space dup_sheet dup_sheet_renamed}; do
  rm -f run_report_$m.json
  timeout 600 python3 otx.py run_report_$m.json $m > run_log_$m.jsonl 2>&1
  rc=$?
  python3 - "$m" "$OPEN" "$rc" <<'PY' || status=1
import json, sys
m, open_modes, rc = sys.argv[1], sys.argv[2].split(), int(sys.argv[3])
r = json.load(open(f"run_report_{m}.json"))
ev = {e["msg"]: e for e in r.get("log", [])}
if "transplanted" not in ev:
    # Refused before the commit: say what was refused and what the user's cells hold.
    print(m, "-> refused:", r.get("outcome"), "| committed", r.get("committed"), "| released", r.get("released"),
          "| detail", {k: r[k] for k in ("overlap", "anchor", "base_address", "now_address", "real_b2", "error") if k in r})
else:
    print(m, "-> winner", r.get("winner"), "| agreement", r.get("level"), "| replays", r.get("replays"),
          "| post-commit verified", ev["transplanted"]["post_commit_verified"], "| notes kept", r.get("real_notes_preserved"),
          "| user cell kept", r.get("user_c3_kept"), "| search s", r.get("search_seconds"), "| total s", r.get("total_seconds"),
          "| released", ev["effects released"]["released"], "| discarded", ev["effects released"]["discarded"], "| rolled back", r.get("rolled_back"),
          "| noise", r.get("null_control", {}).get("noise"),
          "| fork divergence KB", {k: round(v["divergence_bytes"]/1024) for k, v in r.get("forks", {}).items()})
bad = rc != 0 or bool(r.get("mismatches")) or r.get("outcome") == "error"
if m in open_modes:
    if bad:
        print(m, "-> OPEN: required outcome not met (bug not fixed yet) | outcome", r.get("outcome"), "| mismatches", r.get("mismatches"))
        sys.exit(0)
    print(m, "-> OPEN scenario now meets its outcome: remove it from OPEN")
    sys.exit(1)
if bad:
    print(m, "-> FAILED | outcome", r.get("outcome"), "| mismatches", r.get("mismatches"))
sys.exit(1 if bad else 0)
PY
done
exit $status
