# Exp 7 judge packets with the docx table cap removed (sensitivity set)

This folder holds the 22 judge packets that differ from the packets the judge saw in
`research/exp7-combined/judge_packets/`. All 22 are for one task (66399b0d), and the blind ids are the same
as in that folder.

Why these exist: the packet builder printed only the first 10 rows of each docx table, while the table header
gave the true row count. The task's table has 11 rows, so the judge saw 10 of them. This is a deviation from
Amendment 3 (no truncation in judge packets). The committed packets in `judge_packets/` are the packets the
judge saw, and they are unchanged.

What differs: only the docx table rows in `before_state`, `after_state` and `diff`. The rows are printed in full.
The fix is `research/exp5-grounded/inspect_snapshot.py` line 73, `rows[:10]` changed to `rows`, run with the
Exp 7 packet builder (no other change). The 350 other Exp 7 packets were rebuilt the same way and match the
committed packets in content, so they are not repeated here.

Use: this set is a labelled sensitivity run. The primary Exp 7 result stays on `judge_packets/`.
