# Experiment 5: Grounded spec writing (spec writer sees a read-only copy of the starting state)

Date: 2026-11-06. Follows Experiment 4b (`research/exp4b/results.md`), where 4 failure patterns came mostly from the spec writer not seeing the task's files.

## Question

If the spec writer can inspect a read-only copy of the starting state before freezing the spec, do fewer specs make wrong decisions?

## Setup

1. **Rebuild the starting state.** `fetch.py` downloads the files each task's setup puts on the machine (63 files, 44 tasks, 149 MB). The other 22 tasks start from the OSWorld VM image only, which cannot be rebuilt here. They form a control group: their writers saw no files.
2. **Inspect it.** `inspect_snapshot.py` turns each snapshot into a text report: spreadsheet cells with formulas and styles, document paragraphs and runs, slide shapes, image color statistics (3×3 grid, thirds, main colors with bounding boxes), archive listings, and config files in full. It is generic by file type and contains nothing specific to any task. Writers could also run read-only Python on the snapshot.
3. **Write specs.** Six writers (11 tasks each) got the instruction, the setup steps, the reader conventions from 4b, and the report. They were forbidden to read OSWorld evaluators or any 4b output.
4. **Judge blind and paired.** For each task, a judge from a different lab than the writers got the old 4b spec and the new spec under random labels X and Y. The judge also got the official evaluator, its metric code, and the inspection report, so it could check computed values against the real files. It graded each spec with the 4b rubric and picked the better one. `judge_key.json` holds the label mapping; `score.py` unblinds.

"Wrong" means a spec that would make wrong decisions: over-strict (rejects valid work), looser (accepts wrong work), a less faithful interpretation than the official one, or unverifiable.

## Results (same judge for both arms)

| Group | n | Blind (4b) wrong | Grounded wrong | Grounded better / tie / blind better |
|---|---|---|---|---|
| All tasks | 66 | 24 (36.4%) | **5 (7.6%)** | 51 / 10 / 5 |
| Tasks with starting files | 44 | 19 (43.2%) | **4 (9.1%)** | 37 / 4 / 3 |
| Control: no starting files | 22 | 5 (22.7%) | 1 (4.5%) | 14 / 6 / 2 |
| Official uses a gold file | 24 | 14 (58.3%) | **1 (4.2%)** | 21 / 3 / 0 |

Grounding fixed 20 specs and broke 1. In 4b, half of OSWorld's checkers needed a gold file the user would never have. On exactly those tasks, wrong specs dropped from 58.3% to 4.2%.

Grounded verdicts: 17 equivalent, 40 reasonably stricter, 4 different and more faithful to the request than the official checker, 3 over-strict, 2 looser, 0 unverifiable.

## What caused the improvement (honest attribution)

Two things changed at once: the writers saw the starting state, and the writer instructions were new. The new instructions included "tolerances must accept how a human would do it by hand" and "do not require unrequested secondary settings". The control group isolates the second change. Its writers saw no files, yet its error rate still fell 18 points (22.7% → 4.5%). With files, the rate fell 34 points (43.2% → 9.1%). A rough split: about 18 points from better instructions, about 16 more points from grounding. The groups differ in task mix, so this split is an estimate, not a measurement.

Other caveats:
- **The judge is harsher than 4b's judge.** It rated the 4b blind specs 36.4% wrong, where 4b's own judge said 24.2%. Compare arms only under the same judge, as above.
- **The judge saw the inspection reports.** That lets it verify computed values, which could favor the specs that used them. The blind labels limit this, but don't remove it.
- **One run, one judge per task.** No repeat runs and no inter-judge agreement measured.
- **Specs are judged, not executed.** No agent attempt ran against them. A spec rated correct here can still fail on a real end state.

## Examples of what grounding fixed

- `f918266a` (finish calculator code): blind spec was unverifiable. Grounded writer read the code, found the missing line `arr[j+1] = arr[j]`, and required `log.txt` to be exactly `5 6 11 12 13`.
- `6054afcb` (hide N/A): blind spec hid cell text, a different reading from the official one. Grounded writer saw `=NA()` formulas and required exactly rows 3, 6, 8, 9, 12, 14, 18, 19, 20, 24, 27, 32, 33 hidden.
- `d68204bf` (reorder strips warmest to coolest): blind spec was unverifiable. Grounded writer measured mean red minus blue per third (32.1, 40.3, 50.9) and required the order right, middle, left.
- `8e116af7` (receipts into bookkeeping): blind spec was unverifiable. Grounded writer read all five receipts and computed the five rows and the final balance −3234.79.
- `b52b40a5` (merge attachments): blind spec was looser. Grounded writer unpacked the mail, found three 25-page PDFs, and required one 75-page PDF in part order.

## Remaining wrong specs, and the fix for each

| Task | Problem | Fix |
|---|---|---|
| `f4aec372` center triangle | 10 px tolerance still too tight for a hand drag | **Positive variants** (design 5.3): run a real GUI drag in a fork; the spec must accept it |
| `7ae48c60` picture heights | Inspector did not flag a freeform shape filled with a photo as a picture | **Fixed in the inspector** (`image_fill` flag); not re-run, so this result reflects the old inspector |
| `2b9493d7` kill frozen app | Freezes every background process, though some exit on their own | **Null control fork** (built in the prototype): processes that exit on their own in the null fork are noise |
| `3ce045a0` bigger text | No minimum size of change | **Confirm vague amounts**: the spec states a threshold ("at least 1.2×") and shows it to the user before searching |
| `08c73485` Thunderbird filters | A hidden app default that the starting files don't show | **Behavioral probe**: in a fork, deliver a test message and check that the filter fires, instead of reading config keys |

## Files

`fetch.py`, `inspect_snapshot.py`, `inspections/` (44 reports), `batches/`, `writer_conventions.txt`, `specs/batch_1..6.yaml`, `build_packets.py`, `judge/packets_*.json`, `judge/verdicts_*.json`, `judge_key.json`, `score.py`, `paired_results.json`. Snapshots are not committed; rebuild them with `fetch.py`.
