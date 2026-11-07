#!/usr/bin/env python3
"""T6 step 4: blinded judge packets for all 80 end states (no-clip asserts via judge_packets_t6)."""
import json, os, sys
sys.path.insert(0, '/home/factory-user/t6-work')
import judge_packets_t6 as jp

T6 = '/home/factory-user/t6-work'
REPO = '/home/factory-user/repos/outcome-transactions'
OUT = os.path.join(REPO, 'research/t6-ambiguity/judge_packets')
MAP = os.path.join(T6, 'private/judge_blind_map.json')
amb = json.load(open(os.path.join(T6, 'private/ambiguity-set.json')))
records = []
for item in amb:
    for state in ('A', 'B'):
        records.append({
            'amb': item['id'], 'state': state, 'request': item['request'],
            'before_root': os.path.join(jp.REPO, 'research/exp5-grounded/snapshots', item['task_id']),
            'after_root': os.path.join(T6, 'endstates', item['id'], state),
        })
bm = jp.build(records, OUT, MAP, shuffle_seed=6)
print('packets written:', len(bm), 'into', OUT)
