# Outcome-transaction prototype

A minimal, runnable outcome transaction on a real application (LibreOffice). It shows the full loop: freeze the spec, mutation-test it, fork, search in parallel behind an effect firewall, verify, check agreement, merge-check against the live state, commit, and release only the winner's effects.

Run inside WSL Ubuntu as root (needs `unshare`, overlayfs, Xvfb, openbox, xdotool, LibreOffice, poppler-utils):

```
bash run_all.sh
```

## What one run does

1. `make_workspace.py` creates the "real" workspace: `budget.ods` (bold header, values), `notes.txt`, `out/`.
2. **Snapshot**: copy the real workspace to `snap/`. The real workspace stays live; the "user" keeps editing it.
3. **Frozen spec** (hashed): `budget.ods` B2 == 5000, `out/q3.pdf` exists and contains 5000, footprint = {budget.ods, out/q3.pdf}, all other cells and their styles unchanged.
4. **Mutation tests**: build five wrong outcomes (start state, wrong value, no PDF, collateral cell edit, edit outside footprint) and one correct one. The spec is trusted only if it rejects all five and accepts the correct one.
5. **Forks**: each fork is `unshare --mount --net --pid` + an overlayfs upper layer over `snap/` + private `/tmp`. Network is off; an in-fork proxy (`outbox.py`) holds every outgoing request. Four methods race:
   - `gui`: real LibreOffice GUI driven by keystrokes in its own X server,
   - `direct`: edit the ODS XML, render the PDF headless,
   - `roundtrip`: CSV round trip (right value, destroys formatting, touches notes.txt),
   - `wrong`: edits B3 instead of B2.
   A fifth **null control fork** opens and closes the same app with no task.
6. **Verify** each fork's overlay view against the frozen spec, ignoring paths that the null fork also changed.
7. **Agreement**: if two independent passing methods reach the same semantic outcome, confidence is "verified".
8. **Merge check**: compare the real workspace now with the snapshot. If the user changed a file in the winner's footprint, run a cell-level overlap test. If edits are disjoint, replay the winning method on a fresh fork of the current real state, verify again, and commit only if the real state did not move again (optimistic concurrency, up to 3 tries). If the same cell was changed on both sides, nothing is committed.
9. **Commit** by transplanting the changed files (atomic rename), re-verify on the real workspace, release the winner's held request to a sink, discard the losers'.

## Results (final code, 3 consecutive passes of all scenarios)

| Scenario | User does during search | Result |
|---|---|---|
| normal | appends to notes.txt | gui + direct pass and agree ("verified"); roundtrip rejected (bold lost, notes.txt touched); wrong rejected (B2 = 3, B3 changed). Commit verified, user's notes kept, 1 effect released, 3 discarded. Search 11.8 s, total 16.7 s. |
| conflict | also sets budget.ods C3 = 77 | Overlap test: user C3 vs agent B2 = disjoint. Replay on fresh fork passes; commit keeps both C3 = 77 and B2 = 5000, PDF re-rendered from the merged state. Search 11.7 s, total 14.7 s. |
| same_cell | sets budget.ods B2 = 77 | True conflict on B2. Nothing committed, no effects released. |

Per-fork divergence: 72–81 KB of file data (overlay upper layer). The null fork found one noise path, `.~lock.budget.ods#`.

## Problems found while building it, and the fix for each

| Problem | Fix |
|---|---|
| Fork hung forever: the background proxy inherited the captured stdout pipe | PID namespace with `--kill-child`; all fork processes die with the fork |
| Correct GUI result rejected: killed app left a lock file outside the footprint | **Null control fork**: same app, no task; whatever it changes is noise, found per run with no per-app list |
| Same-file concurrent edit by the user | Cell-level overlap test, then **replay on a fresh fork** + optimistic commit; true overlap goes to the user |
| A file-level merge would leave the derived PDF stale | Replay the method instead of merging bytes, so derived artifacts are regenerated from the merged state |
| Xvfb in a later fork refused to start: stale X lock in shared `/tmp`, with a PID from another namespace | Private `/tmp` per fork |
| Cleanup `pkill -f soffice` killed its own shell | `pkill -x soffice.bin` |

## Limits (not built)

- File-level forks, not whole-machine forks. Experiment 1 measured what whole-process forks would cost; the prototype does not fork RAM.
- The merge test understands ODS cells only. Other formats need their own semantic readers (Experiment 4a counted 57 readers in 12 families for OSWorld).
- Replay re-runs the method; it does not yet rebind volatile values (tokens, timestamps).
- The open-document case (the user has `budget.ods` open with unsaved edits) is designed but not built; see `docs/outcome-transactions.md` §5.8.
