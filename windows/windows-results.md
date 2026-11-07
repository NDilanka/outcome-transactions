# Windows results: open-document commit, revert, race, and fork backend

Track T5, gate G5, and the open-document part of G6. The goal: computer use that goes straight to the outcome, never commits a wrong result, and never loses the user's work. This file records what was measured on Windows. Each number comes from a JSON record under `windows/`.

## Outcome

- **Commit into an open document works through the app.** The main matrix passed all 14 in-app COM runs (both apps, clean and dirty). Variance repeated those 14 cells 3 times each: 41 of 42 runs passed. The one miss is in limitation 3: Excel rejected the agent's write, so nothing was written. The user's unsaved edit survived every passing dirty run. Dialogs: 0 in all 90 variance runs.
- **Plain file writes into an open document are refused.** The main matrix refused all 14 such runs, and variance refused 42 of 42. Each fails loudly. The disk file and the user's edit stay unchanged.
- **Preflight race.** With Excel holding `budget.xlsx` at the replace, the replace was refused loudly in 3 of 3 runs (winerror 5). The file kept its bytes. No overwrite was seen. The first attempt of this test errored before the replace, so it is kept in the record below and is not counted as evidence about the replace.
- **Excel commits can be reverted in one action.** The 24-run revert matrix (8 cases, 3 each) gave the expected result in every run. Formula and merged changes need one confirm. A comment added by the commit is not removed (limitation 1). [REVERT RERUN ON SHIPPED CODE: PENDING]
- **Two-method agreement works for plain workbooks.** The openpyxl method agreed with COM on all 8 compared properties in every gate. A formula workbook is refused, because openpyxl does not keep cached formula results (limitation 2).
- **Variance found two things the main matrix did not show.** First, Excel can reject the in-app write after a focus change (limitation 3). Second, a foreground change during commit appeared in 9 of 90 runs, 8 of them in PASS runs (limitation 4). The main matrix ran each cell once and showed none.
- **Unresolved.** The earlier event (foreground moved from Excel to the console) has not recurred in that form. The variance runs show that other desktop apps take focus during commit. The trigger is not identified.

## Known limitations (read first)

1. **Excel commits have no native undo. A recorded one-action revert covers them, but it leaves comments behind.**
   - Word puts the agent's in-app edit on the undo stack, so one Ctrl+Z reverts it. Excel does not. In all 7 in-app Excel commit runs of the main matrix, Ctrl+Z reverted nothing. A dedicated check also found that `ExecuteMso("Undo")` raised a COM error and that `FindControl(Id=128).Execute()` left the agent's value in place. A cell the user types is undone by Ctrl+Z, so the gap is specific to COM edits.
   - The product needs a guaranteed one-action revert. Before each in-app commit, the harness records the prior value, formula, number format, bold, fill, merged range, and comments of each touched cell. A revert writes those values back through COM. It refuses if the user has changed a touched cell since the commit. It asks for one confirm when the change touches a formula, a merged range, or a comment, because the record does not fully capture those.
   - **Open gap: comment residue.** The record does not capture comments, so a revert cannot remove a comment that the commit added. In all 3 comment runs the agent's comment stayed on B2. The fix is to record comment presence and text. That is not done.
   - This is why the preflight gate must require the record before an in-app Excel commit runs.

2. **Formula workbooks are single-method, and a commit into one needs an explicit confirm.**
   - The second method is openpyxl on the owner snapshot. It shares no code path with COM. Its output is compared through an independent XML reader (`windows/unit2/xlsx_props.py`).
   - On a workbook with a formula (F2 = `=C2*2`, cached value 600), openpyxl drops the cached value (600 becomes empty). It keeps the formula text, merged cells, fill, number format, and column width. Its CSV writes the formula text (`=C2*2`), where COM writes `600`. The spec's preserve check also fails on F2. The gate refuses agreement, so the commit does not run.
   - Recalculating outside Excel would need LibreOffice. It is not installed, and nothing was installed. So a formula workbook commit rests on one method, COM, plus the spec checks, and it needs an explicit confirm.

3. **Excel can reject the in-app write after a focus change.** This was found by variance.
   - In the focused, non-quiet dirty Excel cell (`live-com-focused`), the write to B2 failed with COM error `RPC_E_CALL_REJECTED` (0x80010001), "Call was rejected by callee". The rejection happened before any write, so the file and the user's edit were unchanged. The run was recorded as `status error`, not as a verdict.
   - The cell's record is below. Before the retry, 4 of 7 runs failed this way. None of the four had a focus change during commit, so focus changes do not explain them.
   - A bounded retry was added in `a284a78`. It retries only this error code, for up to 10 seconds (40 tries). Afterwards, 1 of 12 runs failed. In that run, every retry was rejected, and the write never happened. The other 11 runs had no rejected write, so the retry was exercised once. The drop from 4 of 7 to 1 of 12 cannot be credited to the retry. The cause of the intermittent rejection is unknown.
   - In variance, Excel also rejected the undo probe in 4 records and the quit call in 5 records. These calls come after the verdict, so no disk verdict changed. In the 4 records with a rejected probe, the probe did not run.
   - Quiet mode (screen updating off) appeared to help. The 6 quiet, focused Excel runs in variance had no write rejection. Non-focused runs had none either. The sample is small.
   - Product rule, now implemented in `windows/unit1/com_gate.py`. Before any in-app Excel commit, a readiness gate reads `Application.Ready` and one cell. If that does not succeed within 5 seconds, the commit refuses with "Excel busy" and writes nothing.
   - Each write is then a checked step. After a rejection, the target cell is read back. The write is retried only while the cell still holds its value from before the write. Any other value refuses the commit. A rejected write is never left partly applied, and a refused commit rolls back the steps that finished. The rollback is checked the same way.
   - The retry budget is 10 seconds (40 tries), as before. The rule covers the commit and the revert write-back in `revert_experiment.py`.
   - Test: Excel is held busy with a modal Open dialog (see "Forced busy" below). The cause of the intermittent rejection seen in variance is still unknown. The gate catches a busy Excel before the write, and the retry covers a short busy window during it.
   - Word has no gate and no read-back check. Its in-app edit is one COM call on a paragraph. Variance saw no Word rejection in 3 runs per cell, and Word was not forced busy. This is an open gap.

4. **Foreground changes during commit come from other desktop apps, and the trigger is not known.** Variance recorded a foreground change during the commit phase in 9 of 90 runs. Eight of the 9 went to another app, and one went to Excel itself.
   - Seven changes went to Microsoft Edge. One went to the Factory desktop app. One was Excel activating itself when `close-replace-reopen` reopened the workbook, which is expected.
   - A refused plain replace (`excel clean replace`, rep 1) also saw an Edge change. A replace does not activate any window, so the commit method does not cause focus changes.
   - Edge was the foreground window at the start of most runs. In 7 runs it took focus during commit.
   - The earlier event (Excel to the console) has not recurred. In one variance run, Windows Terminal took focus in the open phase.
   - The watchdog stays in the harness to record these changes.

5. **The race was tested in one shape.** Excel opened the file 3 seconds after preflight and before the replace, and held it. Two shapes are not tested: a holder that opens during the replace itself, and a holder whose share mode allows delete.

6. **Window counts are weak for Excel.** The watchdog counts top-level windows. Excel workbooks are child windows, so "0 window changes" for Excel says little. Foreground changes are the stronger signal. The main matrix ran each cell once, and its 16 PASS runs recorded no foreground change during commit. That is not evidence of zero. Variance repeated each PASS cell 3 times and recorded a change in 8 of 48 PASS runs (limitation 4).

7. **Quit does not end Office in this harness.** In 32 of 34 matrix runs, Office still ran one second after Quit, so the harness killed it. No holder remained after that in any run. The harness kills only the Office process it started. Quit was also rejected by Excel in 5 variance records (limitation 3).

8. **Concurrent edits are not tested.** User edits are applied between forks, not while a fork is running.

9. **Isolation is in-process only.** The network guard raises on socket connect inside each fork. OS-level network isolation is not applied on Windows. Office COM is allowed in forks, because the socket guard does not cover local COM.

10. **Not ported:** the outbox and the effect firewall. The derived artifact is `out/q3.csv`, not a PDF.

## Environment

- Windows 11 (10.0.26300). Microsoft Office Professional Plus 2021 (Excel and Word 16.0, build 14326), driven through COM with pywin32.
- LibreOffice for Windows is not installed. It was not installed, by decision.
- Free RAM during runs was about 0.3 to 0.9 GB. One Office app ran at a time, and each was closed before the next started.
- Other desktop apps were running during the variance and the reruns, including Microsoft Edge, the Factory desktop app, and Windows Terminal. Limitation 4 depends on this.
- D: is NTFS. Block clone is not available, so snapshots are plain copies.

## Code state for each result

- The 34-run matrix ran at commit `f4c44ac`.
- The 90-run variance ran before the retry change (`a284a78`). Its output is in `windows/unit1/results/variance/`.
- The four diagnostic reruns of the focused cell ran before the retry change. They are in `results/variance/rep1-retry*`.
- Twelve reruns of the focused cell ran with the retry change. They are in `results/variance-fix/`.
- The revert matrix, Excel gate rounds 2 and 3, and the 14 in-app cells were rerun on `a284a78`. [SHIPPED RERUN: PENDING]

## Unit 1: committing while the user's app has the document open

**Setup.** `windows/unit1/open_doc_experiment.py` opens a base document in Excel or Word through COM. The document is clean or dirty. A dirty document has an unsaved user edit made through COM: D1 = "user note" in Excel, or an appended "User note" paragraph in Word. The agent's change is B2 = 5000 or "Total: 5000". Each run takes an owner snapshot, commits with one method, verifies the live document and a post-commit copy, probes the undo stack, and then makes the user's own save. A 50 ms watchdog records foreground changes, window changes, and dialogs, tagged by phase. The disk file is read after each step, so a commit the app later overwrites shows up. Output is redacted at write time, so the profile name does not appear in results.

### Matrix: 34 runs, once each

Records are in `windows/unit1/results/*.json`. The full table is `windows/unit1/results/unit1-results.md`.

| Method | Clean | Dirty | Result |
|---|---|---|---|
| replace (`os.replace` over the file) | yes | yes | REFUSED, winerror 5 (access denied) |
| sibling rename (remove, then rename) | yes | yes | REFUSED, winerror 32 (sharing violation) |
| in-place write | yes | yes | REFUSED, permission denied |
| reload after replace | yes | no | REFUSED, winerror 5 |
| close, replace, reopen | yes | no | PASS |
| in-app COM edit, no save | yes | yes | PASS |
| in-app COM edit, quiet (screen updating off) | yes | yes | PASS |
| in-app COM edit, quiet, focused | yes | yes | PASS |
| in-app COM edit, focused | no | yes | PASS |
| control (focus only, no commit) | yes | yes | CONTROL |

"Focused" means the document window was brought to the front before the commit. Totals: 16 PASS (14 in-app, 2 close, replace, reopen), 14 REFUSED, and 4 CONTROL.

### Variance: 90 runs, 3 reps of each PASS and REFUSED cell

Records are in `windows/unit1/results/variance/rep1..rep3/`. The summary is `windows/unit1/results/variance/unit1-variance.md`. The foreground column counts foreground changes during the commit phase only.

| App | State | Method | Rep 1 | Rep 2 | Rep 3 | Stable | Foreground changes in commit (reps 1, 2, 3) |
|---|---|---|---|---|---|---|---|
| excel | clean | close-replace-reopen | PASS | PASS | PASS | yes | 1, 1, 0 |
| excel | clean | live-com-quiet-focused | PASS | PASS | PASS | yes | 1, 0, 0 |
| excel | clean | live-com-quiet | PASS | PASS | PASS | yes | 0, 0, 0 |
| excel | clean | live-com | PASS | PASS | PASS | yes | 0, 0, 0 |
| excel | dirty | live-com-focused | status error (write rejected) | PASS | PASS | **no** | 0, 0, 1 |
| excel | dirty | live-com-quiet-focused | PASS | PASS | PASS | yes | 0, 0, 1 |
| excel | dirty | live-com-quiet | PASS | PASS | PASS | yes | 0, 0, 0 |
| excel | dirty | live-com | PASS | PASS | PASS | yes | 0, 0, 0 |
| word | clean | close-replace-reopen | PASS | PASS | PASS | yes | 0, 0, 0 |
| word | clean | live-com-quiet-focused | PASS | PASS | PASS | yes | 0, 0, 0 |
| word | clean | live-com-quiet | PASS | PASS | PASS | yes | 0, 0, 0 |
| word | clean | live-com | PASS | PASS | PASS | yes | 0, 0, 0 |
| word | dirty | live-com-focused | PASS | PASS | PASS | yes | 1, 0, 1 |
| word | dirty | live-com-quiet-focused | PASS | PASS | PASS | yes | 1, 0, 0 |
| word | dirty | live-com-quiet | PASS | PASS | PASS | yes | 0, 0, 0 |
| word | dirty | live-com | PASS | PASS | PASS | yes | 0, 0, 0 |
| excel | clean | inplace | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 |
| excel | clean | reload-after-replace | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 |
| excel | clean | replace | REFUSED | REFUSED | REFUSED | yes | 1, 0, 0 |
| excel | clean | sibling-rename | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 |
| excel | dirty | inplace | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 |
| excel | dirty | replace | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 |
| excel | dirty | sibling-rename | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 |
| word | clean | inplace | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 |
| word | clean | reload-after-replace | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 |
| word | clean | replace | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 |
| word | clean | sibling-rename | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 |
| word | dirty | inplace | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 |
| word | dirty | replace | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 |
| word | dirty | sibling-rename | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 |

- **Totals.** 89 of 90 runs gave the expected verdict. The 42 REFUSED runs all gave REFUSED. Of the 48 PASS-cell runs, 47 gave PASS. The one miss is the rep 1 error in the focused Excel dirty cell (limitation 3).
- **Stability.** 29 of 30 cells gave the same verdict in all 3 reps. The focused Excel dirty cell did not.
- **Dialogs.** 0 in all 90 runs.
- **Foreground changes during commit.** 9 of 90 runs, and 8 of 48 PASS runs (limitation 4). One REFUSED run (plain replace, rep 1) also had one. The other 41 REFUSED runs had none.
- **Other errors after the verdict.** The undo probe or quit was rejected by Excel in 9 records, listed in limitation 3.

### What the matrix and variance show

- **Plain file writes are refused, and they fail safe.** All 56 refused runs (14 matrix, 42 variance) failed with a loud error. The disk file was unchanged. In dirty runs the user's unsaved edit was intact. After the user's save, the disk held only the user's state.
- **Commit through the open app works, with one known rejection.** In the matrix, all 14 in-app runs showed the agent's value in the live document. The disk kept the old value until the user saved. After the save, the disk held the agent's value, and in dirty runs the user's edit as well. In variance, 41 of 42 in-app runs did the same. The 42nd run errored before the write (limitation 3).
- **Close, replace, reopen also passes** in both apps (clean state only). The reopened document showed the agent's value. This is the state in which Unit 2's file-level commit applies.
- **Snapshot through the owner works.** Excel `SaveCopyAs` and Word `WordOpenXML` captured the live state in all 34 matrix runs, including the user's unsaved edit in all 16 dirty runs. The file name and dirty flag did not change.
- **Holder detection works.** Restart Manager named the holding process (Microsoft Excel or Microsoft Word, with pid) in 34 of 34 open runs. The `~$` owner file was present in every open run. Excel's owner file is exclusively locked while the workbook is open, so it cannot be read (165 bytes). Word's owner file can be read (162 bytes). The harness records only the size and whether the file is readable, not its contents.

**Undo stack.**

- Word: in all 7 in-app runs of the matrix, the first undo reverted the agent's edit. Redo restored the state.
- Excel: in all 7 in-app runs of the matrix, Ctrl+Z reverted nothing. The dedicated check (`windows/unit1/results/excel_probe_check.txt`) also found that `ExecuteMso("Undo")` raised a COM error and that `FindControl(Id=128).Execute()` left the agent's value in place. SendKeys Ctrl+Z left it in place too. A cell typed by the user was undone by Ctrl+Z. That is why the revert in limitation 1 is a recorded revert, not an undo.

### Focused Excel dirty cell: the rejected write

| Runs | Code | Result | Where the rejection hit | Focus change during commit |
|---|---|---|---|---|
| Variance reps 1 to 3 | before the retry | rep 1 error; reps 2 and 3 PASS | write to B2 (rep 1) | rep 1 no, rep 3 yes |
| Four diagnostic reruns | before the retry | 3 errors; 1 PASS | write to B2 in 3; undo probe in the PASS run | 0 of the 3 errors |
| Twelve reruns | with the retry (40 tries, 10 s) | 11 PASS; 1 error | write to B2 in the error run (every retry rejected); undo probe in one PASS run | error run yes |

The error runs wrote nothing. The record shows `status error`, and no verdict. The retry changes nothing when Excel accepts the first call, so it does not change the 11 passing runs.

### Race: preflight to replace, Excel holding the file

Harness: `windows/unit2/race_experiment.py`. The commit runs preflight (no holder found), then takes its snapshot, then the injected hook runs. In a race run, the hook opens the real `budget.xlsx` in Excel, keeps it open for 3 seconds, and the replace runs during that window. The control runs the same delay without Excel.

**Attempt 2 (shipped code, commit `3a2849c`).** Records in `windows/unit2/results/race/`.

| Run | Excel held the file at replace | Holders at replace | Outcome | Replace error | File changed | Real B2 | Notes kept | Verdict |
|---|---|---|---|---|---|---|---|---|
| race-1 | yes | 1 | refused | PermissionError winerror 5 | no | 1000 | yes | refused loudly, file unchanged |
| race-2 | yes | 1 | refused | PermissionError winerror 5 | no | 1000 | yes | refused loudly, file unchanged |
| race-3 | yes | 1 | refused | PermissionError winerror 5 | no | 1000 | yes | refused loudly, file unchanged |
| control | no | 0 | committed | none | yes | 5000 | yes | committed, as expected |

No overwrite was seen, so this is not a blocker.

**Attempt 1 (kept, not counted as evidence about the replace).** Records are in `windows/unit2/results/race/attempt1-snapshot-after-hook/`.

| Run | Excel held the file | Outcome | What happened | File changed |
|---|---|---|---|---|
| race-1 | yes | error | `PermissionError` (errno 13) reading `~$budget.xlsx` | no |
| race-2 | yes | error | same | no |
| race-3 | yes | error | same | no |
| control | no | committed | no holder, commit ran | yes |

**Why attempt 1 errored.** The commit took its before-snapshot of the live tree after the injected hook. With Excel holding the file, the snapshot tried to read the locked `~$budget.xlsx` owner file and raised. The exception came before the replace, so the replace never ran. Nothing was written, but the run shows nothing about the replace. It was a harness ordering fault. The outcome also came out as an unhandled error, not a refusal.

**Fix (commit `3a2849c`).** The snapshot now runs before the hook, so the replace is the operation under test. If the snapshot fails because a file is locked, the commit returns `refused` and records the error, instead of raising. The product path has the same exposure: a holder that appears between preflight and snapshot now refuses instead of raising.

## Unit 2: fork backend on Windows

`windows/unit2/` ports the prototype's fork, verify, and commit loop to Windows for .xlsx.

- **Snapshot.** The owner snapshot comes from Excel `SaveCopyAs` (`owner_snapshot.py`), checked against the real file. Then a plain copy of the affected files, hash-checked against the source.
- **Fork.** A subprocess with a private TEMP folder, proxy variables pointed at a dead port, and an in-process socket guard that raises on connect. OS-level isolation is not applied on Windows, and every result records this.
- **Verify.** `spec_win.py`, a port of `prototype/spec.py` with xlsx predicates.
- **Two methods.** The direct method is an Excel COM edit. The second method is openpyxl on the owner snapshot, with Office COM refused inside its fork. `agreement.py` compares the two. Any round-trip loss on any property refuses agreement. Any disagreement is a method disagreement. A second method that fails verification refuses agreement.
- **Commit.** A preflight holder check (Restart Manager and the `~$` file) routes the commit to the owner when the file is open. Otherwise the commit writes a sibling temp file, replaces the real file, re-verifies, and rolls back the saved bytes on any failure. Disjoint user edits trigger a replay on a fresh fork of the current real state, with an optimistic hash recheck, up to three tries.

### Offline (no Office)

- `py -3 windows/unit2/tests_offline.py`: 18 of 18 pass.
- `scenarios.py --offline`: normal committed. Conflict committed after one replay, with the user's C3 = 77 kept. Same cell reported as a true conflict, with the user's B2 = 77 kept and nothing committed. Mutation checks 6 of 6 correct in each scenario.

### Second method, per property (real Excel, gate round 1)

Records are in `windows/unit2/results/gate-round-1/`.

| Scenario | Outcome | Winner | Second method verified | Round-trip losses | Gate status (8 properties) |
|---|---|---|---|---|---|
| normal | committed | f1_direct | yes | none | all 8 agreed |
| conflict | committed | replay1 | yes | none | all 8 agreed |
| same_cell | true_conflict, nothing committed | f1_direct | yes | none | all 8 agreed |
| features (formula, merge, fill, number format) | agreement_refused, nothing committed | none | no | `value` (F2 cached result) | see below |

The 8 properties are value, formula, number format, bold, fill, merged, column width, and the CSV. On the plain workbook every property agreed in every gate.

On the features workbook the second method lost the cached formula result. F2 went from 600 to empty. Formula text, merge, fill, number format, and column width all survived. The CSV disagreed: COM wrote `600`, openpyxl wrote `=C2*2`. The spec's preserve check failed on F2 for the second method. The gate refused agreement, so the commit did not run. This is the expected refusal for formula workbooks (limitation 2).

### Excel gate rounds on the shipped code

[GATE ROUNDS 2 AND 3 ON SHIPPED CODE: PENDING]

### Excel mode, three earlier rounds

These rounds ran before the second method and before the snapshot-ordering change. They are kept as recorded. Outcomes did not depend on either change.

| Scenario | Outcome | Replays | Real cells after | Round 1 total s | Round 2 total s | Round 3 total s | Commit s |
|---|---|---|---|---|---|---|---|
| normal | committed, winner f1_direct | 0 | B2 = 5000, notes kept | 12.56 | 9.69 | 5.86 | 0.02 to 0.06 |
| conflict | committed, winner replay1 | 1 | B2 = 5000, user C3 = 77 kept | 15.34 | 12.10 | 14.04 | 0.01 to 0.02 |
| same_cell | true_conflict, nothing committed | 0 | B2 = 77, user edit kept | 14.80 | 15.19 | 11.51 | not run |

Outcomes were identical in all three rounds. Divergence was about 11,660 bytes for the direct fork, about 9,340 for the wrong fork, and 0 for the null fork. The search phase includes the Excel COM work in each fork, so it dominates each total.

**Preflight with real Excel.** With Excel holding the real `budget.xlsx`, the preflight routed the commit to the owner and left the file unchanged (`windows/unit2/results/preflight_owner_check.txt`).

**What the Excel commit does.** When preflight finds no holder, the commit is a file-level replace of the real file. It is not an owner-path commit through the live app. The owner path is measured in Unit 1. The replace is safe because preflight checks first and Office refuses a replace while it holds the file. The race test above checks the window between preflight and replace in one shape.

### Gaps

- Formula workbooks are single-method (limitation 2).
- User edits are applied between forks, not while a fork is running.
- The derived artifact is `out/q3.csv`, not `out/q3.pdf`. There is no headless renderer here without Office, and Excel PDF export inside forks would serialize them on one app.
- The outbox and effect firewall are not ported. Forks get the dead proxy and the socket guard instead.
- The `new_office_pids_during_run` field in the Unit 2 logs is sampled after cleanup, so it reads empty by design. It says nothing about whether Excel launched during a run.

## Reproduce

Run from the worktree root `D:\dev\ic-win` (branch `windows-open-doc`). Unit 1 and Unit 2 Excel mode need Word and Excel installed and about 400 MB of free RAM. The runner waits for memory before each launch.

```
py -3 windows\unit1\open_doc_experiment.py bases        # rebuilds the fixtures and scrubs their author fields
py -3 windows\unit1\open_doc_experiment.py matrix       # 34 runs, one Office app at a time
py -3 windows\unit1\open_doc_experiment.py report
py -3 windows\unit1\variance_runs.py                    # 90 runs: 3 reps of 16 PASS + 14 REFUSED cells
py -3 windows\unit1\variance_runs.py --summary-only
py -3 windows\unit1\excel_probe_check.py                # launches Excel
py -3 windows\unit1\revert_experiment.py fixture        # launches Excel
py -3 windows\unit1\revert_experiment.py matrix         # 24 runs, launches Excel
py -3 windows\unit2\tests_offline.py                    # 18 tests
py -3 windows\unit2\scenarios.py --offline
py -3 windows\unit2\scenarios.py --excel                # launches Excel
py -3 windows\unit2\race_experiment.py                  # launches Excel
py -3 windows\unit2\preflight_owner_check.py            # launches Excel
```
