# Experiment 9 results: do rendered pages catch what the file dumps drop?

Scored under `exp9-preregistration.md` (lock 2e9eac4; Amendment 1 ea844bf; Amendment 2 f933adf, post hoc; Amendment 3 4bc82d0, post hoc). Verdicts: branch `exp9-judge-verdicts`, commit 07f91ed, copied byte for byte to `verdicts/`. Packets: branch `exp9-packets`, commit 58729f9. The salt is revealed in section 8.

## 1. Headline

Both gates pass as written, so under section 5 of the prereg the render representation earns a place. The result rests on few states. G1 counts 3 renderable states (1 as registered), and G2 is a comparison of 30 states.

- G1 (detection): the render judge rejected every renderable group A state. That is 1 of 1 as registered and 3 of 3 under Amendment 2. Pass under both readings.
- G2 (cost): the render judge falsely rejected 5 of the 30 correct states (16.7%). Sol falsely rejected 9 of the same 30 (30.0%) in Exp 7. Pass.
- Group A: the render judge rejected 7 of the 8 corrected wrong accepts. Sol accepted all 8 in Exp 7. The one accept is a cursor state (66399b0d state_02), which is reported separately.
- Group C: the render judge rejected 34 of 40 wrong states (85.0%). Sol rejected 35 of the same 40 (87.5%). On this sample the render judge did not do better than Sol.

The caveats in section 9 apply to these results. Section 5a gives the joint table with Sol.

## 2. Gates

| Gate | Rule (prereg) | Result | Outcome |
|---|---|---|---|
| G1 as registered | Judge rejects each renderable group A state. Set: 57667013 state_22 | state_22 rejected (high) | Pass |
| G1 amended (Amendment 2) | Same rule. Set: 57667013 state_19, state_20, state_22 | 3 of 3 rejected (all high) | Pass |
| G2 cost | Render false-reject rate on B plus D (30 states) at or below Sol's 9 of 30 | 5 of 30 rejected | Pass |

G1 passes only if it passes under both readings. It does under both. The expected renderable count was 4. Under the registered reading 1 state is renderable, and under Amendment 2, 3 states are. The fourth expected state, 66399b0d state_17, is not renderable under Amendment 2 (section 11 of the prereg).

Undecided verdicts: 0 of 78.

## 3. Group A: the eight corrected wrong accepts

Adjudicated properties are from prereg section 4. Reasons are the judge's text, verbatim.

| State | Adjudicated property | Render verdict (confidence) | Judge reason | Counted in G1 |
|---|---|---|---|---|
| 57667013 state_19 | Slide 5 text alpha 0 (text invisible) | Reject (high) | "Slide 5's text is missing instead of being recolored yellow." | Yes, renderable |
| 57667013 state_20 | Slide 5 text lumMod 60000 (dark olive, not FFFF00) | Reject (high) | "Slide 5's text uses a dark olive-yellow shade rather than the exact yellow requested." | Yes, renderable |
| 57667013 state_22 | Six slide 5 shapes with solid black fill | Reject (high) | "Although the text is yellow, slide 5's background was also changed from light blue to dark blue without being requested." | Yes, renderable |
| 66399b0d state_17 | Inserted table with a gridSpan=7 row (one visible column) | Reject (low) | "The only visible addition is a blank third page, with no visible 7-column, 5-row empty table at the insertion point." | No (not renderable under Amendment 2) |
| 66399b0d state_01 | Cursor position of the inserted table (not recorded in the file) | Reject (low) | "The end state has an additional blank page but no visible 7-column by 5-row empty table." | No (cursor) |
| 66399b0d state_02 | Same as state_01 | Accept (low) | "An empty seven-column, five-row table is added without visible changes to existing content, although the original cursor position cannot be verified from the images." | No (cursor) |
| 66399b0d state_03 | Same as state_01 | Reject (low) | "The end state adds a blank third page but shows no identifiable empty seven-column, five-row table." | No (cursor) |
| 66399b0d state_04 | Same as state_01 | Reject (low) | "The end state adds a blank third page rather than showing a 7-column, 5-row table at the original cursor position." | No (cursor) |

Notes on the reasons:
- state_19 and state_20: the reason names the adjudicated property.
- state_22: the verdict matches the adjudicated property. The render shows the light blue slide 5 shapes filled solid black in the end state. The reason calls the change a background change to dark blue, so it misnames the object and the color. G1 counts verdicts, so this reject counts.
- state_17: the reason names the missing table, not the merged row. This fits Amendment 2, which records that no render can show this error.
- Cursor states: no reason cites table placement at the end of the document, so none is a placement reading (prereg section 5). The reasons describe a blank page or no visible table. None names the cursor property directly. Caveat 2 in section 9 has the render check.

## 4. Group B and D: cost

| Set | Render rejects | Render rate (95% CI) | Sol rejects (Exp 7) | Sol rate (95% CI) |
|---|---|---|---|---|
| B (5 states) | 0 | 0.0% (0.0 to 52.2) | 1 | 20.0% (0.5 to 71.6) |
| D (25 states) | 5 | 20.0% (6.8 to 40.7) | 8 | 32.0% (15.0 to 53.5) |
| B plus D (30 states, gate) | 5 | 16.7% (5.6 to 34.7) | 9 | 30.0% (14.7 to 49.4) |

Intervals are exact Clopper-Pearson. With 30 states the comparison has little power, and the intervals overlap.

The five false rejects, all on states whose corrected label is CORRECT:

| State | Group | Confidence | Judge reason |
|---|---|---|---|
| 21760ecb state_14 | D | Low | "An unrequested duplicate presentation was added, while the unchanged static renders cannot establish whether the first slide has the requested dissolve transition." |
| 7ae48c60 state_14 | D | Low | "The pictures on slides 3 and 6 also move upward to the slide's top edge, changing their placement beyond the requested height adjustments." |
| 936321ce state_02 | D | High | "The comma-separated content is arranged into a table, but the original underlining in the example words has been removed." |
| d53ff5ee state_01 | D | Medium | "Uppercase letters remain in the title, body paragraphs, and table, so the requested lowercase conversion is incomplete." |
| d53ff5ee state_17 | D | High | "The main uppercase paragraph is lowercased, but the uppercase course code CHIN9505 remains unchanged." |

Every one of these five is also a Sol false reject (section 5a).

The labels were not re-adjudicated in this scoring. The two d53ff5ee reasons name uppercase text left in place, so those labels are the first to check if a label error is suspected.

## 5. Group C: 40 corrected wrong states outside group A

- Render: 34 of 40 rejected (85.0%, 95% CI 70.2% to 94.3%). Undecided: 0.
- Sol, same 40 states, Exp 7: 35 rejected (87.5%, 73.2% to 95.8%).
- Reason check (prereg section 6), done by hand after the run against the Exp 7 adjudication notes:
  - 31 of 34 rejection reasons name the property the adjudication recorded.
  - 2 name a different defect:
    - 936321ce state_11. Judge: underline removed. Adjudicated: an extra empty fifth column.
    - 66399b0d state_12. Judge: no visible 7-column table. Adjudicated: a 6-column table placed at the document end.
  - 1 cannot be checked: d53ff5ee state_21. Its adjudication row gives a verdict but no property.
- Accepted (6): 21760ecb state_06, 51719eea state_03, 550ce7e7 state_02, 550ce7e7 state_10, 6054afcb state_05, f23acfd2 state_02.

The full reject list with reasons is in `exp9-score.json`.

## 5a. Joint table: render key and Sol on the same states

Sol's column is its Exp 7 primary verdict on the same state. Group A is defined as the corrected wrong accepts of the combined policy, which includes Sol. So every group A state has a Sol accept. Those rows are selected on Sol's miss.

Wrong states (corrected WRONG):

| Set | Both reject | Render only | Sol only | Both miss | Total |
|---|---|---|---|---|---|
| Group C (random sample) | 33 | 1 | 2 | 4 | 40 |
| Groups A and C | 33 | 8 | 2 | 5 | 48 |

- Totals: render rejects 34 of C and 41 of A plus C. Sol rejects 35 of C and 35 of A plus C.
- Group C, render only: 0326d92d state_04.
- Group C, Sol only: 21760ecb state_06, 51719eea state_03.
- Group C, both miss: 550ce7e7 state_02, 550ce7e7 state_10, 6054afcb state_05, f23acfd2 state_02.
- Group A, render only: 57667013 state_19, state_20, state_22; 66399b0d state_01, state_03, state_04, state_17.
- Group A, both miss: 66399b0d state_02.

Correct states (corrected CORRECT, B plus D, 30 states):

| | Sol reject | Sol accept |
|---|---|---|
| Render reject | 5 | 0 |
| Render accept | 4 | 21 |

Every render false reject is also a Sol false reject. Sol has 4 false rejects that render accepts.

## 6. Renderer and run facts

- 78 states: group A 8, B 5, C 40, D 25. 723 page PNGs, one per page, at 150 dpi.
- Amendment 3: 9 pages in 5 states were re-encoded losslessly, and their pixels were checked equal to the render: 04f989aa987f (2), 2998dc6da38e (2), 4b462954d9bd (2), d0786d9632fb (2), 320ea4931b8c (1). No page was tiled, so no request.txt has a Notes block.
- Every PNG is under the 5 MiB read limit. The largest is 4,108,801 bytes. Chunks are IHDR, pHYs, IDAT and IEND only.
- Render time per state (wall clock, `render_state`): median 2.39 s, 90th percentile 10.81 s, maximum 16.35 s. The largest state, 99cc42222a8b, has 72 PNGs.
- PyMuPDF printed "cannot create appearance stream for Screen annotations" 44 times in the final render. These come from LibreOffice form-field annotations, and the pages are rendered as PyMuPDF produces them.
- Judge: pv-sol-xhigh, prompt `sol_prompt_render.txt`, sha256 242c0e168f3ee510bfd41fa7294a8894cb7631e34067bcd25845ab3247939d17 (matches the lock). Template verbatim, with only the three placeholders filled. The judge ran in an isolated clone of the packets branch.
- 29 batches. Verdict files: 78 entries, one per id. Totals: 32 accept, 46 reject. Confidence: 51 high, 5 medium, 22 low.
- Protocol deviation (reported by the orchestrator): batches 23, 24, 25, 28 and 29 ran at once at the tail, not 4 at a time. The prompts were unchanged. No batch failed or was rerun.
- Per-batch judge timing was not measured.
- Prompt check, done after the run. Prereg section 3 asks for the comparison of `sol_prompt_exp7.txt` with the orchestrator's runner copy before batch 1. It was not done before batch 1. It was done after the run. The sha256 of `sol_prompt_exp7.txt` is 7b230f87ab17b6c0f68271759178fc18e7ac4c54165bb9158272f8852256e5f8. It equals the runner copy recovered from the orchestrator's session transcript, character for character, once the three paths are replaced by placeholders. The render prompt (242c0e16) was checked before batch 1, and every batch used it. The Exp 7 template was not used in Exp 9, so the late check has no effect on any verdict.

## 7. Post hoc changes and exposure

- Amendment 1 (before the render): a state over 40 PNGs is judged alone. Applied to 99cc42222a8b (72 PNGs).
- Amendment 2 (after the group A renders, before any judge run): group A renderability predicates changed. Both readings are reported in section 2.
- Amendment 3 (after the first render stopped, before any judge run): an over-limit page is re-encoded losslessly, and tiled only if it is still over the limit. Nine pages were re-encoded, and none was tiled.
- The four renderable group A packets were rendered before Amendment 3. Their stats keys were derived from their files, and every page was under the limit, so every page is counted as kept.
- The packets were in the origin repository on branch `exp9-packets` before judging. A reader with repository access could have matched them to published Exp 7 labels. The judge protocol confined the judge to the batch folder. This is the same exposure as Exp 7, where packets were also in the repository during judging.

## 8. Salt and unblinding

Salt, revealed after scoring:

```
7a9d28d022a70efc77b7525d751098c5445d1a642fdebfc80b58765f8370dcd3
```

- The sha256 of the salt text equals the commitment `4bd21c633107aafa13ad58023c7bc7c1d9647889c5a7706067825d1195a19e19` (checked by `unblind_exp9.py`).
- All 78 blind ids, recomputed from the salt, match the verdict ids and the packet directories.
- Group membership hashes match prereg section 4: A `ed413c66`, B `094409b6`, C `25e4837b`, D `81f7ca3b`.
- The membership table is `exp9-unblinding.json`. It gives group, task, state, the Exp 7 label, and the Exp 7 Sol judge field for each state.

## 9. Caveats

1. G1 rests on 3 states (1 as registered), from one task (57667013) and one property family (slide text color and fill). It shows that the mechanism works on these states. It does not show how often the mechanism works. The state_22 reason misnames the object and the color. It describes a change from light blue to dark blue background. The render shows the blue slide 5 shapes filled solid black.

2. The cursor family (66399b0d, five wrong states). The render judge rejected 4 of 5 (01, 03, 04 and 17) and accepted 02. None of the four reasons cites placement. All of them say that no table is visible. Render check, one state each:
   - state_02 (wrong, accepted): its new table has grid borders, so page 3 shows a grid. The grid has 3 rows on that page. The table has 5 rows in the file, and I did not find why 2 rows are not drawn.
   - state_01, 03 and 04 (wrong, rejected): the new table has no borders. Page 3 of the end render is blank.
   - state_06 (correct, accepted): the new table is at the document start, with no borders. The render shows blank space above the title. The judge accepted it, and its reason says invisible borders prevent confirming seven columns.
   - The other new tables in this family (state_08, state_12 and state_17) also have no borders.

   So in this pipeline an empty table shows only if it has borders. Without borders, its presence shows only as blank space or a blank page. The rejects of 01, 03 and 04 are right on the start-of-document reading, but the render shows only an extra blank page at the end of the document. A correct empty table inserted at the end would look the same. This sample has no correct mid-document cursor insert, so whether a correct insert gets falsely rejected is an open question. The verdicts follow visibility, not placement: state_02 has the same end placement and was accepted. State_17 is a merged-row error. The render cannot show it (Amendment 2), so its reject is not a detection of the merge.

3. The render key and Sol overlap heavily on group C (34 vs 35 of 40). Of the 40, 33 are rejected by both keys, 1 by render only, 2 by Sol only, and 4 are missed by both (section 5a). Across the 48 wrong states of groups A and C, the render key catches 41 and Sol catches 35. Both catch 33. Render alone catches 8, Sol alone catches 2, and both miss 5. Seven of the 8 render-only catches are group A states that Sol accepted by selection, since the combined policy that defines group A includes Sol. On the random sample the two keys make nearly the same calls. So this result does not yet show that rendering is a different representation in general.

Other limits:

- Under the prereg, G1 is a mechanism check, not a rate.
- Ground truth is the Exp 7 corrected label. Those labels were not re-adjudicated here. The cursor states (66399b0d 01 to 04) rest on the start-of-document reading recorded in Exp 7.
- The executor is my Exp 7 implementation. It was not independently verified.
- The render is LibreOffice print output. Transitions and animations do not appear in PDFs, so 21760ecb transition states cannot be checked by render.
- The render judge and the dump judge are the same model (Sol). The prompts differ in two sentences.

## 10. Files

- `exp9-results.md` (this file)
- `verdicts/verdicts_01.json` to `verdicts_29.json`: copied byte for byte from `exp9-judge-verdicts` at 07f91ed
- `exp9-unblinding.json`: membership table, published at unblinding
- `exp9-score.json`: scorer output, reproduced from the repository copies
- `score_exp9.py`: scoring. `unblind_exp9.py`: salt commitment check and unblinding
