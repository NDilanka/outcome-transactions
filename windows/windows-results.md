# Windows results: open-document commit, busy handling, revert, race, and fork backend

Track T5, gate G5, and the open-document part of G6. The goal: computer use that goes straight to the outcome, never commits a wrong result, and never loses the user's work. This file records what was measured on Windows. Each number comes from a JSON record under `windows/`.

Version 2 adds the Word readiness gate, the Excel busy matrix history, and a final chain run on the committed code (`9c19480`). Numbers marked "chain" come from that run.

## Outcome

- **Commit into an open document works through the app, in Excel and Word.** The main matrix passed all 14 in-app COM runs. Variance repeated those 14 cells 3 times each: 41 of 42 runs passed. The one miss is limitation 3. The chain reran the 14 in-app cells on the committed code, and all 14 passed (7 Excel, 7 Word). The user's unsaved edit survived every passing dirty run.
- **Excel refuses cleanly while it is busy.** A modal dialog makes Excel turn away calls from other processes. Each forced-busy attempt runs 21 commits (7 cases, 3 reps each). Attempts 1 and 3 scored 15 of 21, with the same six runs wrong each time. Attempts 4 and 5 scored 20 of 21. Attempt 6, on the committed code, scored 21 of 21 with no errors. Every failed run is kept in the attempt table below.
- **Word had the same gap, and the gap is fixed.** A modal Word dialog made the committed Word write raise an unclassified COM error. The commit neither refused nor reported the value as unknown. Word now has the Excel gate, timed calls, checked writes, and reconcile. On the committed code, all four Word cases give the expected answer. The real modal dialog is refused as "Word busy" in 5.0 s. The other three cases inject a prompt or a delay inside the write call to test the timeout path. This file labels them SYNTHETIC. Each one ends as unknown or refused, and the paragraph reads "Total: 1000" at the answer.
- **The real Word commit has no measured hang path.** Under every condition tested (read-only file, file changed on disk, protected document, and a modal dialog), the commit's write returned or raised within 0.69 s. The commit calls no Save, SaveAs, Close, or Quit, so the real Word prompts that block on those calls do not sit on its path. The Word timeout cases show what the commit does if a write hangs. They do not show that a real hang happens.
- **Plain file writes into an open document are refused.** The main matrix refused all 14 such runs, and variance refused 42 of 42. Each fails loudly. The disk file and the user's edit stay unchanged.
- **Preflight race.** With Excel holding `budget.xlsx` at the replace, the replace was refused loudly in 3 of 3 runs (winerror 5). The file kept its bytes. No overwrite was seen. The first attempt of this test errored before the replace, so it is kept in the record below and is not counted as evidence about the replace.
- **Excel commits can be reverted in one action.** The 24-run revert matrix (8 cases, 3 each) gave the expected result in every run on `a284a78`. On the committed code, all 24 runs are CORRECT. Formula and merged changes need one confirm. A comment added by the commit is not removed (limitation 1).
- **Two-method agreement works for plain workbooks.** The openpyxl method agreed with COM on all 8 compared properties in every gate. A formula workbook is refused, because openpyxl does not keep cached formula results (limitation 2).
- **Variance found two things the main matrix did not show.** First, Excel can turn away the in-app write after a focus change (limitation 3). Second, a foreground change during commit appeared in 9 of 90 runs, 8 of them in PASS runs (limitation 4). The main matrix ran each cell once and showed none.
- **Foreground changes do not come from the commit.** A control run with no commit recorded a foreground event in the harness's commit phase in 3 of 10 runs (`results/control-fg-a284a78`, runs 6, 8, and 10). The control makes no commit, so the commit cannot cause those events. On the committed code, 4 of 10 control runs recorded one (`results/control-fg`, runs 2, 3, 4, and 10). Every event in the commit phase on the committed code, in the controls and in the passing cells, went to Microsoft Edge. The trigger of the foreground changes is still not known.

## Known limitations (read first)

1. **Excel commits have no native undo. A recorded one-action revert covers them, but it leaves comments behind.**
   - Word puts the agent's in-app edit on the undo stack, so one Ctrl+Z reverts it. Excel does not. In all 7 in-app Excel commit runs of the main matrix, Ctrl+Z reverted nothing. A dedicated check also found that `ExecuteMso("Undo")` raised a COM error and that `FindControl(Id=128).Execute()` left the agent's value in place. A cell the user types is undone by Ctrl+Z, so the gap is specific to COM edits.
   - On the committed code, the 7 in-app Word cells each show the same behaviour (7 of 7). The first undo reverts the agent's edit, and redo restores it.
   - The product needs a guaranteed one-action revert. Before each in-app commit, the harness records the prior value, formula, number format, bold, fill, merged range, and comments of each touched cell. A revert writes those values back through COM. It refuses if the user has changed a touched cell since the commit. It asks for one confirm when the change touches a formula, a merged range, or a comment, because the record does not fully capture those.
   - **Open gap: comment residue.** The record does not capture comments, so a revert cannot remove a comment that the commit added. In all 3 comment runs the agent's comment stayed on B2. The fix is to record comment presence and text. That is not done.
   - This is why the preflight gate must require the record before an in-app Excel commit runs.

2. **Formula workbooks are single-method, and a commit into one needs an explicit confirm.**
   - The second method is openpyxl on the owner snapshot. It shares no code path with COM. Its output is compared through an independent XML reader (`windows/unit2/xlsx_props.py`).
   - On a workbook with a formula (F2 = `=C2*2`, cached value 600), openpyxl drops the cached value (600 becomes empty). It keeps the formula text, merged cells, fill, number format, and column width. Its CSV writes the formula text (`=C2*2`), where COM writes `600`. The spec's preserve check also fails on F2. The gate refuses agreement, so the commit does not run.
   - Recalculating outside Excel would need LibreOffice. It is not installed, and nothing was installed. So a formula workbook commit rests on one method, COM, plus the spec checks, and it needs an explicit confirm.

3. **Excel can turn away the in-app write while it is busy. The cause of the intermittent rejection seen in variance is not known.**
   - In the focused, non-quiet dirty Excel cell (`live-com-focused`), the write to B2 failed with COM error `RPC_E_CALL_REJECTED` (0x80010001), "Call was rejected by callee". The rejection happened before any write, so the file and the user's edit were unchanged. The run was recorded as `status error`, not as a verdict.
   - Before the retry, 4 of 7 runs failed this way. None of the four had a focus change during commit, so focus changes do not explain them.
   - A bounded retry was added in `a284a78`. It retries only this error code, for up to 10 seconds (40 tries). Afterwards, 1 of 12 runs failed. In that run, every retry was rejected, and the write never happened. The other 11 runs had no rejected write, so the retry was exercised once. The drop from 4 of 7 to 1 of 12 cannot be credited to the retry. The cause of the intermittent rejection is unknown.
   - In variance, Excel also rejected the undo probe in 4 records and the quit call in 5 records. These calls come after the verdict, so no disk verdict changed. In the 4 records with a rejected probe, the probe did not run.
   - Quiet mode (screen updating off) appeared to help. The 6 quiet, focused Excel runs in variance had no write rejection. Non-focused runs had none either. The sample is small.
   - Product rule, in `windows/unit1/com_gate.py`. Before any in-app Excel commit, a readiness gate reads `Application.Ready` and one cell. If that does not succeed within 5 seconds, the commit refuses with "Excel busy" and writes nothing.
   - Each write is a checked step. After a rejection, the target cell is read back. The write is retried only while the cell still holds its value from before the write. Any other value refuses the commit. A refused commit rolls back the steps that finished, and the rollback is checked the same way.
   - A call that does not return within 5 seconds is an outcome unknown until the reconcile step settles it. The section "Forced busy and in-call prompts" gives the budgets and the tests.
   - Test: a modal Open dialog holds Excel busy. The gate refused every busy run, and the write retry recovered from a dialog that closed 3 seconds into the write. The cause of the intermittent rejection seen in variance is still unknown.

4. **Foreground changes come from other desktop apps. The trigger is not known.** Variance recorded a foreground change during the commit phase in 9 of 90 runs. Eight of the 9 went to another app, and one went to Excel itself.
   - Seven changes went to Microsoft Edge. One went to the Factory desktop app. One was Excel activating itself when `close-replace-reopen` reopened the workbook, which is expected.
   - A refused plain replace (`excel clean replace`, rep 1) also saw an Edge change. A replace does not activate any window, so the commit method does not cause focus changes.
   - Edge was the foreground window at the start of most runs. In 7 runs it took focus during commit.
   - A control run with no commit (`results/control-fg-a284a78`) recorded foreground events in the phase the harness labels commit, in 3 of 10 runs (runs 6, 8, and 10, all Word). The control makes no commit, so this change is background noise. That resolves the single earlier event (Excel to the console), which has not recurred in that form. The committed-code control (`results/control-fg/`) gave 4 of 10: runs 2, 3, and 4 in Excel and run 10 in Word, all to Microsoft Edge.
   - The watchdog stays in the harness to record these changes.

5. **The race was tested in one shape.** Excel opened the file 3 seconds after preflight and before the replace, and held it. Two shapes are not tested: a holder that opens during the replace itself, and a holder whose share mode allows delete.

6. **Window counts are weak for Excel.** The watchdog counts top-level windows. Excel workbooks are child windows, so "0 window changes" for Excel says little. Foreground changes are the stronger signal. The main matrix ran each cell once, and its 16 PASS runs recorded no foreground change during commit. That is not evidence of zero. Variance repeated each PASS cell 3 times and recorded a change in 8 of 48 PASS runs (limitation 4).

7. **Quit does not end Office in this harness.** In 32 of 34 matrix runs, Office still ran one second after Quit, so the harness killed it. No holder remained after that in any run. The harness kills only the Office process it started. Quit was also rejected by Excel in 5 variance records (limitation 3).

8. **Concurrent edits are not tested.** User edits are applied between forks, not while a fork is running.

9. **Isolation is in-process only.** The network guard raises on socket connect inside each fork. OS-level network isolation is not applied on Windows. Office COM is allowed in forks, because the socket guard does not cover local COM.

10. **Not ported: the outbox and the effect firewall.** The derived artifact is `out/q3.csv`, not a PDF.

11. **Prompt coverage covers only the prompts tested.**
    - Excel, before the timeout code: a Close with an unsaved edit and a SaveAs over an existing file each hung the call when alerts were on. With alerts off, the same SaveAs returned with no prompt. The commit runs with alerts off, so the prompt is not reached on the commit path. The Excel layer 3 cases turn alerts on inside the write call on purpose (SYNTHETIC).
    - Word: a read-only save prompt (SYNTHETIC, injected inside the write call) and a modal Open dialog (real).
    - Prompts raised by another app, other prompt types, and other Excel and Word paths are not tested.

12. **The Word commit has no measured hang path.** Every Word hang case in this file injects its prompt or delay inside the write call. See "Word cases, before and after the fix."

13. **Time to answer is bounded. The bound was measured on a fake workbook.** The commit has a forward budget of 30 seconds from its start. That covers the gate, the reads and writes, and the reconcile window. The answer budget is 40 seconds. It covers the answer, including the rollback and the first restore attempt. On the committed code the slowest bounds run answered in 39.34 s, on a fake workbook. Real Excel's worst case was not measured. The slowest Word case answered in 25.16 s, with a synthetic prompt that is never answered.
    - In two bounds cases the rollback did not finish, so the answer is `refused_partial`. The cells the rollback did not reach keep the values the commit wrote, and the message names them for the user to check.

14. **Alerts can stay off after a refused commit for a short time.** The alerts restore is a separate step. It retries until it succeeds, the workbook closes, or Excel exits. The refusal message says alerts are temporarily off until the restore succeeds. Each attempt is logged. In attempt 4, one run left alerts off after two turned-away restores. Attempts 5 and 6 include the message and the restore log.

15. **The gate's offline tests depend on timing.** Some tests use 0.3 and 0.5 second windows. Earlier runs under load flaked. The offline suite passed 62 of 62 on the committed code, and again after the chain. The tests are not yet fully deterministic.

16. **The shipped Word cells do not exercise the alerts guard.** The Word cells start with DisplayAlerts at 0, so the commit's set and restore change nothing in them. The Word cases start at -1 and show the restore.

## Environment

- Windows 11 (10.0.26300). Microsoft Office Professional Plus 2021 (Excel and Word 16.0, build 14326), driven through COM with pywin32.
- LibreOffice for Windows is not installed. It was not installed, by decision.
- Free RAM during runs was about 0.3 to 0.9 GB. One Office app ran at a time, and each was closed before the next started.
- Other desktop apps were running during the variance and the reruns, including Microsoft Edge, the Factory desktop app, and Windows Terminal. Limitation 4 depends on this.
- D: is NTFS. Block clone is not available, so snapshots are plain copies.
- During the session the user closed Word windows. The user said Word was not in use, so no Word document check was needed. The record is `windows/unit1/results/user-session-log.md`.

## Code state for each result

- The 34-run matrix ran at commit `f4c44ac`.
- The 90-run variance ran before the retry change (`a284a78`). Its output is in `windows/unit1/results/variance/`.
- The four diagnostic reruns of the focused cell ran before the retry change. They are in `results/variance/rep1-retry*`.
- Twelve reruns of the focused cell ran with the retry change. They are in `results/variance-fix/`.
- The Word cases, the forced-busy matrix, the 14 in-app cells, the 10 foreground controls, the revert matrix, gate rounds 2 and 3, and the bounds ran on the committed code `9c19480` in the final chain. The chain log is `windows/unit1/results/final-chain/chain.log`.
- The Word probes were first run with `windows/unit1/word_probes.py` before a cleanup (dead code removed, repeated call wrappers merged). The cleanup does not change which calls run. The table in "Word probes" is from a re-run of the cleaned script in the committed tree.
- The `a284a78` results stay in `revert-a284a78/`, `shipped-live-a284a78/`, and `control-fg-a284a78/` for comparison.

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

- Word: in all 7 in-app runs of the matrix, the first undo reverted the agent's edit. Redo restored the state. The committed-code cells repeat this (limitation 1).
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

### Forced busy and in-call prompts

The commit runs these steps for Excel and Word. The budgets bind only when a call fails or hangs. A normal commit does not wait on them.

#### What the commit does now

- **Readiness gate (5 s).** Before the first write, the commit reads `Application.Ready` and one cell. If the app does not answer within 5 seconds, the commit refuses with "Excel busy" or "Word busy". Nothing is written.
- **Timed calls (5 s each).** Each COM call in the commit has a 5 second limit. A call that does not return in time is an outcome unknown until reconcile settles it.
- **Checked writes (retry 10 s).** After a rejection (`RPC_E_CALL_REJECTED`, `RPC_E_RETRYLATER`, or the turned-away error 0x800AC472), the target is read back. The write is retried, for up to 10 seconds, only while the target still holds its value from before the write.
- **Reconcile (20 s).** A timed-out write is polled on fresh connections for up to 20 seconds. If the write lands late and the commit refuses, the late value is rolled back. If the target cannot be read, the outcome is reported unknown, and the message says so.
- **Alerts guard.** The commit sets DisplayAlerts to False for the write. The restore runs as its own step. It runs only if DisplayAlerts still holds the value the commit set. It stops when the workbook closes or the app exits. Each attempt is logged, and the refusal message says alerts are temporarily off until the restore succeeds.
- **Answer budget.** The commit has a forward budget of 30 seconds from its start. It covers the gate, the reads and writes, and the reconcile window. The answer budget is 40 seconds. It covers the answer, including the rollback and the first restore attempt. The bounds run measures both on the committed code (see "Time to answer").

#### Excel busy matrix: attempt history

Each attempt runs the same 7 cases, 3 reps each. The cases are control, gate-busy, write-retry-ok, write-exhausted, guard-no-prompt, hang-late-yes, and hang-no-answer. Failed runs stay in the table. Each attempt folder keeps its own records.

| Attempt | Code | Result | What it showed | Record |
|---|---|---|---|---|
| 1 | first gate, before the harness fixes | 15 of 21 CORRECT. 6 WRONG: write-retry-ok (3), write-exhausted (3). | Harness: the busy probe read a turned-away Excel as not busy, and the dialog probe ran on the main-thread COM object, which Excel refused (RPC_E_WRONG_THREAD). Product: a DisplayAlerts rollback that Excel turned away was reported as refused_partial. | `results/busy/before-harness-fix/` |
| 2 | two code versions in one run | not counted | The run mixed code versions and was killed partway. It is not valid evidence. | `results/busy/attempt2-partial-killed/` |
| 3 | before the Ready fix | 15 of 21 CORRECT. 6 WRONG: the same six cases. | Ready = False was read as not busy. The write failed with 0x800AC472, and the turned-away read-back (AttributeError) was not classified as busy. | `results/busy/attempt3-before-ready-fix/` |
| 4a | after the Ready fix, the six failing cases only | 6 of 6 CORRECT | The six failing cases pass after the Ready fix. | `results/busy/attempt4a-six-recheck/` |
| 4 | final code before the classification fix | 20 of 21 CORRECT. 1 ERROR: write-retry-ok rep 1. | Harness: the Open dialog did not appear within 15 s, so the run ended in an error. The write hit its budget. The DisplayAlerts restore was turned away twice and left alerts off. A post-commit memory read raised an unhandled error. | `results/busy/attempt4-final-code/` |
| 5 | final code before the classification fix | 20 of 21 CORRECT. 1 WRONG: write-exhausted rep 2. | Product: a write that returned busy after the 5 s call budget was classified as unknown, not refused. `_reconcile` now treats a returned busy as rejected. Re-run of write-exhausted reps 1 to 3 on the fixed code: 3 of 3 CORRECT. | `results/busy/attempt5-final-code/`, `results/busy/write-exhausted-rerun-after-fix/` |
| 6 | committed code `9c19480` | 21 of 21 CORRECT. No errors. | Full matrix, 7 cases of 3 reps, Excel only. | `results/busy/attempt6-final-code/` |

**Before and after the 15 of 21 result.** Attempts 1 and 3 each scored 15 of 21, with the same six runs wrong. The six runs failed for two reasons. The harness read a turned-away Excel as not busy (a harness defect). The commit did not classify the turned-away error (a product gap). Both are fixed. After the fixes, those six cases scored 6 of 6 (attempt 4a). The full matrix then scored 20 of 21 on attempts 4 and 5. Those two failed runs stay in the record: one harness error (attempt 4) and one product classification error (attempt 5). The product error is fixed, and its re-run scored 3 of 3.

#### Attempt 6, per case (chain)

Source: `results/busy/attempt6-final-code/unit1-busy.md`. The disk column is the file after the commit call and after the user's save. "Prior value" means the cell kept its value from before the commit.

| Case | What it tests | Reps 1 to 3: result | Rejections seen | Disk after user save | Verdict |
|---|---|---|---|---|---|
| control | No commit, focus only. | committed, 3 of 3 | 0 | agent edit | 3 of 3 CORRECT |
| gate-busy | Excel busy from the start. | refused "Excel busy" after 19 tries, 3 of 3 | 0 | prior value | 3 of 3 CORRECT |
| guard-no-prompt | Alerts guard, no prompt. | committed, 3 of 3 | 0 | agent edit | 3 of 3 CORRECT |
| hang-late-yes | B2 write returns after the timeout and its value lands. | refused, late value rolled back, 3 of 3 | 0 | prior value | 3 of 3 CORRECT |
| hang-no-answer | B2 write never returns in the reconcile window. | unknown, the cell left for the user to check, 3 of 3 | 0 | prior value | 3 of 3 CORRECT |
| write-exhausted | Every write rejected past the write budget. | refused as busy, value unconfirmed, 3 of 3 | 1 each | prior value | 3 of 3 CORRECT |
| write-retry-ok | Dialog closes 3 s into the write. | committed after the retry, 3 of 3 | 1 each | agent edit | 3 of 3 CORRECT |

The write-retry-ok runs read the cell back after the rejection, found the prior value (1000), and retried. The `hang-no-answer` and `write-exhausted` runs could not read the cell back, because Excel turned those calls away. Their reports say the value is unknown.

#### Excel modal probe

Records: `results/busy/unit1-modal-probe.md`. The probe ran in one process while the harness held an Open dialog up in Excel.

| State | Application.Ready | Application.Name | B2 read | B2 write (unchanged value) | Fresh GetObject(path).Application |
|---|---|---|---|---|---|
| dialog closed | True | ok | ok | ok | ok |
| Open dialog up | False, no error | ok | ok | error 0x800AC472 | turned away |
| Open dialog up, second round | False, no error | ok | ok | error 0x800AC472 | turned away |
| dialog closed again | True | ok | ok | ok | ok |

So a busy Excel answers some reads, refuses writes with 0x800AC472, and reports Ready as False with no error. The gate reads that as busy.

#### Excel prompts inside calls, before the timeout code

These probes ran before the timeout code existed, with no dialog open and no timeout. Each probe runs a real call that makes Excel show a prompt. Records: `results/busy/unit1-hang-repro-prompt-probes.md` and `unit1-hang-repro-saveas-probes.md`, and the `scratch-prompt` rows in `unit1-hang-repro.md`. The header of the prompt-probes file says "with the Open dialog up". That header is wrong for these rows. The probes skip the dialog (`PROMPT_PROBES` in `busy_test.py`). The rows are right.

| Call | Alerts | Outcome | Seconds |
|---|---|---|---|
| Close a workbook with an unsaved edit (`close-prompt`) | on | HUNG: no return within 30 s, child killed | more than 30 |
| Quit with an unsaved edit (`quit-prompt`) | on | returned | 0.04 |
| SaveAs over an existing file (`saveas-prompt`) | on | HUNG: no return within 30 s, child killed | more than 30 |
| SaveAs over an existing file (`saveas-prompt-alerts-off`) | off | returned, no prompt | 0.12 |
| SaveAs over an existing file in a scratch workbook (`scratch-prompt`) | on | HUNG: no return within 30 s, child killed | more than 30 |
| The same, answered Yes after 3 s (`scratch-prompt-answer-yes`) | on | returned after the answer | 4.16 |

The shipped commit under the same save prompt hung for more than 30 seconds (`results/busy/unit1-hang-old-commit-a284a78.md`). This is why the commit turns alerts off for the write, and why the timeout and reconcile exist for the case where a prompt still gets through.

With the Open dialog up, the same calls behave differently. The write, read, save, close, and quit calls raised "Call was rejected by callee" (RPC_E_CALL_REJECTED) in 0.01 to 0.34 seconds. The gate refused with "Excel busy" after 21 tries in 5.07 seconds (`results/busy/unit1-hang-repro-dialog-probes.md`).

#### Word cases, before and after the fix

The Word cases use the same harness shape as the Excel cases. Each case runs in its own child process with a 45 second stage limit. The parent lists the visible Word dialogs while a call is stuck, and kills only the Word PIDs the child started. Records: `results/word/`.

| Case | What it sets up | Kind | Before the fix | After the fix (committed code) |
|---|---|---|---|---|
| modal-dialog | A Word Open dialog is up in the instance. | REAL | Raised an unclassified COM error (RPC_E_CALL_REJECTED) at 0.63 s. The paragraph kept "Total: 1000". WRONG. | Refused as "Word busy" at 5.0 s. The paragraph kept "Total: 1000". Alerts restored. CORRECT |
| prompt-no-answer | A real read-only save prompt, raised inside the write call and not answered during the commit. | SYNTHETIC | HUNG: the commit did not return within 45 s. Killed. | Unknown outcome at 25.16 s. Late outcome unchanged. The paragraph kept "Total: 1000". Alerts restored. CORRECT |
| prompt-answer-8s | The same prompt, answered after 8 seconds. | SYNTHETIC | Raised an unclassified error at 8.05 s. The paragraph kept "Total: 1000". WRONG. | Refused at 10.57 s. The call returned after the timeout, and nothing landed. The paragraph kept "Total: 1000". CORRECT |
| delay-landed-late | An 8 second sleep inside the write call, so the write lands after the timeout. | SYNTHETIC | Returned at 8.02 s. The value "Total: 5000" landed and was not classified. WRONG. | Refused at 8.9 s. The late value was rolled back. The paragraph reads "Total: 1000". CORRECT |

"Before the fix" is the Word commit before this change (`live_agent` sha `eb98e94d63c8`). "After the fix" is the committed code (`live_agent` sha `4c81817c4b74`, commit `9c19480`). Records: `results/word/head-*.json` and `results/word/fixed-*.json`.

Two points about these cases.

- **The modal dialog is the real gap.** Before the fix, a real Word Open dialog made the write raise an unclassified error. After the fix, the commit refuses as "Word busy". This is the test-first reproduction. The commit did not refuse and did not say the value was unknown.
- **The three SYNTHETIC cases test the timeout path, not a measured hang.** Each one injects a real prompt, or a real delay, inside the write call. No test of the shipped commit produced a real hang. A synthetic case shows what the commit does if the write hangs.

The Word cells in the in-app matrix start with DisplayAlerts at 0, so they do not test the alerts guard. The four cases above start at -1 and show the restore.

#### Word probes: which calls hang

Tracked tool: `windows/unit1/word_probes.py`. Records: `results/word/probes/`. Each case runs in a child process. Every stage that has not returned a result has a 25 second limit.

| Case | Condition | Call | Outcome | Seconds | Dialog while stuck |
|---|---|---|---|---|---|
| baseline | write, file as copied | write Paragraphs(2).Range.Text | returned | 0.54 | - |
| readonly-file | write, file read-only on disk when opened | write Paragraphs(2).Range.Text | returned | 0.58 | - |
| changed-on-disk | write, file replaced on disk after it was opened | write Paragraphs(2).Range.Text | returned | 0.37 | - |
| protected | write, document protected for reading only | write Paragraphs(2).Range.Text | raised "You are not allowed to edit this selection because it is protected." | 0.69 | - |
| save-readonly-target | SaveAs2 onto a read-only file, alerts on | SaveAs2 onto readonly-target.docx | HUNG: no result within 25 s | - | "We can't save this file because it's read-only." |
| save-file-in-use | SaveAs2 onto a file another instance holds open | SaveAs2 onto budget.docx | HUNG: no result within 25 s | - | "Word cannot save this file because it is already open elsewhere." |
| open-file-in-use | Documents.Open of a file another instance holds open | Documents.Open of budget.docx | HUNG: no result within 25 s | - | "File In Use" (bosa_sdm_msword) |
| modal-open-dialog | Open dialog up in the instance, readiness reads, then the write | write Paragraphs(2).Range.Text | raised "Call was rejected by callee." | 0.0 | - |

The dialog text is copied from the probe's records.

This run used the cleaned script in the committed tree. Its three write conditions returned in 0.37 to 0.58 s, and the protected write raised its error at 0.69 s. The save and Open prompts hung until the 25 s stage limit. The modal write was rejected at once. An earlier run of the same calls, before the cleanup, gave 0.17 to 0.47 s across the four write conditions, with the same outcomes. Write times vary between runs. The outcomes did not change.

The real Word prompts that block are on Save, SaveAs2, and Documents.Open. The commit calls none of them.

#### DisplayAlerts restore

Found in attempt 4. A write that the harness held past its budget left alerts off after two turned-away restores. The fix:

- The restore is a separate step with its own retries.
- It restores only when the value is still the one the commit set.
- It stops when the workbook closes or the app exits.
- Each attempt is logged, with its outcome.
- Until the restore succeeds, the refusal message says alerts are temporarily off.

The attempt 5 and 6 records carry the message and the restore log. The Word cases show alerts at -1 after each run.

#### Time to answer

The budgets are the constants in `com_gate.py`, and the bounds run uses the production values on a fake workbook. Records: `results/bounds/bounds-worst-case.json`.

| Scenario | Answer | Seconds to answer | Cells at the answer | After the hang was released |
|---|---|---|---|---|
| gate-busy | refused, "Excel busy" | 5.00 | nothing written | not needed |
| gate-hang | refused, "Excel not responding" | 5.01 | nothing written | not needed |
| unknown-at-forward-deadline | unknown: the E2 write had not returned by the end of the reconcile window | 30.01 | B2 and E2 not confirmed; the message says to check them | the E2 write landed (E2 = 6); alerts restored |
| refused-write-start-limit | refused_partial: busy 24 times, target unchanged; the E2 rollback did not return within 5 s | 34.92 | B2, E2, and E3 left for the user to check | alerts restored; B2 = 5000, E2 = 6, E3 = 3 |
| refused-read-hang-at-forward-end | refused_partial: the G2 read did not return; the F2 rollback did not return within 5 s | 39.34 | B2, E2, F2, and G2 left for the user to check | alerts restored; B2 = 5000, E2 = 6, F2 = 7, G2 = 4 |

Every case answered within the 40 s bound. Excel's worst measured case is the 39.34 s row, on a fake workbook. Real Excel's worst case was not measured. The Word worst case is 25.16 s (`prompt-no-answer`, synthetic).

#### Harness defects found along the way

Each defect is listed with the attempt that showed it and its status.

- **The busy probe read exceptions only (attempt 1).** A turned-away lookup returned "not busy". Fixed: the probe reads the turned-away result as busy.
- **The dialog probe ran on the main-thread COM object (attempt 1).** Excel refused the call with RPC_E_WRONG_THREAD, and the probe read the dialog as absent. Fixed: the probe runs on the commit's worker thread.
- **Ready = False was not counted as busy (attempt 3).** Fixed in the gate.
- **The 0x800AC472 turned-away error was not classified (attempt 3).** Fixed.
- **The Open-dialog wait had a 15 second limit (attempt 4, one ERROR).** The run stayed an error and is counted as a failure. Status: not changed in code. Attempt 6 had no errors in 21 runs, so it did not recur there.
- **The post-commit memory read raised an unhandled AttributeError in one run (attempt 4).** Status: not changed in code. Attempt 6 had no errors in 21 runs, so it did not recur there.
- **Returned busy after a timeout was classified as unknown (attempt 5, product).** Fixed in `_reconcile`. Re-run 3 of 3 CORRECT.
- **An early Word repro injected SaveAs2 into a setter (superseded).** It found no block, because the injected call was not the commit's call path. Kept as `results/word/unit1-word-hang-repro.md`. The cases above replace it.
- **The prompt-probes header says "with the Open dialog up" (documentation).** The rows ran with no dialog. The file header is wrong, and this section records the correct condition.
- **The Word probe parent waited forever in a setup stage (found in the re-run of `word_probes.py all`).** A Word recovery prompt ("The last time you opened 'budget.docx', it caused a serious error") appeared during the setup of `open-file-in-use`, before the timed call. The parent only timed out in the launch and call-start stages, so it waited with no limit. Status: fixed. Every stage now times out, and each case writes to its own folder. The cause of the recovery prompt is not confirmed. It is likely a record that Word kept from an earlier case, when the harness killed Word during a save prompt. The stalled run was stopped by PID, and its partial output is not used.

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

### Excel gate rounds on the committed code

Chain run on `9c19480`. Records: `windows/unit2/results/gate-round-2/` and `gate-round-3/`.

| Round | Scenario | Outcome | Winner | Replays | Notes kept | User cell kept | Second method verified | Round-trip losses | Commit s | Total s |
|---|---|---|---|---|---|---|---|---|---|---|
| 2 | normal | committed | f1_direct | 0 | yes | n/a | yes | none | 0.02 | 10.90 |
| 2 | conflict | committed | replay1 | 1 | yes | yes | yes | none | 0.01 | 12.17 |
| 2 | same_cell | true conflict, nothing committed | f1_direct | 0 | yes | yes | yes | none | not run | 18.99 |
| 2 | features | agreement refused, nothing committed | none | 0 | yes | n/a | no | value (F2) | not run | 44.74 |
| 3 | normal | committed | f1_direct | 0 | yes | n/a | yes | none | 0.05 | 21.33 |
| 3 | conflict | committed | replay1 | 1 | yes | yes | yes | none | 0.03 | 23.37 |
| 3 | same_cell | true conflict, nothing committed | f1_direct | 0 | yes | yes | yes | none | not run | 15.51 |
| 3 | features | agreement refused, nothing committed | none | 0 | yes | n/a | no | value (F2) | not run | 10.97 |

Both rounds gave the same outcome as the earlier rounds in every scenario. The mutation checks passed 6 of 6 in every scenario. The network guard was installed in every fork, and Office COM was allowed in the forks. The features workbook is refused by design (limitation 2).

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

Run from the worktree root `D:\dev\ic-win` (branch `windows-open-doc`). Unit 1 and Unit 2 Excel mode need Word and Excel installed and about 400 MB of free RAM. The runner waits for memory before each launch. Run one Office command at a time.

```
py -3 windows\unit1\open_doc_experiment.py bases        # rebuilds the fixtures and scrubs their author fields
py -3 windows\unit1\open_doc_experiment.py matrix       # 34 runs, one Office app at a time
py -3 windows\unit1\open_doc_experiment.py report
py -3 windows\unit1\open_doc_experiment.py run <excel|word> <clean|dirty> <method>   # one in-app cell
py -3 windows\unit1\variance_runs.py                    # 90 runs: 3 reps of 16 PASS + 14 REFUSED cells
py -3 windows\unit1\variance_runs.py --summary-only
py -3 windows\unit1\excel_probe_check.py                # launches Excel
py -3 windows\unit1\revert_experiment.py fixture        # launches Excel
py -3 windows\unit1\revert_experiment.py matrix         # 24 runs, launches Excel
py -3 windows\unit1\busy_test.py matrix                 # forced busy: 7 cases x 3 reps, Excel only
py -3 windows\unit1\busy_test.py hang                   # prompt probes on the pre-timeout code (historical)
py -3 windows\unit1\word_test.py cases --label head|fixed [case ...]   # Word busy and hang cases
py -3 windows\unit1\word_probes.py writes|prompts|modal|all            # which Word calls hang
py -3 windows\unit1\office_guard.py instance-check Word # separate-instance check
py -3 windows\unit1\gate_offline_test.py                # gate tests, no Office
py -3 windows\unit1\bounds_test.py                      # time-to-answer bounds, fake workbook, no Office
py -3 windows\unit2\tests_offline.py                    # 18 tests
py -3 windows\unit2\scenarios.py --offline
py -3 windows\unit2\scenarios.py --excel                # launches Excel
py -3 windows\unit2\race_experiment.py                  # launches Excel
py -3 windows\unit2\preflight_owner_check.py            # launches Excel
```
