# Exp 8 post-hoc agreement analysis

Owner: T3 (Exp 8 real-agent executor). Branch `exp8-direct-agent`. Judge: Sol. I did not judge.
Labels: **measured** (script output or file read), **inferred** (from measured facts), **guess** (estimate), **post hoc** (chosen after the primary results were seen).
Version 4. Changes from version 3: a second judge from a different lab (Gemini 4 Argon) judged the same 84 packets. Policies E, E2 and E3 are scored against strict GT v4. All of it is post hoc. Earlier versions: v3 moved all numbers to GT v4 (five rows changed by the orchestrator's rulings, see `exp8-results.md`), resolved the ecc2413d and d53ff5ee questions, corrected the judge-key effect (A with key 14 of 18, not 15), and dropped agreement as a safety key by ruling.

**Status: HYPOTHESIS, dropped as a safety key.** The two agreement policies below were proposed after the primary arm results were known. They were not pre-registered. By orchestrator ruling, agreement is not used as a safety key. This document keeps the analysis only.

Scripts and outputs: `research/exp8-direct/agreement.py` (output in `agreement_output.txt`), `research/exp8-direct/metrics.py` (arms, output in `metrics_output.txt`), and `research/exp8-direct/retest.py` and `retest_twins.py` (judge self-consistency, outputs in `retest_output.txt` and `retest_twins_output.txt`). All use GT v4 with the strict auto-save reading as primary (see `exp8-results.md`).

## Answer first

- Under GT v4 (primary: strict auto-save), policy C commits 10 of 18 requests correctly, with 2 wrong. Policy D commits 9 of 18 correctly, with 1 wrong. Judge-only arm A commits 13 of 18 correctly, with 3 wrong. Neither policy reaches the 80% headline. **Measured.**
- Against A, agreement blocks one wrong commit (083c86e1, the auto-save profile). It costs three correct commits (0326d92d, 51719eea, f23acfd2), where no two methods wrote the same diff. D also loses 66399b0d. CONFIRM rises from 2 (A) to 6 (C) and 8 (D). **Measured.**
- Agreement cannot catch an error that two methods share. d53ff5ee m2 (de97694c) and m4 (b9d8b59c) wrote the same wrong edit, and C commits de97694c. ecc2413d m1 and m4 wrote the same page break, which the render shows is wrong, and C commits m1. **Measured (groups), inferred (cause).**
- Orchestrator ruling: agreement is dropped as a safety key. Kept here as analysis only.
- Judge self-consistency key (verified second Sol pass, commit 29fc5bd): accept only if both passes accept. Four of 84 verdicts flip, all accept to reject. Only arm A changes: 13 correct and 3 wrong becomes 14 and 2, because one flip removes the wrong auto-save accept. B, Bs, C and D do not change. Six wrong accepts survive the key. **Measured.**
- Post hoc, the key moves arm A's G0 point estimate from 72% to 78% (14 of 18, Clopper-Pearson 95% interval 52.4% to 93.6%). An earlier figure of 83% (15 of 18) was wrong under GT v4. The key was chosen after the primary results were seen, so the primary verdict does not change. **Measured, post hoc.**

## Method

- **Signature.** Each end state is compared with the start copy using the GT inspector view (`gt_view.py`). The changed lines only are kept, with whitespace collapsed and sorted. Two attempts agree when their signatures are equal and not empty. No attempt was a no-op. **Measured.**
- **Anchored variant (sensitivity).** Hunks keep one unchanged line of context on each side. This version sees position. It was added after the first sorted run, to test whether the sorted version is blind to position. Anchored gives the same policy counts as sorted on GT v4 (checked). **Measured.**
- **Policy C.** Among the attempts of one request that belong to a group of at least two with the same signature, commit the judge-accepted member with the highest judge confidence. Ties go to the lowest method index. With no qualifying member, the request is a CONFIRM.
- **Policy D.** As C, but only a high-confidence judge accept qualifies.
- **Arms A, B, Bs.** Taken unchanged from `metrics.py`.
- **Limits of the signature.** The inspector view includes run-level markers from the LibreOffice round trip. One example: a6cac88c differs from 699226e8 in one run boundary (a trailing `|` marker) in one paragraph. The document text is identical. So signatures can split identical text on formatting noise. No commit changed because of this here. **Measured.**
- **Limit of independence.** The four methods use one model and the same task text. Agreement between them is partly correlated by design. **Inferred.**

## Results (primary: GT v4, strict auto-save, sorted signatures, 18 requests)

| Arm or policy | Correct, zero click | Wrong commits | CONFIRM (AMBIGUOUS / GAP) |
|---|---|---|---|
| A judge only | 13 of 18 | 3: 2cd43775 083c86e1; d53ff5ee de97694c; ecc2413d 476b080a | 2 (2 / 0) |
| B two-key | 8 of 18 | 1: d53ff5ee de97694c | 9 (7 / 2) |
| Bs spec only | 9 of 18 | 1: same as B | 8 (6 / 2) |
| C agreement, judge accept | 10 of 18 | 2: d53ff5ee de97694c; ecc2413d 476b080a | 6 (5 / 1) |
| D agreement, high-confidence judge | 9 of 18 | 1: d53ff5ee de97694c | 8 (6 / 2) |

**Measured.** Anchored signatures give the same counts for all five rows.

- Agreement groups (sorted): 15 groups, in 14 of 18 requests. Group GT: 12 all correct, 1 mixed (66399b0d), 2 all wrong (d53ff5ee m2 and m4; ecc2413d m1 and m4). Anchored: 13 all correct, 2 all wrong. **Measured.**
- Sensitivity, auto-save as adjudicated (all four C): A 14 correct, 2 wrong; B 8 and 1; Bs 9 and 1; C 10 and 2; D 9 and 1. Agreement does not change, because the auto-save request has no agreement group. **Measured.**

### Per request (primary, sorted signatures)

Each group shows the method and GT of its members. A to D show the commit as method:GT.

| task | agreement groups (method: GT) | A | B | C | D | D CONFIRM tag (blank when D commits) |
|---|---|---|---|---|---|---|
| 0326d92d | none | 1:C | 2:C | none | none | GAP |
| 1273e544 | 1c8e14 {1:C, 2:C, 3:C, 4:C} | 1:C | 1:C | 1:C | 1:C | |
| 21760ecb | 354b38 {1:C, 2:C, 4:C} | 2:C | 2:C | 2:C | 2:C | |
| 2cd43775 | none | 1:W | none | none | none | AMBIGUOUS |
| 42e0a640 | 320b72 {1:C, 2:C}; eabaa1 {3:C, 4:C} | 1:C | 1:C | 1:C | 1:C | |
| 51719eea | none | 3:C | none | none | none | AMBIGUOUS |
| 550ce7e7 | fb78ac {1:C, 2:C, 4:C} | 1:C | none | 1:C | 1:C | |
| 57667013 | 9c1336 {1:C, 2:C, 4:C} | 1:C | 1:C | 1:C | 1:C | |
| 6054afcb | 89e4ae {1:C, 2:C, 3:C, 4:C} | 1:C | 1:C | 1:C | 1:C | |
| 66399b0d | e4222f {1:C, 2:C, 4:W} | 1:C | 1:C | 1:C | none | AMBIGUOUS |
| 6a33f9b9 | db9a95 {1:C, 2:C, 4:C} | 1:C | none | 1:C | 1:C | |
| 7ae48c60 | fb6e96 {2:C, 4:C} | none | none | none | none | AMBIGUOUS |
| 88fe4b2d | 1cde4b {1:C, 2:C} | 1:C | none | 1:C | 1:C | |
| 936321ce | c7485e {1:C, 2:C, 4:C} | 1:C | none | 1:C | 1:C | |
| a9f325aa | adf400 {1:C, 2:C, 3:C, 4:C} | none | none | none | none | AMBIGUOUS |
| d53ff5ee | d7c15a {2:W, 4:W} | 2:W | 2:W | 2:W | 2:W | |
| ecc2413d | 0d7fbd {1:W, 4:W} | 1:W | 3:C | 1:W | none | GAP |
| f23acfd2 | none | 3:C | none | none | none | AMBIGUOUS |

**Measured.** Blank CONFIRM tag means a commit was made.

## Where agreement helps and where it hurts

**Helps.**
- 2cd43775 (auto-save): no two methods agree, so C and D abstain. A commits 083c86e1, which is wrong under the strict reading. **Measured.**

**Hurts.**
- 0326d92d: all four diffs have 17 changed lines. Pairwise Jaccard is 0.55 for every pair, so no two are identical. A commits 1:C (judge low accept, tie to method 1). C and D abstain. **Measured.**
- 51719eea: four very different diffs (75, 215, 80, 77 changed lines, Jaccard 0.02 to 0.05). A commits 3:C. C and D abstain. **Measured.**
- f23acfd2: four single-line or small edits with no line in common (Jaccard 0.00). A commits 3:C. C and D abstain. **Measured.**
- 66399b0d (D only): e4222f joins two correct methods and one wrong one. C commits 1:C. D abstains, because the judge gave every candidate only a low accept. **Measured.**
- ecc2413d: m1 and m4 have the same one-line diff (0d7fbd), and both are wrong under GT v4. C commits m1, so agreement endorses a shared misreading. B commits m3, the only candidate with a unique edit, and it is correct. **Measured.**

In this sample, a request without a partner gets no commit under C or D. Three of those requests were correct under A. Agreement can only commit where two methods match. **Measured (counts), inferred (general rule).**

## Root cause and catching key for each wrong end state

Keys: spec (executor decision, frozen Exp 5 specs at c909d02), judge (Sol, blind). Agreement shows the group the state falls into (sorted). The last row is the ablation attempt, which no arm sees.

| Code | Task, method | Defect (GT note or inspection) | Spec | Judge | Agreement | Committed by | Caught by |
|---|---|---|---|---|---|---|---|
| de97694c | d53ff5ee, 2 | Lowercased ordinary-case words (Presentation, China, What and others), not only all-caps text. The request is ambiguous (flagged). | ACCEPT | accept, high | Twin b9d8b59c (same diff, both wrong) | A, B, Bs, C, D | Not caught. Passes both keys. Agreement endorses it. |
| b9d8b59c | d53ff5ee, 4 | Same edit as de97694c | ACCEPT | accept, high | Twin de97694c | Not committed (method 2 wins ties) | Not caught. Passes both keys. |
| e6b4b156 | 66399b0d, 4 (ui) | Table inserted one paragraph above the cursor (wrong position). | ACCEPT | accept, low | Sorted: joins m1 and m2 (position-blind). Anchored: separate. | Not committed (method 1 wins ties; D abstains on low) | Passes both keys. Judge accepts it. Anchored agreement separates it. |
| 476b080a | ecc2413d, 1 (ui) | No blank page after page 1. The render has 7 pages, with text equal to the input. | REJECT | accept, low | Twin 7b72ebd1 (same diff, both wrong) | A, C | Spec rejects it. The judge accepts it, and the key does not remove it. |
| eeb4b683 | ecc2413d, 2 (ui) | Same as 476b080a | REJECT | accept, low | None (2 changed lines) | Not committed | Spec rejects it. The judge accepts it. |
| 7b72ebd1 | ecc2413d, 4 (ui) | Same as 476b080a | REJECT | accept, low | Twin 476b080a | Not committed (method 1 wins ties) | Spec rejects it. The judge accepts it. |
| 083c86e1 | 2cd43775, 1 | Strict reading: end-state profile does not set UserAutoSaveEnabled=true. | UNDECIDED | accept, high | None | A | Judge accepts it, and the spec abstains (UNDECIDED), so B abstains. The key removes it. |
| 81a65c80 | 2cd43775, 4 | Same strict reading | UNDECIDED | reject, high | None | None | Judge only. |
| a9e34228 | 2cd43775, 2 | Same strict reading | UNDECIDED | reject, high | None | None | Judge only. |
| 3ab6ba1b | 51719eea, 1 | SUMIF summary table, not a PivotTable. | REJECT | reject, high | None | None | Spec and judge. |
| 3f9e3de2 | 51719eea, 2 | Static summary, not a PivotTable. Column D formulas overwritten with static text. Date formats changed. | UNDECIDED | reject, high | None | None | Judge only. |
| f06f57bc | 7ae48c60, 3 | Many shapes on slide 18 resized (272 changed lines). The request named one picture on slide 3. | UNDECIDED | reject, high | None | None | Judge only. |
| f624e5ec | 21760ecb, 3 (ui) | Dissolve added. Grouped picture, flowchart and connector shapes moved about 4 cm. Underline added to a URL. | REJECT | reject, high | None | None | Spec and judge. |
| 2cd48d90 | 21760ecb, 3 (noui, ablation) | Dissolve added. Many shapes moved or resized up to about 4 cm. The LibreOffice round trip dropped 9 embedded fonts. | REJECT | reject, high | Not in primary set | Not in arms | Spec and judge. |

**Measured** (inspection and keys). Counts over the 14 wrong end states: the judge rejects 7. The spec rejects 3 more that the judge accepts (the ecc2413d states). Both keys pass 3 (de97694c, b9d8b59c, e6b4b156). The remaining one, 083c86e1, has an UNDECIDED spec and an accepting judge.

Agreement blocked one commit that A makes: 083c86e1 (no partner). It did not block de97694c, because its partner is equally wrong, and it did not block 476b080a, because its partner (7b72ebd1) is equally wrong. **Measured.**

## What each key saw on the two contested requests

### ecc2413d (blank page after page 1)

- Request: "throw in a blank page right after this one". The cursor is on page 1. **Measured (task file).**
- Spec: rendered-page predicates on a LibreOffice PDF of each candidate. m3 passes all seven predicates. m1, m2 and m4 fail four each (page count, blank page, page 3 start, page 3 text). **Measured.** The spec agrees with GT v4.
- Judge: text dumps only, no pagination. Accept, low, on all four. **Measured.** The judge cannot see the page break.
- Agreement: m1 and m4 have the same one-line diff (an empty paragraph with a page break, before the title). m2 differs (2 lines). m3 is unique (28 changed lines). **Measured.**
- Render (LibreOffice to PDF, pypdf): input is 7 pages. m1, m2 and m4 are 7 pages, with page text identical to the input. m3 is 8 pages. Page 2 is blank, and pages 3 to 8 match input pages 2 to 7. Word was not checked. **Measured.**
- GT v4 (ruling 1c, render is the GT for page layout): m3 is correct, and m1, m2 and m4 are wrong. **Measured (ruling).**
- Result: the judge accepts all four (low). The spec rejects m1, m2 and m4, so B and Bs commit m3, the correct one. Agreement commits m1, one of the wrong pair (m1 and m4). **Measured.**

### d53ff5ee (convert uppercase text to lowercase)

- Request: "converting all uppercase text to lowercase". The task is flagged ambiguous in GT. **Measured.**
- Spec: m1 and m3 REJECT (only all-caps text lowercased; 2 predicates pass, 3 fail). m2 and m4 ACCEPT (5 pass, 0 fail). The spec predicates check that no uppercase letters remain, so they accept lowercasing of everything. **Measured.**
- Judge: m1 accept (medium), m2 accept (high), m3 reject (medium), m4 accept (high). **Measured.**
- Agreement: m2 and m4 have the same diff (d7c15a, 18 changed lines). m1 (4 lines) and m3 (6 lines) are unique. **Measured.**
- GT v4 (ruling d53ff5ee, option a): m1 and m3 are correct (all-caps text only). m2 and m4 are wrong, because they lowercase ordinary-case words too. **Measured (ruling, `ruling_d53ff5ee.py`).**
- Result: the two keys and agreement accept the same wrong content (m2 and m4). No key separates them. **Measured.**

## Blind spot of the sorted signature

- The sorted signature ignores position. e6b4b156 (wrong position) joins its two correct partners (m1, m2) in sorted mode. Anchored mode separates it. **Measured.**
- No commit changes here, because method 1 wins the tie in every arm. **Measured.**

## Judge self-consistency key (second judge pass)

**Status: verified.** A second, independent Sol pass on all 84 packets is on `origin/exp8-judge-verdicts` at commit 29fc5bd, in `research/exp8-direct/judge_retest/`. It used the same prompt and the same six batches. According to the commit message, each judge saw only its own batch, not the first-pass verdicts. `retest.py` reads both passes from that commit and checks them against the first-pass TSV that `metrics.py` uses. Output: `retest_output.txt`. **Measured.**

### Checks on the two passes (measured)

- 84 packets in each pass. The packet ids match the private packet map for all 84.
- The first-pass TSV matches the first-pass files: 84 of 84.
- Four flips, all accept to reject: 083c86e1, d8fa1b66, 4e3dd7f6 and 699226e8. (Attempt codes only.)
- Second pass alone: 60 accept, 24 reject.
- Confidence labels match on 77 of 84.
- Flipped packets had first-pass confidence high 1, medium 3, low 0. Of the 43 packets rated high in both passes, none flipped.

### The key

A judge accept counts only if both passes accept. A kept accept uses its first-pass confidence (main rule). A sensitivity rule uses the lower of the two labels. The two rules give the same pick for every arm and request (zero changes in the rule check), so the 7 label mismatches change no commit. **Measured.**

### The four flipped packets

| Code | Task, method | GT (v4, strict) | Spec | First pass | Second pass |
|---|---|---|---|---|---|
| 083c86e1 | 2cd43775, 1 (auto-save) | W, ambiguous | UNDECIDED | accept, high | reject, medium |
| 4e3dd7f6 | 6054afcb, 3 | C | ACCEPT | accept, medium | reject, medium |
| d8fa1b66 | 6054afcb, 2 | C | ACCEPT | accept, medium | reject, medium |
| 699226e8 | d53ff5ee, 1 | C (ruling d53ff5ee) | REJECT | accept, medium | reject, medium |

**Measured.** Under GT v4 the flips remove three correct accepts (4e3dd7f6, d8fa1b66, 699226e8) and one wrong accept (083c86e1, wrong under the strict reading only).

Second-pass reasons, as written in the files:
- 083c86e1: "The change enables three-minute AutoRecovery snapshots but does not enable saving the actual document automatically as requested."
- 6054afcb, d8fa1b66 and 4e3dd7f6: "Entire rows are hidden, concealing valid dates and budgets as well as the N/A entries instead of hiding only the missing-data indicators."
- 699226e8: "Only the all-caps passages were lowercased, while uppercase letters remain in the title, body text, and table." This describes the correct edit under ruling d53ff5ee. The reject is a judge error.

### Effect on the arms (primary 72 attempts, GT v4 strict)

| Arm | First pass: correct / wrong / CONFIRM | With key: correct / wrong / CONFIRM | Wrong commits with key |
|---|---|---|---|
| A | 13 / 3 / 2 | 14 / 2 / 2 | d53ff5ee de97694c; ecc2413d 476b080a |
| B | 8 / 1 / 9 | 8 / 1 / 9 | d53ff5ee de97694c |
| Bs | 9 / 1 / 8 | 9 / 1 / 8 | same as B (Bs does not use the judge) |
| C | 10 / 2 / 6 | 10 / 2 / 6 | d53ff5ee de97694c; ecc2413d 476b080a |
| D | 9 / 1 / 8 | 9 / 1 / 8 | d53ff5ee de97694c |

**Measured (script).**

- Only A changes, on one request (2cd43775). The key removes the wrong auto-save accept. A falls to the next accepted candidate, 76604199 (method 3, high), which is correct under the strict reading. The second pass accepts 76604199 (high) and rejects the other three profiles, so on this family it applies the strict reading consistently. **Measured.**
- B and Bs do not change. B's spec key already excludes 083c86e1, because its spec is UNDECIDED.
- C and D do not change. The flipped packets are not the picks of either policy. On 6054afcb, C and D still pick method 1 (high, correct). On d53ff5ee, method 1 is in no agreement group.
- CONFIRM tags do not change.
- Judge accepts fall from 64 to 60. Correct accepts fall from 57 to 54, and wrong accepts from 7 to 6. Precision (correct accepts over all accepts) rises from 89.1% to 90.0%. Recall on correct end states falls from 81.4% (57 of 70) to 77.1% (54 of 70). **Measured.**
- Tie-break counts in `retest_output.txt` (A 13 requests, B 8, C 11, D 9) use first-pass confidence. The min rule changes no pick. **Measured.**

### Identical or near-identical content

All four flips are on content that the judge also saw in an identical or near-identical twin. The second pass did not treat those twins alike.

- **6054afcb.** Four end states (5a2c5250 m1, d8fa1b66 m2, 4e3dd7f6 m3, fbd38e91 m4) are identical in every cell value, formula and hidden row (13 rows each). For all four, the hidden rows are exactly the rows that contain `=NA()`. GT v4 labels all four C (ruling 1b). Judge: 5a2c5250 accept high (both passes), fbd38e91 accept high (both passes), d8fa1b66 accept medium then reject medium, 4e3dd7f6 accept medium then reject medium. Under ruling 1b the rejects are judge errors, so the flips are judge inconsistency on identical content. **Measured (content and verdicts), inferred (cause).**
- **d53ff5ee.** 699226e8 and a6cac88c have the same document text. GT v4 labels both C (ruling d53ff5ee). First pass: accept and reject, both medium. Second pass: reject, reject. Both second-pass rejects are judge errors under GT v4. **Measured.**
- **2cd43775.** The four profiles differ only in `registrymodifications.xcu`. 76604199 is the only one with UserAutoSaveEnabled set to true. 083c86e1 and a9e34228 hold the same settings (AutoSave Enabled true, TimeIntervall 3, no UserAutoSaveEnabled). They differ only in XML type attributes and quote style. **Measured (file diff).** Treating them as the same setting is **inferred**. The first pass accepted 083c86e1 (high) and rejected a9e34228 (high). The second pass rejected both (083c86e1 medium, a9e34228 high). **Measured.**

### What the key does not catch

- Six wrong accepts remain after the key: e6b4b156 (66399b0d m4, low), de97694c (d53ff5ee m2, high), b9d8b59c (d53ff5ee m4, high), and 476b080a, eeb4b683 and 7b72ebd1 (ecc2413d m1, m2, m4, low). Both passes accept all six. **Measured (retest output).**
- The key is a stability filter, not a correctness filter. A wrong accept that the judge repeats survives it. The same model with the same prompt repeats its own errors on these six. **Inferred.**
- Flips are few and sit in the middle band: 3 of 12 medium verdicts flipped, 1 of 47 high, 0 of 25 low. The counts are small. **Measured.**

### Summary of the key

- The four flips remove three correct accepts and one wrong accept (under the strict reading).
- Arm A changes on one request: 13 correct and 3 wrong becomes 14 and 2. B, Bs, C and D are unchanged.
- The key is not a safety mechanism on this sample. It removes one of the wrong first-pass accepts (the auto-save one) and three correct ones. Six wrong accepts survive.

## Second judge from another lab (Gemini 4 Argon), policies E, E2, E3

**Status: post hoc.** Gemini judged the same 84 packets in the same six batches. Verdicts are on `origin/exp8-judge-verdicts` at commit 99f06b3, in `research/exp8-direct/judge_gemini/`. The commit message says each judge saw only its own batch, not Sol's verdicts. Script: `gemini_policies.py`. Output: `gemini_policies_output.txt`. All numbers use strict GT v4.

### Checks (measured)

- 84 verdicts. The packet ids match the private map for all 84. 73 accept, 11 reject. Confidence: 75 high, 3 medium, 6 low. Sol's first pass had 47 high of 84, so Gemini's confidence label carries less information. **Measured, inferred (information content).**
- Sol first pass x Gemini: 61 accept/accept, 8 reject/reject, 15 disagreements (12 where Sol rejects and Gemini accepts, 3 the reverse). These match the counts the orchestrator reported.
- Against GT v4 (all 84): Gemini accepts 63 correct and 10 wrong; rejects 7 correct and 4 wrong. Precision 86.3%, recall on correct states 90.0%. Sol's first pass: precision 89.1%, recall 81.4%. Gemini accepts more of everything, wrong states included. **Measured.**
- Disagreements by GT: of the 12 Sol-reject/Gemini-accept, 8 are correct and 4 wrong (f624e5ec, 81a65c80, a9e34228, and 2cd48d90 in the ablation set). Of the 3 Sol-accept/Gemini-reject, 2 are correct and 1 is wrong (eeb4b683). **Measured.**

### Policies (primary 72 attempts, 18 requests)

- **E:** Sol accept (first pass) AND Gemini accept.
- **E2:** E with the Sol self-consistency key: Sol accept in both passes AND Gemini accept.
- **E3:** spec ACCEPT AND Sol accept (first pass) AND Gemini accept.
- Pick rule: highest confidence of the policy's first verdict (Sol's first pass for E, E2, E3), ties to the lower method index. A sensitivity rule takes the lowest label over the verdicts the policy uses. It changes no result (checked).
- Reference arms: A and B as in `metrics.py`. G is Gemini alone, for reference only.

| Policy | Correct zero-click | 95% CI (exact) | Wrong commits | CONFIRM (AMBIGUOUS / GAP) | Wrong commit tasks |
|---|---|---|---|---|---|
| A (reference) | 13 of 18 (72.2%) | 46.5% to 90.3% | 3 | 2 (2 / 0) | 083c86e1, de97694c, 476b080a |
| B (reference) | 8 of 18 (44.4%) | 21.5% to 69.2% | 1 | 9 (7 / 2) | de97694c |
| G Gemini only (reference) | 15 of 18 (83.3%) | 58.6% to 96.4% | 3 | 0 | 083c86e1, de97694c, 476b080a |
| E | 13 of 18 (72.2%) | 46.5% to 90.3% | 3 | 2 (2 / 0) | 083c86e1, de97694c, 476b080a |
| E2 | 14 of 18 (77.8%) | 52.4% to 93.6% | 2 | 2 (2 / 0) | de97694c, 476b080a |
| E3 | 8 of 18 (44.4%) | 21.5% to 69.2% | 1 | 9 (7 / 2) | de97694c |

**Measured (script), post hoc.**

- E changes no commit against A. Gemini rejects 3 packets that Sol accepts, and none of them is A's pick on its request. At the candidate-pool level E removes one wrong accept (eeb4b683), which no arm picked anyway.
- E2 equals A with the self-consistency key on every request. Gemini adds nothing to the key here.
- E3 equals B on every request. Gemini's rejects never touch B's candidate pool picks.
- G alone commits on all 18 requests (no CONFIRM), commits the same three wrong states as A, and reaches 15 of 18 correct. It has no abstention, so it carries no safety signal. Its wrong-commit upper bound equals A's (0.377). **Measured.**
- One-sided 95% upper bounds on wrong commits per request: E 0.377 (3 of 18), E2 0.31 (2 of 18), E3 0.238 (1 of 18). **Measured.**

### The six wrong accepts that survive Sol's key: Gemini's verdict and what the packet showed

| Code | Task, method | Sol (both passes) | Gemini | What discriminates the state | Did the packet show it? |
|---|---|---|---|---|---|
| e6b4b156 | 66399b0d, 4 (ui) | accept, low | accept, high | The inserted table sits one paragraph above the cursor's empty last paragraph | No. The dump lists all paragraphs first and all tables second, so the diff order is not document order. The UI state names the cursor ("empty last paragraph, below the table"), but nothing ties the new table to a position relative to it. |
| de97694c | d53ff5ee, 2 | accept, high | accept, high | 21 ordinary-case letters were lowercased along with the all-caps text | Yes. The diff shows the ordinary-case words before and after ("Presentation Instruction" and others). Both judges read "all uppercase text" as "all uppercase characters". A reading error, not an observability gap. The request is flagged ambiguous. |
| b9d8b59c | d53ff5ee, 4 | accept, high | accept, high | Same edit as de97694c | Yes. Same as above. |
| 476b080a | ecc2413d, 1 (ui) | accept, low | accept, high | The render has no blank page after page 1 (7 pages, text equal to input) | No. The packet shows the page-break count (4 to 5) and a new empty paragraph, but no rendered pagination. The judge inferred a blank page from the break. |
| eeb4b683 | ecc2413d, 2 (ui) | accept, low | reject, low | Same render result | No, same gap, but Gemini rejected it anyway: "only a single page break was added without a new paragraph ... either inserts a break before page 1 or fails to create a blank page after page 1". Its diff differs from m1 and m4 (no new paragraph). The only one of the six Gemini catches. |
| 7b72ebd1 | ecc2413d, 4 (ui) | accept, low | accept, high | Same render result as m1 | No. Same pagination gap as m1. |

**Measured (packets, verdicts, end states).** The position claim for e6b4b156 was checked by walking the end state with python-docx: the new table sits between the existing table and the last two empty paragraphs, one paragraph above the cursor paragraph. The packet's own diff cannot show that, because the dump groups paragraphs and tables separately.

Reference: 02d030c7 (ecc2413d m3, wrong in GT v3, correct in v4). Gemini accepts it (high), as do both Sol passes. Correct accept under v4.

### Pattern against Exp 7

Exp 7 found all 8 of its two-key failures came from properties no dump printed. Here, four of the six surviving wrong accepts fail on a property the packet did not show (one cursor position, three rendered pagination). Two fail on request reading with the evidence in full view (the d53ff5ee pair). A second lab does not fix either kind: Gemini catches 1 of the 6, and it accepts 4 wrong states that Sol rejected. **Measured.**

## Limits

- 18 requests and 14 wrong states (13 in the primary set). Any result here is for one sample. **Measured.**
- The policies, the high-confidence threshold and the key rule were chosen after the primary results were seen. **Measured (timeline).**
- GT v4 is post hoc. Five rows changed after the primary v3 numbers were seen, and all policy numbers here use v4. **Measured (timeline).**
- Signatures depend on the inspector view, which includes round-trip run markers (see Method). **Measured.**
- Agreement depends on the four method hints producing diffs that can match. Two methods with the same wrong reading will match. ecc2413d shows this. **Inferred.**
- Judge verdicts come from one model and one prompt, run twice. The second pass measures run-to-run variance, not bias. Gemini is a second lab, but on the same packets and the same task wording. **Measured (design), inferred (effect).**
- Policies E, E2 and E3 were defined and scored after the Gemini verdicts were seen. All Gemini numbers here are post hoc. **Measured (timeline).**

## Next steps

- Agreement stays out of any safety design. If it is pursued for other reasons, test it on more requests with independent method hints, and add a check for shared misreading (for example, an independent wording of the request).
- If a judge packet is ever revised, add the two properties the current dump cannot show: document-order position of inserted objects relative to the cursor, and rendered pagination. Four of the six surviving wrong accepts fail on those two properties.
