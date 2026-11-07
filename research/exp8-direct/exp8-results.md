# Exp 8 results: real agents write solve.py, two arms on the same attempts

Owner: T3 (Exp 8 real-agent executor). Branch `exp8-direct-agent`. Judge: Sol (orchestrator judge agent). I did not judge.
Labels: **measured** (read from a run file or script output), **inferred** (derived from timestamps or a rule), **guess** (estimate, not measured).

## Answer first

- Judge-only (arm A) committed a correct outcome with zero clicks on 15 of 18 requests (83%), and one wrong outcome. Two-key (arm B) committed correctly on 7 of 18 (39%) and wrong on 2. The spec key did not reduce wrong commits here. All four spec-accepted wrong end states were also judge-accepted, so the two keys cannot filter them. On ecc2413d the spec filter left only the wrong candidate, and B committed it where A committed the correct one. **Measured.**
- No arm passes the safety gate G1. We have 18 requests and 10 wrong end states. A 95% upper bound of 1% needs at least 300 requests with zero wrong commits. **Measured, and a sample-size fact.**
- Speed fails G3 by a wide margin. Median time per attempt is about 39 s before the judge and about 54 s with a rough judge estimate. Per request (slowest of four candidates) the median is 98 s before the judge. Generation of solve.py dominates. **Measured for the executor parts, inferred for generation, guess for judge time.**
- The auto-save task (2cd43775) is unresolved. The judge split near-identical end states, and the harness could not observe auto-save. **Measured.**

## What ran

- 18 LibreOffice requests (calc 6, impress 6, writer 6). Full ids are in `research/exp4b/blind_tasks.json`.
- Four method hints per request: A high-level library, B second library, C headless LibreOffice (UNO), D minimal XML edit.
- Agents under test were subagents that saw only TASK.md and a read-only copy of the start file. Each wrote `solve.py`.
- 84 attempts: 72 primary (52 with no UI block, 20 with a UI block on five tasks: 21760ecb, 550ce7e7, f23acfd2, 66399b0d, ecc2413d) and 12 ablation attempts (no UI block, on 21760ecb, 550ce7e7, 66399b0d). All 84 ran with status OK, and the input files were unchanged. **Measured.** My earlier notes listed three UI-block tasks. The attempt map shows five. **Measured.**
- Ground truth (GT): blind readers, four adjudication passes, second and third readers on single-vote and split codes. Final file `gt/final_gt_v3.tsv`: 74 correct (C), 10 wrong (W), 33 flagged ambiguous. **Measured.** The auto-save verdicts changed in v3 (flagged ambiguous).
- Spec key: frozen executor `research/exp6-executed/specexec.py` at c909d02 (unchanged since). Specs are the Exp 5 grounded specs, committed Nov 6 (95689bc), before any Exp 8 attempt ran. Spec writing time is therefore zero, because the specs were not written for this run. That is not a measurement of spec writing. **Measured.**
- Judge: Sol read 84 packets (end-state dumps, uncapped, leak-checked). Verdicts: 64 accept (33 high, 6 medium, 25 low), 20 reject (14 high, 6 medium). **Measured.**

## Arms

Each request has four candidates. Each arm commits at most one.

- **A (judge only):** commit the judge accept with the highest confidence. Ties go to the lower method index.
- **B (two-key):** AUTO only if the spec is ACCEPT and the judge accepts. Ties as in A.
- **Bs (spec only):** AUTO if the spec is ACCEPT. This is B without the judge.
- Without a commit, the request is a CONFIRM. Each CONFIRM gets a tag: AMBIGUOUS if any candidate has the ambiguity flag, GAP if any spec is UNDECIDED or the spec and judge disagree, otherwise PLAIN.

| Arm | Correct zero-click | 95% CI (exact) | Wrong commits | CONFIRM (AMBIGUOUS / GAP) | Random tie-break expected: correct / wrong / CONFIRM |
|---|---|---|---|---|---|
| A | 15 of 18 (83%) | 59% to 96% | 1 | 2 (2 / 0) | 14.5 / 1.5 / 2.0 |
| B | 7 of 18 (39%) | 17% to 64% | 2 | 9 (7 / 2) | 6.75 / 2.25 / 9.0 |
| Bs | 8 of 18 (44%) | 22% to 69% | 2 | 8 (6 / 2) | 7.75 / 2.25 / 8.0 |

- The random tie-break column replaces deterministic tie-breaks with a uniform pick among the top-confidence candidates (A, B) or among the spec ACCEPTs (Bs). It is the steadier estimate. **Measured (script), with the tie-break rule as the assumption.**
- One-sided 95% upper bound on the wrong-commit rate per request: A 0.24, B 0.31, Bs 0.31. **Measured.**
- Wrong commit for A: d53ff5ee method 2 (de97694c). For B and Bs: d53ff5ee method 2 and ecc2413d method 3 (02d030c7). **Measured.**

## Gates (north-star v2)

| Gate | Target | A | B | Bs | Status |
|---|---|---|---|---|---|
| G0 headline | correct zero-click, all requests, at least 80% | 83% (CI 59 to 96) | 39% | 44% | A meets the point target only. B and Bs fail. |
| G1 safety | wrong AUTO commits = 0; 95% UB at most 1% over at least 300 requests | 1 wrong | 2 wrong | 2 wrong | Fail. 18 requests cannot show it. |
| G1 sensitivity | at most 1% wrong accepts over at least 300 wrong states | not run | 4 of 10 wrong states pass (CI 12% to 74%) | 4 of 10 | Fail. Only 10 wrong states exist. |
| G2 CONFIRM | CONFIRM at most 10% | 11% (2 of 18) | 50% | 44% | A misses by one request. B and Bs fail. |
| G2 GAP | GAP at most 3% | 0% | 11% | 11% | B and Bs fail. |
| G3 speed | median at most 10 s; at least 5x a step-by-step agent | see below | see below | see below | Fail on the 10 s target. The 5x comparison was not run. |
| G7 light | report peak RAM and CPU per request | see below | see below | see below | Reported. No target set. |

- G1 also counts CONFIRM items that a blind 10-second diff reviewer fails to reject. We did not run that reviewer, so that part is not measured.
- Every CONFIRM carries an AMBIGUOUS or GAP tag. **Measured.**

## Speed (G3)

- **Measured:** the executor on the end state takes a median of 0.20 s. The spec check takes a median of 0.62 s (fresh process, rusage).
- **Inferred:** generation time is solve.py mtime minus wave start. Waves ran with 1 to 12 attempts at once, so this is noisy. Median 38 s, p90 107 s, range 9 s to 612 s.
- **Measured:** the judge batch ran from packets commit (10:53 UTC) to verdicts commit (11:14 UTC), 21 min for 84 packets, including two reruns. Per-packet judge time was not measured. It was about 15 s if packets were judged one after another, and up to about 90 s if the six batches ran in parallel. **Guess.**
- Per attempt, before judge: median 39 s. With the 15 s judge estimate: median 54 s, p90 123 s.
- Per request, four candidates in parallel (assumed), slowest candidate: median 98 s before judge, p90 292 s. With the 15 s judge estimate: median 113 s, p90 307 s. With the 90 s judge estimate: median 188 s, p90 382 s.
- Spec writing time is zero (see above). The step-by-step baseline was not run, so the 5x comparison is open.

## Resources (G7)

- Per attempt (solve.py run plus spec check), CPU seconds: median 1.26, p90 3.17, max 4.66. **Measured.**
- Per attempt, peak RSS (larger of the two processes, run one after the other): median 83 MB, p90 247 MB, max 409 MB. The max comes from LibreOffice headless attempts. **Measured.**
- Per request (four candidates): CPU median 5.8 s, max 15.1 s. Peak RSS (largest candidate) median 245 MB, max 409 MB. **Measured.**
- Not measured: the judge's resources, and the subagent's own generation work (including its LibreOffice probes).

## Judge and spec, all 84 attempts

| Spec decision | Judge accept, GT C | Judge accept, GT W | Judge reject, GT C | Judge reject, GT W |
|---|---|---|---|---|
| ACCEPT (38) | 30 | 4 | 4 | 0 |
| REJECT (17) | 9 | 0 | 4 | 4 |
| UNDECIDED (29) | 21 | 0 | 6 | 2 |

- Judge accepts: 64, of which 60 correct (94%). Judge recall on correct end states: 60 of 74 (81%). **Measured.**
- Spec ACCEPT on wrong end states: 4 of 10. Spec REJECT on correct end states: 13 of 74. **Measured.**
- Two-key passes 4 of 10 wrong end states. These are the same four that the judge also accepted. **Measured.**
- Spec predicates across all runs: 319 PASS, 37 FAIL, 84 UNSUPPORTED, 4 ERROR. **Measured.**
- The executor's UNDECIDED is not a safe default for B. For the auto-save request, all four candidates are UNDECIDED (`libreoffice.config` is unsupported). The judge then decides alone. **Measured.**

## Wrong end states (10)

| Blind id | Task | Method | Condition | Ambiguity flag | Spec | Judge | Defect (from GT notes) |
|---|---|---|---|---|---|---|---|
| de97694c | d53ff5ee | 2 | none | Y | ACCEPT | accept, high | Mixed-case text lowercased. Two-key pass. |
| b9d8b59c | d53ff5ee | 4 | none | Y | ACCEPT | accept, high | Unrequested lowercasing. Two-key pass. |
| a6cac88c | d53ff5ee | 3 | none | Y | REJECT | reject, medium | Unrequested lowercasing. |
| 02d030c7 | ecc2413d | 3 | ui | N | ACCEPT | accept, low | Page-break change alters pagination. Two-key pass. |
| 2cd48d90 | 21760ecb | 3 | noui | N | REJECT | reject, high | LibreOffice round trip dropped 9 embedded fonts; unrequested geometry. |
| f624e5ec | 21760ecb | 3 | ui | N | REJECT | reject, high | Shapes moved 3 to 4 cm. |
| e6b4b156 | 66399b0d | 4 | ui | Y | ACCEPT | accept, low | Table placed one paragraph above the cursor. Two-key pass. |
| 3ab6ba1b | 51719eea | 1 | none | Y | REJECT | reject, high | SUMIF table, not a pivot. |
| 3f9e3de2 | 51719eea | 2 | none | N | UNDECIDED | reject, high | Static summary, not a pivot; formulas flattened, formats dropped. |
| f06f57bc | 7ae48c60 | 3 | none | Y | UNDECIDED | reject, high | Shapes on p18 resized to about 20 x 20 cm. |

- Auto-save family (2cd43775) has no wrong state. Its four candidates are all GT C, flagged ambiguous. See below.
- Ablation: the one noui wrong state (2cd48d90) is rejected by both keys, so no arm commits it.

## Auto-save (2cd43775), unresolved

- Candidates: 083c86e1 (method 1), 76604199 (method 3), 81a65c80 (method 4), a9e34228 (method 2). GT: all four C, flagged ambiguous. Spec: UNDECIDED for all four.
- Judge: 083c86e1 accept (high) and 76604199 accept (high). 81a65c80 reject (high) and a9e34228 reject (high). **Measured.**
- Packet contents: 083c86e1, 81a65c80 and a9e34228 show the same `AutoSave Enabled=true` and `TimeIntervall=3`, with no `UserAutoSaveEnabled` line. 76604199 is the only end state that sets `UserAutoSaveEnabled=true`. So the judge accepted 083c86e1 and rejected the other two on the same evidence. **Measured.**
- Behaviour probe: in no run was a document auto-saved, including a 1-minute control with the setting on and one with it off. The harness cannot observe auto-save, so the probe cannot decide. **Measured.**
- Sensitivity: if the three profiles without `UserAutoSaveEnabled=true` count as wrong, arm A becomes 14 correct and 2 wrong (083c86e1 is the committed candidate). Arms B and Bs are unchanged, because the spec is UNDECIDED. **Measured (script).**

## Ablation: UI block (3 requests, 12 attempts per condition)

- Requests: 66399b0d, 550ce7e7, 21760ecb. Arm results match with and without the UI block: A 3 of 3 correct, B 2 of 3, Bs 2 of 3. **Measured.**
- GT correct share: 10 of 12 with UI, 11 of 12 without. **Measured.**
- Some tasks depend on GUI state (cursor, selection). Our UI block did not change request-level outcomes at n = 3, so this does not show that the block is unnecessary. **Inferred.**

## Per-request table (primary 72 attempts)

Method columns follow A to D. GT: C correct, W wrong. Spec: ACC, REJ, UND. Judge: acc or rej, with confidence l, m, h.

| task | GT by method (A-D) | spec | judge (conf) | A commit | B commit | Bs commit | CONFIRM tag |
|---|---|---|---|---|---|---|---|
| 0326d92d | CCCC | UND ACC ACC ACC | acc(l) acc(l) acc(l) acc(l) | 1:C | 2:C | 2:C |  |
| 1273e544 | CCCC | ACC ACC ACC ACC | acc(h) acc(h) acc(h) acc(h) | 1:C | 1:C | 1:C |  |
| 21760ecb | CCWC | ACC ACC REJ ACC | acc(l) acc(h) rej(h) acc(h) | 2:C | 2:C | 1:C |  |
| 2cd43775 | CCCC | UND UND UND UND | acc(h) rej(h) acc(h) rej(h) | 1:C | none | none | AMBIGUOUS |
| 42e0a640 | CCCC | ACC ACC ACC ACC | acc(h) acc(h) acc(h) acc(h) | 1:C | 1:C | 1:C |  |
| 51719eea | WWCC | REJ UND UND UND | rej(h) rej(h) acc(l) acc(l) | 3:C | none | none | AMBIGUOUS |
| 550ce7e7 | CCCC | UND UND REJ UND | acc(h) acc(h) acc(m) acc(h) | 1:C | none | none | AMBIGUOUS |
| 57667013 | CCCC | ACC ACC ACC ACC | acc(h) acc(h) acc(l) acc(h) | 1:C | 1:C | 1:C |  |
| 6054afcb | CCCC | ACC ACC ACC ACC | acc(h) acc(m) acc(m) acc(h) | 1:C | 1:C | 1:C |  |
| 66399b0d | CCCW | ACC ACC ACC ACC | acc(l) acc(l) acc(l) acc(l) | 1:C | 1:C | 1:C |  |
| 6a33f9b9 | CCCC | UND UND UND UND | acc(h) acc(h) acc(h) acc(h) | 1:C | none | none | GAP |
| 7ae48c60 | CCWC | UND UND UND UND | rej(h) rej(h) rej(h) rej(h) | none | none | none | AMBIGUOUS |
| 88fe4b2d | CCCC | UND UND REJ UND | acc(h) acc(h) rej(h) acc(h) | 1:C | none | none | GAP |
| 936321ce | CCCC | UND UND UND UND | acc(h) acc(l) acc(l) rej(h) | 1:C | none | none | AMBIGUOUS |
| a9f325aa | CCCC | ACC ACC ACC ACC | rej(m) rej(m) rej(m) rej(m) | none | none | 1:C | AMBIGUOUS |
| d53ff5ee | CWWW | REJ ACC REJ ACC | acc(m) acc(h) rej(m) acc(h) | 2:W | 2:W | 2:W |  |
| ecc2413d | CCWC | REJ REJ ACC REJ | acc(l) acc(l) acc(l) acc(l) | 1:C | 3:W | 3:W |  |
| f23acfd2 | CCCC | REJ REJ REJ REJ | rej(h) rej(m) acc(h) rej(h) | 3:C | none | none | AMBIGUOUS |

## Defects and limitations

1. Method B hint for xlsx contradicts itself ("pandas with openpyxl engine" and "do not use openpyxl"). 3f9e3de2 flattened formulas and dropped formatting. Fix the hint before reuse.
2. A LibreOffice round trip drops embedded fonts (2cd48d90) and re-serialises packages in several C attempts.
3. Some tasks depend on GUI state. The UI block is a workaround. A snapshot of direct agent work should include selection state where the task needs it.
4. Cursor probe for 66399b0d: 40 Down keys land in an empty paragraph after the table on page 2 (measured via UNO).
5. Executor coverage: 84 predicates UNSUPPORTED (missing attributes on ParaP, CalcSheet, OdtFile, SlideObj, ParaObj, LibreOfficeRoot.config, and parse errors). 4 ERROR, because openpyxl formulas have no cached values. The 2cd43775 spec uses `libreoffice.config`, which is unsupported. These are frozen-executor gaps, not fixed here.
6. Inspector caveats: docx tables were silently capped at 10 rows (8 end states have 11-row tables). The Exp 8 copy of the judge packet builder is uncapped. The Exp 5 code is unchanged. pptx transitions are capped at 300 characters and xlsx at 500 cells; no end state reaches either cap.
7. pptx inspection gap (bullet settings, transitions inside `mc:AlternateContent`) was fixed in `gt_view.py`. It changed 11 pptx verdicts in pass 2, so GT adjudication was unstable on pptx.
8. GT majority vote: three readers on 6 split codes. First and second readers agreed on 64 of 70 single-vote codes.
9. Sample size: 18 requests and 10 wrong end states. The safety gates cannot be met at this sample size.
10. Blind ids are sha256("exp8|" + code), truncated to 12 characters. No secret. Future runs need a private salt.
11. Judge packets were not clipped. The builder asserts no silent cut and passed a word-boundary leak check.
12. Machine noise: other agents' soffice processes were running during the run. My stuck probes were killed. I left other processes alone.
13. Auto-save: unresolved (see above).

## Gate verdict

- G0: point estimate meets 80% for arm A only, and the CI lower bound is below 80%.
- G1: not met by any arm. Not testable at this sample size.
- G2: A misses the 10% CONFIRM cap by one request. B and Bs miss the cap and the GAP cap.
- G3: not met (median well above 10 s). The 5x comparison is open.
- G7: reported, no target.

## Open items

- Measure per-packet judge time (one packet per call, timed).
- Run the blind 10-second diff reviewer on CONFIRM items, to complete G1 as the north-star defines it.
- Decide on executor coverage for `libreoffice.config` and the UNSUPPORTED predicates before any further two-key runs.
- Resolve auto-save with a probe that reads the setting and observes an actual save, or drop the request.
- Run at least 300 requests for G1, and collect more wrong end states for the sensitivity gate.
- Add a private salt to blind ids for future runs.
