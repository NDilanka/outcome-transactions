# Exp 8 results: real agents write solve.py, two arms on the same attempts

Owner: T3 (Exp 8 real-agent executor). Branch `exp8-direct-agent`. Judge: Sol (orchestrator judge agent). I did not judge.
Labels: **measured** (read from a run file or script output), **inferred** (derived from timestamps or a rule), **guess** (estimate, not measured), **post hoc** (chosen after the primary results were seen).
Version 4. Changes from version 3: ground truth is now GT v4, after the orchestrator's rulings on ecc2413d and d53ff5ee (five rows). All arm numbers are recomputed on v4. The post hoc key figure is corrected: A with the key is 14 of 18 (78%), not 15 of 18 (83%). Agreement is dropped as a safety key. The private salt is wired into the packet builder for future runs. The GT issues section is replaced by the GT v4 rulings and evidence.

## Answer first

- **Judge only (arm A) commits a correct outcome with zero clicks on 13 of 18 requests (72%, 95% CI 46.5% to 90.3%).** It commits a wrong outcome on 3. The 80% headline needs 15 of 18, so **A misses the headline target.** **Measured.**
- Post hoc, a second Sol judge pass (commit 29fc5bd) lifts A to 14 of 18 (78%, CI 52.4% to 93.6%) with 2 wrong. The key counts a judge accept only if both passes accept. It was chosen after the primary results, so the primary verdict stays at 72%. The earlier post hoc figure of 83% (15 of 18) was wrong under GT v4. **Measured, post hoc.**
- Two-key (B) commits correctly on 8 of 18 (44%) and wrong on 1. Spec only (Bs) commits correctly on 9 of 18 (50%) and wrong on 1. Both send more requests to CONFIRM than the 10% cap allows, and both have GAP tags above the 3% cap. **Measured.**
- **GT v4 moves ecc2413d.** The LibreOffice render says only candidate m3 adds the requested blank page. That makes A's commit on this request wrong, which cuts A from 14 to 13 correct. It makes B's commit correct. Word was not checked. **Measured (render), inferred (effect on arms).**
- No arm passes the safety gate G1. There are 14 wrong end states in the sample (13 in the primary set). Two-key passes 3 of the 14. A 95% upper bound of 1% needs at least 300 requests with zero wrong commits. **Measured, and a sample-size fact.**
- Speed fails G3. Median time per request is 98 s without the judge (slowest of four candidates, parallel assumed), against a 10 s target. The 5x comparison with a step-by-step agent was not run. **Measured for executor time, inferred for generation time, guess for judge time.**
- The auto-save task (2cd43775) is unresolved. The primary reading counts 083c86e1 wrong, and A commits it. The judge split near-identical profiles, and the harness cannot observe auto-save. **Measured.**
- Agreement is dropped as a safety key (orchestrator ruling). The post hoc policy C commits 10 of 18 correctly, with 2 wrong. The analysis stays in `exp8-agreement.md`. **Measured, hypothesis.**
- Second judge (Gemini): not yet on origin. Policies E and E2 wait for its verdicts. **Pending.**

## What ran

- 18 LibreOffice requests (calc 6, impress 6, writer 6). Full ids are in `research/exp4b/blind_tasks.json`.
- Four method hints per request: A high-level library, B second library, C headless LibreOffice (UNO), D minimal XML edit.
- Agents under test were subagents that saw only TASK.md and a read-only copy of the start file. Each wrote `solve.py`.
- 84 attempts. **Primary: 72** (52 with no UI block; 20 with a UI block on five tasks: 21760ecb, 550ce7e7, f23acfd2, 66399b0d, ecc2413d). **Ablation: 12** (no UI block, on three tasks only: 21760ecb, 550ce7e7, 66399b0d). f23acfd2 and ecc2413d have a UI block but no no-UI comparison. **Measured.**
- All 84 ran with status OK, and the input files were unchanged. **Measured.**
- Ground truth: `gt/final_gt_v4.tsv` (private, not committed). It is built from v3 by `make_gt_v4.py`. v4 has 73 C and 11 W as adjudicated, and 33 flagged ambiguous. With the strict auto-save reading it has 70 C and 14 W (59 C and 13 W in the primary set). **Measured.**
- Spec key: frozen executor `research/exp6-executed/specexec.py` at c909d02 (unchanged since). Specs are the Exp 5 grounded specs, committed Nov 6 (95689bc), before any Exp 8 attempt ran. Spec writing time is therefore zero, because the specs were not written for this run. That is not a measurement of spec writing. **Measured.**
- Judge: Sol read 84 packets (end-state dumps, uncapped, leak-checked). First pass: 64 accept (33 high, 6 medium, 25 low) and 20 reject (14 high, 6 medium). A second, independent pass on the same packets is verified (see the judge section). **Measured.**

## GT reading used in this report

- **Primary: GT v4, strict auto-save.** The end-state profiles of 083c86e1, 81a65c80 and a9e34228 do not set `UserAutoSaveEnabled=true`. 76604199 does. The strict reading counts the first three as wrong. This reading is applied in `metrics.py` (`AUTOSAVE_STRICT_W`). **Orchestrator ruling.**
- **Sensitivity: GT v4 with the auto-save family as adjudicated (all four C).** Only the auto-save numbers differ, as shown in the arms section.
- GT v4 is post hoc. The five changed rows came from rulings made after the primary v3 numbers were seen. See the GT v4 section. **Measured.**

## GT v4: changes, rulings and evidence

| Code | Task, method (condition) | v3 | v4 | Basis |
|---|---|---|---|---|
| 476b080a | ecc2413d, 1 (ui) | C | W | Render: no blank page after page 1. Ruling 1c. |
| eeb4b683 | ecc2413d, 2 (ui) | C | W | Same render result. Ruling 1c. |
| 7b72ebd1 | ecc2413d, 4 (ui) | C | W | Same render result. Ruling 1c. |
| 02d030c7 | ecc2413d, 3 (ui) | W | C | Render: blank page 2 right after page 1, as asked. Ruling 1c. |
| a6cac88c | d53ff5ee, 3 | W | C | Only all-caps text lowercased, the same output as 699226e8 (C). Ruling d53ff5ee, option a. |

Not changed: 6054afcb (all four end states stay C, ruling 1b). The auto-save family is not changed in v4. The strict reading is applied in `metrics.py`.

**ecc2413d (ruling 1c: LibreOffice render is the GT for page layout).** The request asks for "a blank page right after this one", with the cursor on page 1. Each candidate was rendered to PDF with LibreOffice (per-file profile) and read with pypdf. **Measured (`ruling_ecc2413d.py`).**
- Input: 7 pages.
- m1, m2 and m4: 7 pages. Every page's text equals the input page.
- m3: 8 pages. Page 2 is blank. Pages 3 to 8 equal input pages 2 to 7.
- Page 1 equals input page 1 in all four.
- Word was not checked. The render is LibreOffice only. **Measured (LibreOffice), unverified (Word).**
- The frozen spec predicates on the same render also accept m3 only (see the wrong end states and the spec table). So the spec and the render agree with v4. **Measured.**

**d53ff5ee (ruling d53ff5ee, option a: "all uppercase text" means all-caps runs).** Lowercasing ordinary capitals is collateral damage, so it is not the requested edit. `ruling_d53ff5ee.py` counts paragraphs whose text is all-caps (or has a two-letter or longer all-caps word) and checks what each candidate lowercased. **Measured.**
- 699226e8 and a6cac88c: each changes 2 paragraphs, both all-caps. They lower 210 all-caps letters and no ordinary-case letters. Both stay the same content, so both are C.
- de97694c and b9d8b59c: each changes 14 paragraphs, 12 of them ordinary-case. They lower 210 all-caps letters and 21 ordinary-case letters (Presentation, Instruction, Describe, China, Such, What, Please, Do). Both stay W.

**6054afcb (ruling 1b: no change).** The four end states 5a2c5250, d8fa1b66, 4e3dd7f6 and fbd38e91 are identical in every cell value, formula and hidden row. The hidden rows are exactly the rows that contain `=NA()`. All four stay C. **Measured (twin check, `retest_twins.py`).**

### Judge errors recorded against v4

These are judge errors, not GT changes. Counts are measured from the verdict files.

- 699226e8 (C): the second pass rejects it, with the reason "only the all-caps passages were lowercased". That describes a correct edit under the ruling. Judge error.
- a6cac88c (C): both passes reject it (medium). Judge error. The first pass accepts its twin 699226e8.
- 6054afcb: the first pass accepts all four identical end states (two high, two medium). The second pass rejects d8fa1b66 and 4e3dd7f6 (medium), for "whole rows are hidden". Under ruling 1b, hiding the `=NA()` rows is valid, so these rejects are judge errors. Judge inconsistency on identical content. **Measured.**

## Arms

Each request has four candidates. Each arm commits at most one.

- **A (judge only):** commit the judge accept with the highest confidence. Ties go to the lower method index.
- **B (two-key):** AUTO only if the spec is ACCEPT and the judge accepts. Ties as in A.
- **Bs (spec only):** AUTO if the spec is ACCEPT. This is B without the judge.
- Without a commit, the request is a CONFIRM. Each CONFIRM gets a tag: AMBIGUOUS if any candidate has the GT ambiguity flag, GAP if any spec is UNDECIDED or the spec and judge disagree, otherwise PLAIN.

| Arm | Correct zero-click | 95% CI (exact) | Wrong commits | CONFIRM (AMBIGUOUS / GAP) | Random tie-break expected: correct / wrong / CONFIRM |
|---|---|---|---|---|---|
| A | 13 of 18 (72.2%) | 46.5% to 90.3% | 3 | 2 (2 / 0) | 13.5 / 2.5 / 2.0 |
| B | 8 of 18 (44.4%) | 21.5% to 69.2% | 1 | 9 (7 / 2) | 7.75 / 1.25 / 9.0 |
| Bs | 9 of 18 (50.0%) | 26.0% to 74.0% | 1 | 8 (6 / 2) | 8.75 / 1.25 / 8.0 |
| A with key (post hoc) | 14 of 18 (77.8%) | 52.4% to 93.6% | 2 | 2 (2 / 0) | n/a |

- Wrong commits. A: 083c86e1 (2cd43775, auto-save, strict), de97694c (d53ff5ee, method 2) and 476b080a (ecc2413d, method 1). B and Bs: de97694c. With the key, A drops 083c86e1 and commits 76604199 (correct). **Measured.**
- Sensitivity, auto-save as adjudicated (all four C): A 14 of 18 with 2 wrong (de97694c, 476b080a); B 8 and 1; Bs 9 and 1. **Measured (script).**
- The random tie-break column replaces deterministic tie-breaks with a uniform pick among the top-confidence candidates (A, B) or among the spec ACCEPTs (Bs). It is the steadier estimate. **Measured (script), with the tie-break rule as the assumption.**
- One-sided 95% upper bound on the wrong-commit rate per request: A 0.377 (3 of 18), B and Bs 0.238 (1 of 18). A with the key: 0.31 (2 of 18). Zero wrong commits in 18 requests would still leave an upper bound of 0.153. **Measured.**
- The CONFIRM tag AMBIGUOUS uses the GT ambiguity flag. A running system does not have that flag. So AMBIGUOUS is a label for what kind of request it was, not a signal the system had. **Measured (definition).**

## Gates (north-star v2)

| Gate | Target | A | B | Bs | Status |
|---|---|---|---|---|---|
| G0 headline | correct zero-click, all requests, at least 80% | 72% (46.5% to 90.3%). With key, post hoc: 78% | 44% | 50% | A misses by two requests. The key does not reach 80%. B and Bs fail. |
| G1 safety | wrong AUTO commits = 0; 95% UB at most 1% over at least 300 requests | 3 wrong | 1 wrong | 1 wrong | Fail. 18 requests cannot show it. |
| G1 sensitivity | at most 1% wrong accepts over at least 300 wrong states | not run | 3 of 14 wrong states pass both keys (CI 4.7% to 50.8%) | 3 of 14 spec accepts (judge not used) | Fail. Only 14 wrong states exist. |
| G2 CONFIRM | CONFIRM at most 10% | 11% (2 of 18) | 50% | 44% | A misses by one request. B and Bs fail. |
| G2 GAP | GAP at most 3% | 0% | 11% (2 of 18) | 11% (2 of 18) | B and Bs fail. |
| G3 speed | median at most 10 s; at least 5x a step-by-step agent | see below | see below | see below | Fail on the 10 s target. The 5x comparison was not run. |
| G7 light | report peak RAM and CPU per request | see below | see below | see below | Reported. No target set. |

- G1 also counts CONFIRM items that a blind 10-second diff reviewer fails to reject. We did not run that reviewer, so that part is not measured.
- Every CONFIRM carries an AMBIGUOUS or GAP tag. **Measured.** The AMBIGUOUS tag uses GT flags (see above).

## Speed (G3)

- **Measured:** the executor on the end state takes a median of 0.20 s. The spec check takes a median of 0.62 s (fresh process, rusage).
- **Inferred:** generation time is solve.py mtime minus wave start. Waves ran with 1 to 12 attempts at once, so this is noisy. Median 38 s, p90 107 s, range 9 s to 612 s.
- **Measured:** the judge batch ran from packets commit (10:53 UTC) to verdicts commit (11:14 UTC), 21 min for 84 packets, including two reruns. Per-packet judge time was not measured. It was about 15 s if packets were judged one after another, and up to about 90 s if the six batches ran in parallel. **Guess.**
- Per attempt, before judge (all 84): median 39 s. With the 15 s judge estimate: median 54 s, p90 123 s.
- Per request, four candidates in parallel (assumed), slowest candidate (72 primary attempts): median 98 s before judge, p90 292 s. With the 15 s judge estimate run serially: median 113 s, p90 307 s. With the 90 s judge estimate: median 188 s, p90 382 s.
- Spec writing time is zero (see above). The step-by-step baseline was not run, so the 5x comparison is open.

## Resources (G7)

- Per attempt (solve.py run plus spec check), CPU seconds: median 1.26, p90 3.17, max 4.66. **Measured.**
- Per attempt, peak RSS (larger of the two processes, run one after the other): median 83 MB, p90 247 MB, max 409 MB. The max comes from LibreOffice headless attempts. **Measured.**
- Per request (four candidates): CPU median 5.8 s, max 15.1 s. Peak RSS (largest candidate) median 245 MB, max 409 MB. **Measured.**
- Not measured: the judge's resources, and the subagent's own generation work (including its LibreOffice probes).

## Judge and spec, all 84 attempts (GT v4, strict)

| Spec decision | Judge accept, GT C | Judge accept, GT W | Judge reject, GT C | Judge reject, GT W |
|---|---|---|---|---|
| ACCEPT (38) | 31 | 3 | 4 | 0 |
| REJECT (17) | 6 | 3 | 5 | 3 |
| UNDECIDED (29) | 20 | 1 | 4 | 4 |

- Judge accepts: 64, of which 57 correct (89%). Judge recall on correct end states: 57 of 70 (81%). **Measured.**
- Spec ACCEPT on wrong end states: 3 of 14. Spec REJECT on correct end states: 11 of 70. **Measured.**
- Judge rejects on wrong end states: 7 of 14. **Measured.**
- Two-key passes 3 of 14 wrong end states: de97694c, b9d8b59c and e6b4b156. All three are judge-accepted. B commits only de97694c, because method 1 or 2 wins the tie for the other two. **Measured.**
- Spec predicates across all runs: 319 PASS, 37 FAIL, 84 UNSUPPORTED, 4 ERROR. **Measured.**
- The executor's UNDECIDED is not a safe default for B. For the auto-save request, all four candidates are UNDECIDED (`libreoffice.config` is unsupported). The judge then decides alone. **Measured.**

### Judge self-consistency (second pass, post hoc)

- A second, independent Sol pass on all 84 packets is on `origin/exp8-judge-verdicts` at commit 29fc5bd, in `research/exp8-direct/judge_retest/`. It used the same prompt and the same six batches. `retest.py` reads both passes and checks the first pass against the TSV that `metrics.py` uses. **Measured (`retest_output.txt`).**
- The first-pass TSV matches the first-pass files on 84 of 84 packets. The second pass alone: 60 accept, 24 reject. Confidence labels match on 77 of 84. **Measured.**
- Four verdicts flip, all accept to reject: 083c86e1 (accept high, then reject medium), 4e3dd7f6 and d8fa1b66 (both accept medium, then reject medium), and 699226e8 (accept medium, then reject medium). Of the 43 verdicts rated high in both passes, none flipped. **Measured.**
- Under GT v4, the flips remove three correct accepts (4e3dd7f6, d8fa1b66, 699226e8) and one wrong accept (083c86e1, wrong under the strict reading only). **Measured.**
- With the key (accept only if both passes accept): judge accepts fall from 64 to 60 (54 correct, 6 wrong), precision rises from 89.1% to 90.0%, and recall on correct end states falls from 81.4% (57 of 70) to 77.1% (54 of 70). **Measured.**
- The key changes arm A only, on one request (2cd43775). B, Bs, C and D do not change. **Measured.**
- Six wrong accepts survive the key: e6b4b156, de97694c, b9d8b59c, 476b080a, eeb4b683 and 7b72ebd1. Both passes accept all six. The key is a stability filter, not a correctness filter. **Measured.**
- Identical content: the four identical 6054afcb end states get accept verdicts in the first pass, and two of them get reject verdicts in the second. The 699226e8 and a6cac88c pair has the same text and opposite first-pass verdicts. Under GT v4 both are C, so the second-pass rejects of both are judge errors (see GT v4). **Measured.**

## Wrong end states (14: 13 primary, 1 ablation)

The table lists each wrong state, the defect from the GT notes or inspection, and what the judge and spec did. The 14th row is the ablation attempt, which no arm sees. Agreement results for these states are in `exp8-agreement.md`.

| Code | Task | Method | Condition | Ambiguity flag | Spec | Judge | Defect |
|---|---|---|---|---|---|---|---|
| de97694c | d53ff5ee | 2 | none | Y | ACCEPT | accept, high | Lowercased ordinary-case words (Presentation, China, What and others), not only all-caps text. Committed by A, B, Bs, C and D. Passes both keys. |
| b9d8b59c | d53ff5ee | 4 | none | Y | ACCEPT | accept, high | Same edit as de97694c. Passes both keys. Not committed (method 2 wins the tie). |
| e6b4b156 | 66399b0d | 4 | ui | Y | ACCEPT | accept, low | Table placed one paragraph above the cursor. Passes both keys. Not committed (method 1 wins the tie). |
| 476b080a | ecc2413d | 1 | ui | N | REJECT | accept, low | No blank page after page 1 (render: 7 pages, text equal to input). Committed by A and C. Survives the key. |
| eeb4b683 | ecc2413d | 2 | ui | N | REJECT | accept, low | Same as 476b080a. Not committed. Survives the key. |
| 7b72ebd1 | ecc2413d | 4 | ui | N | REJECT | accept, low | Same as 476b080a. Not committed. Survives the key. |
| 083c86e1 | 2cd43775 | 1 | none | Y | UNDECIDED | accept, high | Strict reading: profile without `UserAutoSaveEnabled=true`. Committed by A. Removed by the key. |
| 81a65c80 | 2cd43775 | 4 | none | Y | UNDECIDED | reject, high | Same strict reading. |
| a9e34228 | 2cd43775 | 2 | none | Y | UNDECIDED | reject, high | Same strict reading. |
| 3ab6ba1b | 51719eea | 1 | none | Y | REJECT | reject, high | SUMIF table, not a PivotTable. |
| 3f9e3de2 | 51719eea | 2 | none | N | UNDECIDED | reject, high | Static summary, not a PivotTable. Formulas flattened, formats dropped. |
| f06f57bc | 7ae48c60 | 3 | none | Y | UNDECIDED | reject, high | Many shapes on slide 18 resized. |
| f624e5ec | 21760ecb | 3 | ui | N | REJECT | reject, high | Shapes moved about 4 cm, and an underline added to a URL. |
| 2cd48d90 | 21760ecb | 3 | noui (ablation) | N | REJECT | reject, high | Shapes moved or resized up to about 4 cm. LibreOffice round trip dropped 9 embedded fonts. |

- Judge rejects 7 of the 14 wrong states. The spec rejects 3 more that the judge accepts (the ecc2413d states). Both keys pass 3 (de97694c, b9d8b59c, e6b4b156). The last one, 083c86e1, has an UNDECIDED spec: B abstains on it, and A commits it. **Measured.**
- The ecc2413d states were not caught by the judge, which saw text dumps with no pagination. The spec's render predicates did catch them. **Measured (judge packet contents, spec predicates).**

## Auto-save (2cd43775), unresolved

- Candidates: 083c86e1 (method 1), 76604199 (method 3), 81a65c80 (method 4), a9e34228 (method 2). GT v4 keeps all four as C and flags them ambiguous. Under the strict reading, only 76604199 is C. Spec: UNDECIDED for all four. **Measured.**
- Judge: 083c86e1 accept (high) and 76604199 accept (high). 81a65c80 reject (high) and a9e34228 reject (high). **Measured.**
- Packet contents: 083c86e1, 81a65c80 and a9e34228 show the same `AutoSave Enabled=true` and `TimeIntervall=3`, with no `UserAutoSaveEnabled` line. 76604199 is the only end state that sets `UserAutoSaveEnabled=true`. So the judge accepted 083c86e1 and rejected the other two on the same evidence. **Measured.**
- Behaviour probe: in no run was a document auto-saved, including a 1-minute control with the setting on and one with it off. The harness cannot observe auto-save, so the probe cannot decide. **Measured.**
- Effect on arms: under the strict reading A commits 083c86e1 (tie with 76604199 at high confidence, broken by method order), so A has one of its three wrong commits here. Under GT as adjudicated, A has no wrong commit on this request. B and Bs are unchanged, because the spec is UNDECIDED. **Measured (script).**

## Ablation: UI block (three requests, 12 attempts)

- Requests: 66399b0d, 550ce7e7, 21760ecb. These are the only three tasks with a no-UI run. Arm results match with and without the UI block: A 3 of 3 correct, B 2 of 3, Bs 2 of 3. **Measured.**
- GT correct share: 10 of 12 with UI, 11 of 12 without. **Measured.**
- Wrong states on these three tasks: with UI, f624e5ec (21760ecb, method 3) and e6b4b156 (66399b0d, method 4, primary). Without UI, 2cd48d90 (21760ecb, method 3, ablation only). **Measured.** The v3 list omitted e6b4b156.
- Some tasks depend on GUI state (cursor, selection). Our UI block did not change request-level outcomes at n = 3, so this does not show that the block is unnecessary. **Inferred.**
- Not covered: f23acfd2 and ecc2413d have a UI block in the primary set, with no no-UI comparison. **Measured.**

## Per-request table (primary 72 attempts, GT v4 strict)

GT by method A to D: C correct, W wrong. Spec: ACC, REJ, UND. Judge: acc or rej, with confidence l, m, h. The last column is B's CONFIRM tag (blank when B commits).

| task | GT by method (A-D) | spec | judge (conf) | A commit | B commit | Bs commit | B CONFIRM tag |
|---|---|---|---|---|---|---|---|
| 0326d92d | CCCC | UND ACC ACC ACC | acc(l) acc(l) acc(l) acc(l) | 1:C | 2:C | 2:C | |
| 1273e544 | CCCC | ACC ACC ACC ACC | acc(h) acc(h) acc(h) acc(h) | 1:C | 1:C | 1:C | |
| 21760ecb | CCWC | ACC ACC REJ ACC | acc(l) acc(h) rej(h) acc(h) | 2:C | 2:C | 1:C | |
| 2cd43775 | WWCW | UND UND UND UND | acc(h) rej(h) acc(h) rej(h) | 1:W | none | none | AMBIGUOUS |
| 42e0a640 | CCCC | ACC ACC ACC ACC | acc(h) acc(h) acc(h) acc(h) | 1:C | 1:C | 1:C | |
| 51719eea | WWCC | REJ UND UND UND | rej(h) rej(h) acc(l) acc(l) | 3:C | none | none | AMBIGUOUS |
| 550ce7e7 | CCCC | UND UND REJ UND | acc(h) acc(h) acc(m) acc(h) | 1:C | none | none | AMBIGUOUS |
| 57667013 | CCCC | ACC ACC ACC ACC | acc(h) acc(h) acc(l) acc(h) | 1:C | 1:C | 1:C | |
| 6054afcb | CCCC | ACC ACC ACC ACC | acc(h) acc(m) acc(m) acc(h) | 1:C | 1:C | 1:C | |
| 66399b0d | CCCW | ACC ACC ACC ACC | acc(l) acc(l) acc(l) acc(l) | 1:C | 1:C | 1:C | |
| 6a33f9b9 | CCCC | UND UND UND UND | acc(h) acc(h) acc(h) acc(h) | 1:C | none | none | GAP |
| 7ae48c60 | CCWC | UND UND UND UND | rej(h) rej(h) rej(h) rej(h) | none | none | none | AMBIGUOUS |
| 88fe4b2d | CCCC | UND UND REJ UND | acc(h) acc(h) rej(h) acc(h) | 1:C | none | none | GAP |
| 936321ce | CCCC | UND UND UND UND | acc(h) acc(l) acc(l) rej(h) | 1:C | none | none | AMBIGUOUS |
| a9f325aa | CCCC | ACC ACC ACC ACC | rej(m) rej(m) rej(m) rej(m) | none | none | 1:C | AMBIGUOUS |
| d53ff5ee | CWCW | REJ ACC REJ ACC | acc(m) acc(h) rej(m) acc(h) | 2:W | 2:W | 2:W | |
| ecc2413d | WWCW | REJ REJ ACC REJ | acc(l) acc(l) acc(l) acc(l) | 1:W | 3:C | 3:C | |
| f23acfd2 | CCCC | REJ REJ REJ REJ | rej(h) rej(m) acc(h) rej(h) | 3:C | none | none | AMBIGUOUS |

- For 66399b0d, GT reads CCCW, so method 4 (e6b4b156) is wrong. It is in the candidate set of A, B and Bs, and method 1 wins the tie in each.
- For ecc2413d, the spec agrees with the render: ACCEPT only on m3, which is C under v4. B commits m3 correctly.

## Defects and limitations

1. Method B hint for xlsx contradicts itself ("pandas with openpyxl engine" and "do not use openpyxl"). 3f9e3de2 flattened formulas and dropped formatting. Fix the hint before reuse.
2. A LibreOffice round trip drops embedded fonts (2cd48d90) and re-serialises packages in several C attempts. It also adds run-level markers. These can make identical text look different to the inspector (see `exp8-agreement.md`).
3. Some tasks depend on GUI state. The UI block is a workaround. A snapshot of direct agent work should include selection state where the task needs it. The UI effect was measured on three tasks only.
4. Cursor probe for 66399b0d: 40 Down keys land in an empty paragraph after the table on page 2 (measured via UNO).
5. Executor coverage: 84 predicates UNSUPPORTED (missing attributes on ParaP, CalcSheet, OdtFile, SlideObj, ParaObj, LibreOfficeRoot.config, and parse errors). 4 ERROR, because openpyxl formulas have no cached values. The 2cd43775 spec uses `libreoffice.config`, which is unsupported. These are frozen-executor gaps, not fixed here.
6. Inspector caveats: docx tables were silently capped at 10 rows (8 end states have 11-row tables). The Exp 8 copy of the judge packet builder is uncapped. The Exp 5 code is unchanged. pptx transitions are capped at 300 characters and xlsx at 500 cells; no end state reaches either cap.
7. pptx inspection gap (bullet settings, transitions inside `mc:AlternateContent`) was fixed in `gt_view.py`. It changed 11 pptx verdicts in pass 2, so GT adjudication was unstable on pptx.
8. GT majority vote: three readers on 6 split codes. First and second readers agreed on 64 of 70 single-vote codes.
9. Sample size: 18 requests and 14 wrong end states. The safety gates cannot be met at this sample size.
10. Blind ids. The 84 existing packets use the legacy formula sha256("exp8|" + code), truncated to 12 characters. That formula has no secret, so the ids are mappable: anyone with the attempt codes can recompute them. Rebuilding with `build_judge_packets.py --legacy-unsalted` reproduces the 84 packets and the blind map byte for byte. The builder now uses the private salt by default for future runs, and the salt is not in the repo. Existing packets were not regenerated. **Measured.**
11. Judge packets were not clipped. The builder asserts no silent cut and passed a word-boundary leak check.
12. Machine noise: other agents' soffice processes were running during the run. My stuck probes were killed. I left other processes alone.
13. Auto-save: unresolved (see above).
14. The CONFIRM tag AMBIGUOUS uses GT flags, which a running system does not have (see Arms).
15. GT v4 changes five rows after the primary numbers were seen (see GT v4). The Word render of ecc2413d was not checked.
16. The agreement analysis is post hoc (see `exp8-agreement.md`). It is not a safety key.
17. The judge ran twice with the same prompt. Four of 84 verdicts flip, all accept to reject. The key changes arm A only, and six wrong accepts survive it. **Measured.**
18. The packet builder needs odfpy, xlrd, python-pptx, python-docx, openpyxl, numpy and Pillow. In a scratch rebuild without odfpy, four packets were written with "inspection failed" in place of the document text. The builder now stops on that message. **Measured.**

## Gate verdict

- G0: point estimate for A is 72% (13 of 18), below the 80% target. Post hoc, with the judge self-consistency key, A is 78% (14 of 18). Still below 80%. B and Bs fail. **Measured.**
- G1: not met by any arm. Not testable at this sample size. **Measured.**
- G2: A misses the 10% CONFIRM cap by one request (2 of 18). B and Bs miss the CONFIRM cap, and both miss the 3% GAP cap. **Measured.**
- G3: not met (median well above 10 s). The 5x comparison is open. **Measured.**
- G7: reported, no target. **Measured.**

## Open items

- Second judge (Gemini) on the same 84 packets. Verdicts are not on origin yet. When they land, add policy E (Sol accept and Gemini accept) and E2 (E with Sol's key), against strict GT v4, labelled post hoc.
- Word render check of ecc2413d, if a Word render can be produced. Until then the page-layout GT rests on LibreOffice only.
- Auto-save: resolve with a probe that reads the setting and observes an actual save, or drop the request.
- Measure per-packet judge time (one packet per call, timed).
- Run the blind 10-second diff reviewer on CONFIRM items, to complete G1 as the north-star defines it.
- Decide on executor coverage for `libreoffice.config` and the UNSUPPORTED predicates before any further two-key runs.
- Run at least 300 requests for G1, and collect more wrong end states for the sensitivity gate.
- Agreement: test on more requests with independent method hints before any use (see `exp8-agreement.md`). It is dropped as a safety key.
- Judge key: decide whether a both-passes key is used in any later run. It is post hoc here. Six wrong accepts survive it.
