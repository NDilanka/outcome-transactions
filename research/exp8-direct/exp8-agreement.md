# Exp 8 post-hoc agreement analysis

Owner: T3 (Exp 8 real-agent executor). Branch `exp8-direct-agent`. Judge: Sol. I did not judge.
Labels: **measured** (script output or file read), **inferred** (from measured facts), **guess** (estimate).

**Status: HYPOTHESIS.** The two agreement policies below were proposed after the primary arm results were known. They were not pre-registered and do not change any gate verdict in `exp8-results.md`.

Scripts and outputs: `research/exp8-direct/agreement.py` (output in `agreement_output.txt`) and `research/exp8-direct/metrics.py` (arms, output in `metrics_output.txt`). Both use the primary GT reading (strict auto-save, see `exp8-results.md`).

## Answer first

- In this sample, agreement trades correct commits for fewer wrong ones. Policy C (commit the judge-accepted member of a group of at least two attempts with the same diff) commits 11 of 18 requests correctly, with 1 wrong. Policy D (C with a high-confidence judge accept) commits 9 of 18 correctly, with 1 wrong. Judge-only arm A commits 14 of 18 correctly, with 2 wrong. Neither policy reaches the 80% headline target. **Measured.**
- Agreement cuts one wrong commit (auto-save 083c86e1, which A commits). It costs three correct commits (0326d92d, 51719eea, f23acfd2), because no two methods wrote the same diff there. CONFIRM rises from 2 (A) to 6 (C) and 8 (D). **Measured.**
- Agreement does not catch the wrong state that the two keys also pass (d53ff5ee m2, de97694c). Its twin (m4, b9d8b59c) wrote the same wrong edit, so the two agree with each other. Shared misreadings look like agreement. **Measured (group), inferred (cause).**
- Of the 12 wrong end states in the primary set, agreement avoids two wrong commits that A or B make (083c86e1 and 02d030c7). It does not avoid the third (de97694c), which A, B, Bs, C and D all commit. **Measured.**
- Two GT labels look wrong or inconsistent: ecc2413d (the render check contradicts the GT for all four candidates) and a6cac88c versus 699226e8 (same document text, opposite labels). Either can change results. GT v3 is not changed here. This needs a ruling. **Measured.**

## Method

- **Signature.** Each end state is compared with the start copy using the GT inspector view (`gt_view.py`). The changed lines only are kept, with whitespace collapsed and sorted. Two attempts agree when their signatures are equal and not empty. No attempt was a no-op. **Measured.**
- **Anchored variant (sensitivity).** Hunks keep one unchanged line of context on each side. This version sees position. It was added after the first sorted run, to test whether the sorted version is blind to position. **Measured.**
- **Policy C.** Among the attempts of one request that belong to a group of at least two with the same signature, commit the judge-accepted member with the highest judge confidence. Ties go to the lowest method index. With no qualifying member, the request is a CONFIRM.
- **Policy D.** As C, but only a high-confidence judge accept qualifies.
- **Arms A, B, Bs.** Taken unchanged from `metrics.py`.
- **Limits of the signature.** The inspector view includes run-level markers from the LibreOffice round trip. One example: a6cac88c differs from 699226e8 in one run boundary (a trailing `|` marker) in one paragraph. The document text is identical. So signatures can split identical text on formatting noise. No commit changed because of this here. **Measured.**
- **Limit of independence.** The four methods use one model and the same task text. Agreement between them is partly correlated by design. **Inferred.**

## Results (primary: strict auto-save, sorted signatures, 18 requests)

| Arm or policy | Correct, zero click | Wrong commits | CONFIRM (AMBIGUOUS / GAP) |
|---|---|---|---|
| A judge only | 14 of 18 | 2: 2cd43775 083c86e1; d53ff5ee de97694c | 2 (2 / 0) |
| B two-key | 7 of 18 | 2: d53ff5ee de97694c; ecc2413d 02d030c7 | 9 (7 / 2) |
| Bs spec only | 8 of 18 | 2: same as B | 8 (6 / 2) |
| C agreement, judge accept | 11 of 18 | 1: d53ff5ee de97694c | 6 (5 / 1) |
| D agreement, high-confidence judge | 9 of 18 | 1: d53ff5ee de97694c | 8 (6 / 2) |

**Measured.** Anchored signatures give the same counts for all five rows.

- Agreement groups: 15 groups, in 14 of 18 requests. Group GT: 13 groups all correct, 1 mixed (66399b0d), 1 all wrong (d53ff5ee m2 and m4). **Measured.**
- Sensitivity, GT v3 as adjudicated (auto-save family all correct): A 15 correct, 1 wrong; C 11, 1; D 9, 1. Agreement results do not change, because no agreement group exists for the auto-save request. **Measured.**
- Sensitivity, render check on ecc2413d (see below, not GT): A 13 correct, 3 wrong; B 8, 1; Bs 9, 1; C 10, 2; D 9, 1. **Measured.**

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
| ecc2413d | 0d7fbd {1:C, 4:C} | 1:C | 3:W | 1:C | none | GAP |
| f23acfd2 | none | 3:C | none | none | none | AMBIGUOUS |

**Measured.** Blank CONFIRM tag means a commit was made.

## Where agreement helps and where it hurts

**Helps.**
- 2cd43775 (auto-save): no two methods agree, so C and D abstain. A commits 083c86e1, which is wrong under the strict reading. **Measured.**
- ecc2413d: m1 and m4 have the same one-line diff (0d7fbd), so C commits m1. B commits m3, which has no partner, and is wrong (GT). D abstains, because the judge gave m1 only a low accept. **Measured.**

**Hurts.**
- 0326d92d: all four diffs have 17 changed lines. Pairwise Jaccard is 0.55 for every pair, so no two are identical. A commits 1:C (judge low accept, tie to method 1). C and D abstain. **Measured.**
- 51719eea: four very different diffs (75, 215, 80, 77 changed lines, Jaccard 0.02 to 0.05). A commits 3:C. C and D abstain. **Measured.**
- f23acfd2: four single-line or small edits with no line in common (Jaccard 0.00). A commits 3:C. C and D abstain. **Measured.**

In this sample, a request without a partner gets no commit under C or D, and three of those requests were correct under A. Agreement can only commit where two methods match. **Measured (counts), inferred (general rule).**

## Root cause and catching key for each wrong end state

Keys: spec (executor decision, frozen Exp 5 specs at c909d02), judge (Sol, blind). Agreement shows the group the state falls into (sorted, then anchored). The 13th row is the ablation attempt, which no arm sees.

| Blind id | Task, method | Defect (GT note or inspection) | Spec | Judge | Agreement | Committed by | Caught by |
|---|---|---|---|---|---|---|---|
| de97694c | d53ff5ee, 2 | Lowercased mixed-case and title-case text, not only uppercase. The request is ambiguous (flagged). | ACCEPT | accept, high | Twin b9d8b59c (same diff, both wrong) | A, B, Bs, C, D | Not caught. Two-key pass. Agreement endorses it. |
| b9d8b59c | d53ff5ee, 4 | Same edit as de97694c | ACCEPT | accept, high | Twin de97694c | Not committed (method 2 wins ties) | Not caught. Two-key pass. |
| a6cac88c | d53ff5ee, 3 | GT: table text not all-caps was lowercased. Document text is identical to 699226e8 (method 1, GT C). See GT issues. | REJECT | reject, medium | None | None | Spec and judge (judge inconsistent with its accept of 699226e8). |
| 02d030c7 | ecc2413d, 3 | GT: extra page break moved the disclaimer onto page 2. The render does not show this. See GT issues. | ACCEPT | accept, low | None (28 changed lines) | B, Bs | Two-key pass. C and D abstain. |
| f624e5ec | 21760ecb, 3 (ui) | Dissolve added. Grouped picture, flowchart and connector shapes moved about 4 cm. Underline added to a URL. | REJECT | reject, high | None | None | Spec and judge. |
| e6b4b156 | 66399b0d, 4 (ui) | Table inserted one paragraph above the cursor (wrong position). | ACCEPT | accept, low | Sorted: joins m1 and m2 (position-blind). Anchored: separate. | Not committed (method 1 wins ties; D abstains on low) | Two-key pass. Judge missed it. Anchored agreement separates it. |
| 3ab6ba1b | 51719eea, 1 | SUMIF summary table, not a PivotTable. | REJECT | reject, high | None | None | Spec and judge. |
| 3f9e3de2 | 51719eea, 2 | Static summary, not a pivot. Column D formulas overwritten with static text. Date formats changed. | UNDECIDED | reject, high | None | None | Judge only. |
| f06f57bc | 7ae48c60, 3 | Many shapes on slide 18 resized (272 changed lines). The request named one picture on slide 3. | UNDECIDED | reject, high | None | None | Judge only. |
| 083c86e1 | 2cd43775, 1 | Strict reading: end-state profile does not set UserAutoSaveEnabled=true. | UNDECIDED | accept, high | None | A | Missed by both keys. B abstains, because the spec is undecided. |
| 81a65c80 | 2cd43775, 4 | Same strict reading | UNDECIDED | reject, high | None | None | Judge only. |
| a9e34228 | 2cd43775, 2 | Same strict reading | UNDECIDED | reject, high | None | None | Judge only. |
| 2cd48d90 | 21760ecb, 3 (noui, ablation) | Dissolve added. Many shapes moved or resized up to about 4 cm. The LibreOffice round trip dropped 9 embedded fonts. | REJECT | reject, high | Not in primary set | Not in arms | Spec and judge. |

**Measured** (inspection and keys). Counts: spec and judge caught 4 (a6cac88c, 3ab6ba1b, f624e5ec, 2cd48d90 ablation). Judge only caught 4 (3f9e3de2, f06f57bc, 81a65c80, a9e34228). Both keys passed 4 (de97694c, b9d8b59c, 02d030c7, e6b4b156). Missed by both: 1 (083c86e1).

Agreement blocked two commits that A or B make: 083c86e1 (no partner) and 02d030c7 (no partner, and low confidence under D). It did not block de97694c, because its partner is equally wrong. **Measured.**

## What each key saw on the two contested requests

### ecc2413d (blank page after page 1)

- Request: "throw in a blank page right after this one". The cursor is on page 1. **Measured (task file).**
- Spec: rendered-page predicates on a LibreOffice PDF of each candidate. m3 passes all seven predicates. m1, m2 and m4 fail four each (page count, blank page, page 3 start, page 3 text). **Measured.**
- Judge: text dumps only, no pagination. Accept, low, on all four. **Measured.**
- Agreement: m1 and m4 have the same one-line diff (an empty paragraph with a page break, before the title). m2 differs (2 lines). m3 is unique (28 changed lines). **Measured.**
- Render (LibreOffice to PDF, pypdf): input is 7 pages. m1, m2 and m4 are 7 pages, with page text identical to the input. m3 is 8 pages. Page 1 is identical to the input, page 2 is blank, and pages 3 to 8 match input pages 2 to 7. **Measured.**
- GT v3: m1, m2, m4 correct. m3 wrong, with the note that the extra break moved the disclaimer onto page 2. The render does not show that: page 1 is unchanged and m3's page 2 is blank. **Measured (comparison).**
- Consequence: if the render is right, the GT labels for this request are inverted. m3 is the only candidate that gives the user a blank page after page 1. Under that reading, A and C commit a wrong state (m1), and B commits the correct one (m3). This is a sensitivity result only. It is not GT. **Inferred.**

### d53ff5ee (convert uppercase text to lowercase)

- Request: "converting all uppercase text to lowercase". The task is flagged ambiguous in GT. **Measured.**
- Spec: m1 and m3 REJECT (only all-caps text lowercased; 2 predicates pass, 3 fail). m2 and m4 ACCEPT (5 pass, 0 fail). The spec predicates check that no uppercase letters remain, so they accept lowercasing of everything. **Measured.**
- Judge: m1 accept (medium), m2 accept (high), m3 reject (medium), m4 accept (high). **Measured.**
- Agreement: m2 and m4 have the same diff (d7c15a, 18 changed lines). m1 (4 lines) and m3 (6 lines) are unique. **Measured.**
- GT v3: m1 correct. m2, m3, m4 wrong. m1 and m3 have the same document text, so one of the two labels is wrong (see GT issues). **Measured.**
- Result: the two keys and agreement all accept the same wrong content (m2 and m4). No key separates them. **Measured.**

## Blind spot of the sorted signature

- The sorted signature ignores position. e6b4b156 (wrong position) joins its two correct partners (m1, m2) in sorted mode. Anchored mode separates it. **Measured.**
- No commit changes here, because method 1 wins the tie in every arm. **Measured.**

## GT and judge issues (not changed in GT v3)

1. **ecc2413d.** The render check contradicts GT v3 on all four candidates (see above). Needs a re-read and a ruling. Affects A, B and C on this request.
2. **d53ff5ee, a6cac88c versus 699226e8.** Document text is identical, and the only other difference is one run-boundary marker in one paragraph. GT v3 says a6cac88c is wrong and 699226e8 is correct. The judge also accepted 699226e8 (medium) and rejected a6cac88c (medium). **Measured.** Either label could be wrong. Needs a ruling.
3. **Auto-save family (2cd43775).** See `exp8-results.md`. The judge accepted 083c86e1 and rejected 81a65c80 and a9e34228 on the same profile evidence. **Measured.**

## Limits

- 18 requests and 12 wrong states in the primary set. Any result here is for one sample. **Measured.**
- The policies and the high-confidence threshold were chosen after the primary results were seen. **Measured (timeline).**
- Signatures depend on the inspector view, which includes round-trip run markers (see Method). **Measured.**
- Agreement depends on the four method hints producing diffs that can match. Two methods with the same wrong reading will match. **Inferred.**
- Judge verdicts are one judge's labels. **Measured.**

## Next steps

- Ruling on the ecc2413d and d53ff5ee GT labels (blocks any firm agreement result).
- If agreement is pursued, test it on more requests with independent method hints, and add a check for shared misreading (for example, an independent wording of the request).
- Do not treat policy C or D as a safety mechanism on this sample. It did not catch the one wrong state that agreed with another.
