# T6 ambiguity gate: results

Status: final. The gate result is the orchestrator's scoring against the sealed intents. My recomputation from the joined data matches it, with two differences noted below. n = 39 requests. amb16 is excluded from the rate because its two readings are identical (A = B = start). It is reported separately.

Labels: measured = produced by a run or by a count I made; inferred = my reasoning from measured results; guess = not tested.

## Gate result

| Executor | Both keys accept the unintended reading | Rate | 95% interval (exact, two-sided) | Gate (<= 5%) |
|---|---|---|---|---|
| Frozen c909d02 (primary) | 1 (amb30) | 2.6% | 0.1% to 13.5% | Point estimate passes; interval does not show it |
| Sensitivity (__eq__ and __hash__ added in memory) | 3 (amb30, amb31, amb35) | 7.7% | 1.6% to 20.9% | Fails |
| Sensitivity, judge high confidence only | 0 | 0% | 0.0% to 9.0% | Point estimate passes |

All three sensitivity failures have a low-confidence judge accept. amb30's failure is the same under both executors.

## My check of the scoring (measured)

- Reproduced from the joined data: both-key failures (frozen 1, sensitivity 3), spec-alone unintended accepts (frozen 6, sensitivity 11), judge-alone unintended accepts (11), and intended commits with spec and judge both accepting (frozen 18, sensitivity 23).
- Difference 1: intended commits with spec ACCEPT and judge high confidence. I count 14 (amb16 excluded). The scoring says 15. The 15 is reproduced only if amb16 is counted. Its A state has spec ACCEPT and judge accept at high confidence, so the gap is most likely that. This is inferred, not confirmed with the scoring author; I use 14.
- Difference 2: expected joint count under independence. For frozen, 6 x 11 / 39 = 1.69. The scoring says about 1.6. For sensitivity, 11 x 11 / 39 = 3.1, which matches the scoring's 3.1.
- Difference 3: the scoring's 0% judge-high figure is for the joint policy only. Judge high confidence alone accepts the unintended reading on 4 of 39 requests (amb05, amb10, amb23, amb33). That is 10.3%, above 5%. A judge-only gate fails.
- The 95% intervals I computed are exact (Clopper-Pearson). The scoring's approximate bounds are close, except for 0 of 39, where the scoring's 7.4% is a one-sided bound and mine is two-sided (9.0%).

## Independence (inferred)

Under independence, the expected joint counts are 1.69 (frozen) and 3.1 (sensitivity). The observed counts are 1 and 3. Two observations cannot test independence, so the claim that the errors are independent is assumed, not shown.

## What the three sensitivity failures share (inferred)

- amb30: the writer followed the union of both readings (italics on conditional lines and bracketed instructions). Its spec accepts either reading, and the judge accepts both at low confidence. Writer flag: two readings plausible; writer confidence low.
- amb31 and amb35: both are title edits. The sensitivity spec accepts the wrong reading because its must predicates check text and structure, not the difference between the two readings (title size versus title plus body, or subtitle alignment). The judge accepts both at low confidence. Both writers flagged two readings, and both have low writer confidence. amb35's A state is a no-op, because the title is already centred.

## Writer detector: "two readings" flag (measured)

Signal: the writer's flag `two_readings_plausible`. I also searched each spec's text for explicit statements of an alternative reading. Among the seven requests the flag marks as not ambiguous, only amb16 has such a statement ("either outcome is acceptable" for the title cell). On n = 39, the flag alone and the flag or text give the same counts, because amb16 is excluded.

- Hit rate on the three sensitivity failures: 3 of 3 (100%; 95% interval 44% to 100%). Frozen failure amb30: 1 of 1.
- False-alarm rate on the other 36 requests: 30 of 36 (83%; 95% interval 68% to 92%).
- Flagged overall: 33 of 39. Precision (failures among flagged): 3 of 33 (9%).
- Not flagged: amb01, amb02, amb32, amb34, amb37, amb40 (and amb16, excluded).

Reading (inferred): the flag misses no failure on this set, but it fires on 85% of requests. It cannot separate failures from the requests the keys handle correctly. Routing every flagged request to confirmation would confirm 33 of 39 requests. The detector is not a usable gate on its own. Its hit rate on three failures has a wide interval, so this result is weak evidence either way.

## Recommendation (inferred)

- Do not auto-commit when spec and judge both accept, under the sensitivity executor. The gate fails at 7.7%.
- A judge confidence floor (accept only when high) removes the three failures in the joint policy. It also removes 9 intended commits.
- Judge high confidence alone is unsafe (4 unintended accepts).
- Fix the executor equality bug (CellObj and RunP) and add formatting coverage before the next run. Re-test on fresh requests. This is a guess until tested.

## Per-request table (measured, with intended readings revealed)

Intended reading per the sealed intents. The unintended reading is the other one. amb16 is excluded. Spec columns are the empty_all_undecided_decision values. Judge columns are verdict and confidence from the blinded Sol judge.

| request | request text | intended | unintended | spec on A (frozen / sensitivity) | spec on B (frozen / sensitivity) | judge on A | judge on B | writer's followed reading | no-op state | both keys accept unintended (frozen / sensitivity) |
|---|---|---|---|---|---|---|---|---|---|---|
| amb01 | Bold the headers. | A | B | ACCEPT / ACCEPT | ACCEPT / ACCEPT | accept (high) | reject (medium) | A | - | no / no |
| amb02 | Add a total for each rep. | A | B | UNDECIDED / UNDECIDED | REJECT / REJECT | accept (high) | reject (high) | A | - | no / no |
| amb03 | Round the numbers. | B | A | UNDECIDED / UNDECIDED | UNDECIDED / UNDECIDED | accept (medium) | accept (medium) | B | A | no / no |
| amb04 | Put net income in the next column. | A | B | ACCEPT / ACCEPT | UNDECIDED / UNDECIDED | accept (high) | reject (high) | A | - | no / no |
| amb05 | Sort by the revenue column. | B | A | UNDECIDED / UNDECIDED | UNDECIDED / UNDECIDED | accept (high) | accept (high) | A | - | no / no |
| amb06 | Show the expenses as a percent of revenue. | A | B | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | - | no / no |
| amb07 | Clean up the movie titles. | B | A | REJECT / REJECT | ACCEPT / ACCEPT | reject (medium) | accept (medium) | B | - | no / no |
| amb08 | Make the headers stand out more. | A | B | ACCEPT / ACCEPT | ACCEPT / ACCEPT | accept (low) | reject (low) | A | - | no / no |
| amb09 | Get rid of the N/A rows. | A | B | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | - | no / no |
| amb10 | Sort this by date. | A | B | UNDECIDED / UNDECIDED | REJECT / REJECT | accept (high) | accept (high) | A | - | no / no |
| amb11 | Add up the actuals. | A | B | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | - | no / no |
| amb12 | Sum the quantity for Aspen. | A | B | ACCEPT / ACCEPT | ACCEPT / ACCEPT | accept (high) | reject (high) | A | - | no / no |
| amb13 | Show the discounts as percents. | A | B | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | - | no / no |
| amb14 | Remove the duplicate products. | A | B | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | B | no / no |
| amb15 | Add a total at the bottom. | A | B | UNDECIDED / UNDECIDED | REJECT / REJECT | accept (high) | reject (high) | A | - | no / no |
| amb17 | Make the amounts bigger. | B | A | REJECT / REJECT | REJECT / REJECT | reject (low) | accept (low) | neither | - | no / no |
| amb18 | Bold the headings. | A | B | ACCEPT / ACCEPT | ACCEPT / ACCEPT | accept (high) | reject (medium) | A | - | no / no |
| amb19 | Move the apologies up with the attendees. | A | B | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | - | no / no |
| amb20 | Save a copy as a PDF too. | A | B | UNDECIDED / UNDECIDED | REJECT / REJECT | accept (low) | accept (low) | A | - | no / no |
| amb21 | Make the title bigger. | A | B | REJECT / UNDECIDED | REJECT / UNDECIDED | accept (low) | reject (medium) | A | - | no / no |
| amb22 | The marks in the table should add up to 10. | A | B | REJECT / REJECT | REJECT / REJECT | accept (medium) | reject (medium) | neither | - | no / no |
| amb23 | Drop the instructions, I only need the table. | A | B | REJECT / UNDECIDED | REJECT / UNDECIDED | accept (high) | accept (high) | A | - | no / no |
| amb24 | Fill in the total row. | A | B | REJECT / REJECT | REJECT / REJECT | accept (high) | reject (high) | A | A | no / no |
| amb25 | Underline the headings. | A | B | REJECT / ACCEPT | REJECT / ACCEPT | accept (medium) | reject (medium) | A | A | no / no |
| amb26 | The tutorial is worth 30, split the three parts evenly. | A | B | UNDECIDED / UNDECIDED | REJECT / REJECT | accept (high) | accept (medium) | A | A | no / no |
| amb27 | Bold the headers in the second table. | A | B | REJECT / ACCEPT | REJECT / ACCEPT | accept (low) | reject (high) | A | - | no / no |
| amb28 | Make the examples bigger. | A | B | REJECT / ACCEPT | REJECT / ACCEPT | accept (low) | reject (medium) | A | - | no / no |
| amb29 | Take the highlighting off the script. | A | B | ACCEPT / ACCEPT | ACCEPT / ACCEPT | accept (high) | reject (high) | A | - | no / no |
| amb30 | Italicize the stage directions. | A | B | ACCEPT / ACCEPT | ACCEPT / ACCEPT | accept (low) | accept (low) | neither (union of A and B) | - | yes / yes |
| amb31 | Make the title bigger. | A | B | REJECT / ACCEPT | REJECT / ACCEPT | accept (low) | accept (low) | A | - | no / yes |
| amb32 | Save it as a PDF too, on the Desktop. | A | B | UNDECIDED / UNDECIDED | REJECT / REJECT | accept (low) | reject (high) | A | - | no / no |
| amb33 | Put the title of the last slide in all caps. | A | B | UNDECIDED / UNDECIDED | UNDECIDED / UNDECIDED | accept (high) | accept (high) | A | - | no / no |
| amb34 | Delete the second slide. | A | B | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | - | no / no |
| amb35 | Center the title on the first slide. | A | B | REJECT / ACCEPT | REJECT / ACCEPT | accept (low) | accept (low) | A | A | no / yes |
| amb36 | Move the last bullet up. | A | B | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (medium) | A | - | no / no |
| amb37 | Make the headings on the overview slide match the title slide. | A | B | REJECT / REJECT | REJECT / REJECT | accept (low) | accept (medium) | A | - | no / no |
| amb38 | Change the title on the last slide to Launch day. | A | B | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | - | no / no |
| amb39 | Take the placeholder bullets off the agenda slide. | A | B | REJECT / REJECT | REJECT / REJECT | reject (medium) | reject (high) | neither | - | no / no |
| amb40 | On the last slide, make the links clickable. | A | B | ACCEPT / ACCEPT | REJECT / REJECT | accept (low) | reject (high) | A | - | no / no |

## Method (steps 0 to 4)

- Environment: Ubuntu 24.04, 4 CPUs, 7.8 GiB RAM. LibreOffice 24.2.7.2 installed for PDF rendering and verified (measured).
- End states (step 1): built by five builder subagents with Python edits to the Exp 5 starting snapshots (fetched by `research/exp5-grounded/fetch.py`, not committed). An independent tree diff (`tools/verify_endstates.py`) checked each state against its start. Seven requests have a state byte-identical to the start (amb03 A, amb14 B, amb24 A, amb25 A, amb26 A, amb35 A, and amb16 A and B), kept per the orchestrator's ruling (measured).
- Specs (step 2): 40 grounded specs written by fresh subagents, each seeing only the request text and the inspector report. Writers never saw the readings, end states, or brief. Frozen with 80 SHA-256 hashes (commit 4d5d23d). Hashes were checked before each executor run (measured).
- Executor (step 3): frozen `specexec.py` at c909d02 run on all 80 end states, plus each spec against the untouched start (240 runs). The primary and vacuous-all decisions agree on every run (measured). Results: `results/executor_results.json`. Sensitivity run: `results/executor_results_eqfix.json`.
- Judge packets (step 4): 80 blinded packets built with `tools/judge_packets_t6.py` and `tools/inspect_snapshot_t6.py`. Clip asserts pass on all 80 (measured). A rebuild is byte-identical to the committed set (measured). Verdicts from the Sol judge, joined through the blind map: all 80 present, no duplicates (measured).

## Findings from steps 1 to 4

1. Executor bug (measured). `CellObj` (table cells) and `RunP` (text runs) in `specexec.py` have no `__eq__`. Table-row and text-run equality is therefore identity-based. It makes `table(n).rows == before(...)` and `text_runs == before(...)` False even on an identical file. The primary result keeps the frozen file. The sensitivity run adds `__eq__` and `__hash__` in memory and changes 22 decisions. No spec uses `!=` on these values, so the bug causes false REJECTs, not false ACCEPTs, in the primary result.
2. amb37 is still wrong after the patch. `text_runs subset_of ['FFC000']` compares run objects with colour strings. This is a spec error (measured).
3. Start-state gate (inferred). The gate rule in `exp6-gate.md` requires a spec to REJECT the start root. Applied to measured START decisions, it would reject 11 of 15 start-accepting specs. Ten of those 11 are formatting checks the executor cannot read. One (amb12) is a content gap: the spec never checks the total. It would wrongly reject 4 specs whose followed reading is a no-op or no change (amb16, 22, 25, 35). The gate itself was not run on these specs (guess that it behaves as described).
4. Spec coverage gaps (measured). Formatting readings (bold, font size, fill, number format, alignment, highlight, italic, hyperlink) are not checked by the executor. Specs for those requests check content only, so both readings can be accepted (amb01, 08, 18, 29, 30, and in the sensitivity run 27, 28, 31).
5. Spec errors (measured). Parse errors leave predicates UNSUPPORTED for amb02, 05, 10, 23, 26, 33. amb24 reads `rows[10]` (0-based), which is the "NOT to be funded" row; the Total row is index 9 (inferred: spec index error from measured row content).
6. Writers followed reading A on 34 of 40 requests (mapped by me from writer flag text; writers never saw A or B). The most likely explanation is that A is the natural reading (inferred, not tested).
7. Degenerate and PDF cases (measured). amb20 and amb32 PDFs were hand-built, text-only, because LibreOffice was not yet installed when they were built. They were not re-rendered. amb34's two readings both assume a false premise: slide 2 is not picture-only, since its grouped shapes hold instruction text. amb32 B deletes the original pptx by design of that reading.

## Deviations and limits

- The Exp 5 writer instruction text is not in the repo. `writer_conventions.txt` was used (measured: file used; inferred: the Exp 5 prompt differs).
- Writers received a reader reference and filtered grammar examples, not the Exp 5 examples (most Exp 5 calc examples came from this request set).
- Judge packets used an inspector copy with its row, slice, and entry caps lifted (`tools/inspect_snapshot_t6.py`). Spec writers used the original inspector. Clip asserts pass on all 80 packets (measured).
- Snapshots were downloaded from HuggingFace at build time and are not committed. They are reproducible with `research/exp5-grounded/fetch.py`.
- The judge ran on the orchestrator side (Sol). I did not judge any state.
- The "intended" letters come from the orchestrator's scoring. I could not read the sealed intent file.
