# Windows results: open-document commit and fork backend

Track T5, gate G5, and the open-document part of G6. The goal is computer use that goes straight to the outcome, never commits a wrong result, and never loses the user's work. This file records what was measured on Windows, not what was assumed.

## Outcome

- Committing into a document the user has open works through the app itself. The in-app COM edit passed in all 14 such runs (both apps, clean and dirty). The user's unsaved edit survived, and the commit caused no foreground change and no dialog.
- Plain file writes into an open document are refused in all 14 such runs. Each write fails loudly. The file on disk and the user's edit stay unchanged.
- Holder detection found the open app in 34 of 34 open runs.
- Three limitations matter most. Excel commits cannot be undone by the user, while Word commits can. The Excel fork backend has one passing method, so it has no two-method agreement. One foreground event in Excel is still unexplained.
- Unit 2 offline tests pass 12 of 12. In Excel mode, three clean rounds gave the same outcome each time.

## Known limitations (read first)

1. **Excel commits cannot be undone by the user.** Word puts the agent's in-app edit on the undo stack, so one Ctrl+Z reverts it. Excel does not. In all 7 in-app Excel commit runs, Ctrl+Z reverted nothing. A cell the user types is undone by Ctrl+Z, so the gap is specific to COM edits. For the user, a commit into an open Excel workbook has no undo. This strengthens the case for the preflight gate. Recommendation: require one-click confirm before any commit into an open, dirty Excel document.

2. **The Excel fork backend rests on one passing method.** The Linux prototype commits only when two independent methods agree. In Windows Excel mode, the direct method is an Excel COM edit. The only XML method is the wrong-cell control, which the spec must reject. The null method changes nothing. So no second independent method produces the expected result in Excel. An Excel commit currently rests on one method, the spec checks, and the pre-commit hash recheck. Two-method agreement is shown only for the XML path. Closing this gap needs a second, independent, Excel-capable method.

3. **One foreground event is unexplained (unresolved).** In the first attempt of one focused Excel run, the foreground moved from Excel to the console during the commit. That run was the first to use the AttachThreadInput foreground helper. Six later focused runs did not reproduce it, including a no-commit control with the same timing. The cause is unknown. The watchdog stays in the harness to catch a repeat.

4. **Window counts are weak for Excel.** The watchdog counts top-level windows. Excel workbooks are child windows, so "0 window changes" for Excel says little. Foreground changes are the stronger signal. They were 0 in all 16 PASS runs.

5. **Quit does not end Office in this harness.** In 32 of 34 runs, Office still ran one second after Quit, so the harness killed it. No holder remained after that in any run. The harness kills only the Office process it started.

6. **Two reopen runs have no undo result.** In the two Excel close, replace, reopen runs, the COM object disconnected during the undo probe. Their commit verdicts come from disk state read before the probe, so they stand.

## Environment

- Windows 11 (10.0.26300). Microsoft Office Professional Plus 2021 (Excel and Word 16.0, build 14326), driven through COM with pywin32.
- LibreOffice for Windows is not installed. It was skipped, and nothing was installed.
- Free RAM during runs was 0.27 to 0.9 GB. One Office app ran at a time, and each was closed before the next started.
- D: is NTFS. Block clone is not available, so snapshots are plain copies.

## Unit 1: committing while the user's app has the document open

**Setup.** `windows/unit1/open_doc_experiment.py` opens a base document in Excel or Word through COM. The document is either clean or dirty. A dirty document has an unsaved user edit made through COM: D1 = "user note" in Excel, or an appended "User note" paragraph in Word. The agent's change is B2 = 5000 or "Total: 5000". Each run takes an owner snapshot, commits with one method, verifies the live document and a post-commit copy, probes the undo stack, and then makes the user's own save. A 50 ms watchdog records foreground changes, window changes, and dialogs, tagged by phase. The disk file is read after each step, so a commit that the app later overwrites shows up.

34 runs: 2 apps, each with 9 clean and 8 dirty variants. Records are in `windows/unit1/results/*.json`. The full 34-row table is in `windows/unit1/results/unit1-results.md`.

### Results by method (each row covers one run per app)

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

### What the measurements show

**Plain file writes are refused, and they fail safe.** All 14 refused runs failed with a loud error. The disk file was unchanged, and in dirty runs the user's unsaved edit was intact. After the user's own save, the disk held only the user's state. Office denies replace and rename while it holds the document. The race between the preflight check and the write was not tested.

**Commit through the open app works.** In all 14 in-app runs, the agent's value appeared in the live document. The disk kept the old value until the user saved. After the save, the disk held the agent's value, and in dirty runs the user's edit as well. The user's unsaved edit survived every dirty commit. The commit caused 0 foreground changes and 0 dialogs in all 16 PASS runs.

**Close, replace, reopen also passes.** When the app had closed the document, a file-level replace worked in both apps (clean state only). The reopened document showed the agent's value. This is the state in which Unit 2's file-level commit applies. The Word reopen run recorded one window change, from the reopen.

**Snapshot through the owner works.** Excel `SaveCopyAs` and Word `WordOpenXML` captured the live state in all 34 runs, including the user's unsaved edit in all 16 dirty runs. The file name and dirty flag did not change in any run.

**Holder detection works.** Restart Manager named the holding process (Microsoft Excel or Microsoft Word, with pid) in 34 of 34 open runs. The `~$` owner file was present in every open run. Excel's owner file is exclusively locked while the workbook is open, so it cannot be read (165 bytes). Word's owner file can be read (162 bytes). Its header holds the Windows account name, which the harness does not record. The harness records only the size and whether the file is readable. So an unreadable owner file is a valid signal for Excel only. Restart Manager covers both apps.

**Undo stack.**

- Word: in all 7 in-app runs, the first undo reverted the agent's edit. Redo restored the state. In the dirty Word runs without a commit, the first undo reverted the user's COM edit, so Word COM edits are undoable.
- Excel: in all 7 in-app runs, Ctrl+Z reverted nothing. In 4 of them, the first Ctrl+Z was refused by the harness because Excel was not in front. After activation, the second Ctrl+Z reached Excel and still reverted nothing. The user's own COM edit in the dirty Excel runs was not undone either. That fits the finding that COM edits stay outside Excel's undo stack. The 6 refused Excel runs have no agent edit to undo, so their "nothing" says nothing about undo.
- Dedicated check (`windows/unit1/results/excel_probe_check.txt`, Excel focused): `ExecuteMso("Undo")` raised a COM error. `FindControl(Id=128).Execute()` left the agent's value in place. SendKeys Ctrl+Z left it in place too. A cell typed by the user was undone by Ctrl+Z. The same check also raised a SaveAs COM error and an Excel dialog. That step was part of the check, not a commit.
- Redo restored the document in all 32 runs where the probe ran.

**Measurement caveats.** Each cell ran once, so run-to-run variance was not measured. The watchdog counts top-level windows only. The two base fixtures had the Windows account name in their author fields, which Office wrote when the fixtures were built. The name is now replaced with "fixture", and both files were reopened in Excel and Word (B2 = 1000, paragraphs as expected). Cell and paragraph content did not change. The bytes did, so the fixtures are not byte-identical to the ones the runs used.

## Unit 2: fork backend on Windows

`windows/unit2/` ports the prototype's fork, verify, and commit loop to Windows for .xlsx.

- **Snapshot.** A plain copy of the affected files, hash-checked against the source.
- **Fork.** A subprocess with a private TEMP folder, proxy variables pointed at a dead port, and an in-process socket guard that raises on connect. The guard applies inside the fork process only. OS-level isolation is not applied on Windows, because it would need firewall rules. Every result records this.
- **Verify.** `spec_win.py`, a port of `prototype/spec.py` with xlsx predicates.
- **Commit.** A preflight holder check (Restart Manager and the `~$` file) routes the commit to the owner when the file is open. Otherwise the commit writes a sibling temp file, replaces the real file, re-verifies, and rolls back the saved bytes on any failure. Disjoint user edits trigger a replay on a fresh fork of the current real state, with an optimistic hash recheck, up to three tries.

### Offline (no Office)

- `py -3 windows/unit2/tests_offline.py`: 12 of 12 pass.
- `scenarios.py --offline`: normal committed. Conflict committed after one replay, with the user's C3 = 77 kept. Same cell reported as a true conflict, with the user's B2 = 77 kept and nothing committed. Mutation checks were 6 of 6 correct in each scenario.

### Excel mode, three clean rounds (real Office)

Each round ran `scenarios.py --excel` in its own workspace folder.

| Scenario | Outcome | Replays | Real cells after | Round 1 total s | Round 2 total s | Round 3 total s | Commit s |
|---|---|---|---|---|---|---|---|
| normal | committed, winner f1_direct | 0 | B2 = 5000, notes kept | 12.56 | 9.69 | 5.86 | 0.02 to 0.06 |
| conflict | committed, winner replay1 | 1 | B2 = 5000, user C3 = 77 kept | 15.34 | 12.10 | 14.04 | 0.01 to 0.02 |
| same_cell | true_conflict, nothing committed | 0 | B2 = 77, user edit kept | 14.80 | 15.19 | 11.51 | not run |

- Outcomes were identical in all three rounds. Mutation checks were 6 of 6 correct in every scenario.
- The search phase includes the Excel COM work in each fork, so it dominates each total.
- Divergence was about 11,660 bytes for the direct fork, about 9,340 for the wrong fork, and 0 for the null fork in every round.
- Network guard: installed in each fork. Office COM is allowed, because the socket guard does not cover local COM.

**Preflight with real Excel.** With Excel holding the real `budget.xlsx`, the preflight routed the commit to the owner and left the file unchanged (`windows/unit2/results/preflight_owner_check.txt`).

**What the Excel commit does.** When preflight finds no holder, the commit is a file-level replace of the real file. It is not an owner-path commit through the live app. The owner path is measured in Unit 1. The replace is safe only because preflight checks first, and Office refuses a replace while it holds the file. The check-then-replace race was not tested.

### Gaps

- The Excel fork backend has one passing method (limitation 2).
- User edits are applied between forks, not while a fork is running.
- The derived artifact is `out/q3.csv`, not `out/q3.pdf`. There is no headless renderer here without Office, and Excel PDF export inside forks would serialize them on one app. Regeneration from the merged state on replay is unchanged.
- The outbox and effect firewall are not ported. Forks get the dead proxy and the socket guard instead.
- The `new_office_pids_during_run` field in the Unit 2 logs is sampled after cleanup, so it reads empty by design. It says nothing about whether Excel launched during a run.

## Reproduce

Run from the worktree root `D:\dev\ic-win` (branch `windows-open-doc`). Unit 1 and Unit 2 Excel mode need Word and Excel installed and about 400 MB of free RAM. The runner waits for memory before each launch.

```
py -3 windows\unit1\open_doc_experiment.py bases        # rebuilds the fixtures and scrubs their author fields
py -3 windows\unit1\open_doc_experiment.py matrix       # 34 runs, one Office app at a time
py -3 windows\unit1\open_doc_experiment.py report
py -3 windows\unit1\excel_probe_check.py                # launches Excel
py -3 windows\unit2\tests_offline.py
py -3 windows\unit2\scenarios.py --offline
py -3 windows\unit2\scenarios.py --excel                # launches Excel
py -3 windows\unit2\preflight_owner_check.py            # launches Excel
```
