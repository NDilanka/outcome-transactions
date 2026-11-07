# Experiment 9 preregistration: do rendered pages catch what the file dumps drop?

Status: LOCKED by commit 2e9eac4, which adds this file with the scripts, prompts and input manifest listed in section 9. Amendment 1 (section 10) was made after the lock and before any render. Amendment 2 (section 11) is post hoc: it was made after the group A renders and before any judge run. Amendment 3 (section 12) changes how a page over the 5 MiB read limit is written, and was made before the render restart and before any judge run. The lock commit hash is in the message to the orchestrator and in the results. Written before any Exp 9 render or judge call. The image-input probe (section 3) ran before the lock. No Exp 9 render or judge output exists yet.

## 0. Decisions settled before the lock (changes from draft v1)

- Render resolution is 150 dpi (draft v1 said 120).
- PyMuPDF 2.1 is the rasteriser (`pymupdf.__version__`, venv `/home/factory-user/venvs/exp6`). `pdftoppm` is not installed and is not used.
- Image input is confirmed (probe, section 3). The render judge is the Exp 7 dump judge, Sol.
- G1 is 4 of 4 renderable states, read as a proof-of-mechanism check (section 5). The "6 of 7" threshold of draft v1 does not apply to 4 states.
- G2 is decided on the 30 correct states (B plus D). Group B alone (5 states) is reported with the same comparison.
- barDir (0326d92d state_08) is outside all groups (section 4).
- Judge prompt is committed as two files with hashes. The render variant changes two sentences (section 3).
- Packet layout, the file list, the batch cap and the undecided rule are fixed (section 3).
- Group D was added during review of draft v1. It was not in the original design. Its size and seed were confirmed by the orchestrator.

## 1. Why

Exp 7 found 8 corrected wrong accepts that the combined policy committed (spec ACCEPT and Sol judge accept). Each turns on a property that no reader, checker or judge packet exposes: text alpha, text luminance, a shape fill, a merged table cell, or the insertion cursor. A reviewer from a third lab, which saw only the request and the raw files, accepted all 8 as well. The blind spot is in what the readers see, not only in the packet. Exp 9 tests a different representation: rendered pages. The judge sees pictures only.

## 2. Questions

- Primary: how many of the 8 corrected wrong accepts does the render judge reject? Counted separately for the renderable and the non-renderable states (section 4).
- Cost: the render judge's false-reject rate on correct states, its reject rate on the random wrong sample, and render time per state.

## 3. Frozen before data

Representation
- Renderer: LibreOffice 24.2.7.2 headless (`/usr/bin/soffice`). Each state gets a new user profile (`-env:UserInstallation=file://<new directory>`), deleted when the state is done. Every timing therefore includes a cold start.
- Each office file is copied to a private work directory before conversion, because LibreOffice writes lock files beside its source. The copy is converted to PDF with `--convert-to pdf`, in its own folder.
- Rasteriser: PyMuPDF 2.1. Every page is rendered to PNG at 150 dpi with alpha off. Each PNG is checked: only the IHDR, pHYs, IDAT and IEND chunks are allowed, so no text or metadata chunk reaches the judge. PDF metadata never reaches the judge.
- File types: the 78 states hold 163 files, all office documents (53 docx, 51 pptx, 41 xlsx, 14 odt, 3 ods, 1 odp). Any other file type stops the run.
- Pages: every page of every file on each side. No page cap. A file identical on both sides is still rendered on each side where it exists.
- Packet, one directory per blind id (written by `render_lib.py`):
  - `request.txt`: the request text, then a file list with one line per file: its number, its path inside the state, and the folders that hold its pages.
  - `start/fNN_pNNN.png` and `end/fNN_pNNN.png`: one PNG per page. NN numbers the files in sorted order of the relative paths present in either state. NNN is the page number inside that file, from 1.
  - Image names carry no task, state, filename or label. The folder names `start` and `end` say which state a page belongs to. They are the two states compared, not labels.
- Judge input: the packet only. The file list gives paths but not sizes. Nothing else: no dumps, inspector output, diffs, labels, Exp 7 verdicts, spec output, reviewer output or adjudication notes.
- Inputs: before = `research/exp5-grounded/snapshots/<task>`; after = the normalised states that the Exp 7 executor and Sol judge saw, `/tmp/exp7/states_norm/<task>/<state>`. `input_manifest.json` holds the sha256 of every input file, in sorted path order, keyed by blind id. The renderer hashes both sides before and after rendering and stops if either changed.
- Read limit: the judge reads images with its Read tool. A PNG over 5 MiB stops the run before judging.

Judge
- Judge: Sol (`pv-sol-xhigh`), the judge of Exp 6 and Exp 7.
- Image-input probe, run by the orchestrator before this lock: `pv-sol-xhigh` read a test PNG through the Read tool and reported it correctly (a solid blue rectangle on the left, and the small red text "K7Q" to its right). The image reaches the model through the Read tool. This is the same model as the Exp 7 dump judge, so G2 compares like with like.
- Instruction text: `sol_prompt_exp7.txt` is the Exp 7 template, verbatim. `sol_prompt_render.txt` differs from it in two sentences only: the packet description (now the request with its file list, and page images) and "If the images cannot show whether the request is met" (in place of "If the dump cannot show"). The diff is in the lock commit. Both hashes are recorded in section 9. The Exp 7 template was restored from the orchestrator's judge runner text, which is outside this repository. Before batch 1, the orchestrator compares the sha256 of `sol_prompt_exp7.txt` with its runner's copy.
- Verdict format: unchanged. Accept or reject, confidence high, medium or low, a one-sentence reason, and one entry per packet.
- Batches: sort the blind ids and cut them into consecutive groups of 4. A group whose PNG total is over 40 is split into consecutive runs, taking states in order while the total stays at or under 40. A state with more than 40 PNGs is judged alone in its own batch, with no PNG cap (Amendment 1, section 10). Splits depend only on PNG counts, never on verdicts. No page is dropped or truncated. If a batch cannot be judged, the run stops and the orchestrator reports it.
- Undecided: a missing verdict, an unparseable file, or an id not in the batch is undecided. Undecided counts as a reject for G2 and as a miss for G1. Both choices are conservative for the render key.
- One judge run. A rerun is labelled post hoc.

Blinding
- Fresh salted blind ids: `bid9 = sha256(SALT + "|exp9|" + task + "|" + state)[:12]`. The Exp 7 ids (`sha256("exp7-" + task|state)`, unsalted) are not used.
- SALT is 32 random bytes, stored as 64 hex characters in a private file. Its commitment is `sha256(SALT text)` = `4bd21c633107aafa13ad58023c7bc7c1d9647889c5a7706067825d1195a19e19`, where the SALT text is the file content without its final newline. SALT is revealed only after the judge run and scoring.

## 4. States

| Group | Definition | n | Pool | Seed | sha256 of sorted "task\|state" list |
|---|---|---|---|---|---|
| A | The 8 corrected wrong accepts of the combined policy (corrected WRONG, spec ACCEPT, Sol accept) | 8 | fixed | none | `ed413c66d9016879ea2bad8f5864bcaa8e55133c92b06d16cabe5b97896142fe` |
| B | Corrected CORRECT states on the same tasks as A (57667013, 66399b0d) | 5 | fixed | none | `094409b65de8809a23175ff042f14ea2a04f98ad0507212dca577ef737cb0305` |
| C | Seeded random sample of corrected WRONG states not in A | 40 | 300 | `exp9-sample-C-v1` | `25e4837ba8640ef21d77e2f0042215b01ecf1f721ea32b30f9f6e9c5fb739b1a` |
| D | Seeded random sample of corrected CORRECT states on the other tasks | 25 | 59 | `exp9-sample-D-v1` | `81f7ca3b13b07262e76fafb5a9f6c1dc0ae1ab7e8df17207c33d1949986adfb9` |

Total: 78 states. The correct comparison set for the cost gate is B plus D: 30 states.

Group A members and renderability. The checks are in `renderability_checks.py` and run on the same packets the judge reads.

| Task | State | Adjudicated property | Renderable | Check |
|---|---|---|---|---|
| 57667013 | 19 | Slide 5 text alpha 0 (text invisible) | yes | `check_text_alpha`: slide 5 has at least 20 yellow text pixels inside its yellow text spans before, and at most 5% of that after |
| 57667013 | 20 | Slide 5 text lumMod 60000 (dark olive, not FFFF00) | yes | `check_text_luminance`: the yellow test as above, and after has at least 20 dark olive pixels (R 100 to 200, abs(R-G) at most 20, B at most 60) in those spans |
| 57667013 | 22 | Six slide 5 shapes with solid black fill | yes | `check_black_fills`: after has at least 6 more black filled shapes (area at least 100 pt²) and at least 500 more near-black pixels on slide 5 |
| 66399b0d | 17 | Inserted table with a gridSpan=7 row | yes | `check_merged_row`: after has at least 1 more table row drawn as one cell spanning at least 95% of its table |
| 66399b0d | 01 to 04 | Cursor position of the inserted table (not recorded in the file) | no | No check. The docx records no cursor (checked in Exp 7). Judged and reported separately. |

Thresholds are fixed in the code and were not tuned on any render. Expected renderable count r = 4. A state whose check fails is non-renderable and reported that way. It is still judged.

barDir. The chart-orientation property (0326d92d state_08, a horizontal bar chart) is not one of the eight. Under the primary reading, bars are read as horizontal bars, and the state is CORRECT. Under the column reading it is WRONG, which Exp 7 §5 records as a reader gap. The state is in none of groups A, B or C, and it is not in the drawn D sample. It is in the D pool. It is therefore not rendered or judged in Exp 9. It is not added to group A without an orchestrator ruling. If it is ever drawn into a group, its render shows horizontal bars, and a judge reject on it is a false reject under the primary reading.

Sampling procedure (Python 3.12.3):
```python
import random
pool = sorted(pool_states, key=lambda s: s["task"] + "|" + s["state"])
sample = random.Random("exp9-sample-C-v1").sample(pool, 40)   # C; D uses 25 and "exp9-sample-D-v1"
```
The C pool is the 300 corrected WRONG states not in A. The D pool is the 59 corrected CORRECT states not in B. Commitment: `sha256("\n".join(sorted(task + "|" + state for each member)))`, given in the table above. Members are published at unblinding. Anyone with the Exp 7 corrected table can recompute them from the seed.

## 5. Gates (pre-registered)

G1, detection (proof of mechanism). The render judge rejects every renderable group A state.
- Four states are expected to be renderable. G1 passes only if all four are rejected. Any miss fails G1.
- This is a mechanism check on four states. It is not a rate.
- If fewer than four states pass their check, G1 is decided on the states that pass, and the shortfall is reported.
- Cursor-state rejects are counted and reported separately. They do not count toward G1. A cursor-state reject that cites table placement at the end of the document is reported as a placement reading, not as detection of the cursor property.

G2, cost. The render judge's false-reject rate on the correct comparison set (B plus D, 30 states) is at or below Sol's rate on the same 30 states.
- Sol's rate, from the primary Exp 7 Sol run (`judge_verdicts`, not the cap-fix rerun): 9 of 30 = 30.0% (exact 95% interval 14.7% to 49.4%). B: 1 of 5. D: 8 of 25.
- Undecided counts as a reject (section 3).
- Compare point rates as written. Report exact 95% binomial (Clopper-Pearson) intervals for both rates. With 30 states the comparison has little power, and the results say so.
- Group B alone (5 states; Sol 1 of 5 = 20.0%) is reported with the same comparison. It is not part of the gate. Five states cannot carry a gate.

Earns a place: G1 and G2 both pass. If either fails, the render key does not earn a place, and the result is reported as is.

## 6. Secondary and cost measurements

- Render judge on group C (40 states): the reject count, and whether each reject's reason names the property the Exp 7 adjudication recorded (checked after the run).
- Render time per state: wall clock of `render_state`, covering the new profile and cold start, conversion, rasterising and PNG checks. Input hashing is excluded. Report median, 90th percentile and maximum over the 78 states, and name the largest state. Also report PNGs per state, PNGs per batch, and the largest PNG in bytes.
- Judge cost: PNGs per batch and, if the provider reports them, tokens per batch.

## 7. Limits stated in advance

- Spreadsheets render as print output. Hidden rows and columns and cells outside the print range do not appear. Counted by file type.
- 150 dpi may not show very small print. A reject on small text is a reject the render made, not a check of the dump's exact text.
- PDF exports do not carry transitions or animations. Exp 7 transition verdicts (21760ecb) cannot be checked by renders.
- LibreOffice is the only renderer. PowerPoint and Word behaviour is not verified.
- File names and paths reach the judge through the file list. File sizes do not.
- Group A has 4 renderable states. Any result describes those states.

## 8. Run order after the lock

1. Lock commit (this commit).
2. `renderability_checks.py`: renders the four group A states that have a check, and runs the checks. It also writes the packets for those states.
3. `render_all.py`: renders groups B, C and D and the four cursor states (74 states), then cuts all 78 into judge batches.
4. The orchestrator runs the judge batches and saves each verdict file verbatim.
5. Score, reveal SALT, publish `exp9-results.md`.

Nothing in this document depends on any render or judge output.

## 9. Lock contents

- `exp9-preregistration.md` (this file)
- `sol_prompt_exp7.txt`: sha256 `7b230f87ab17b6c0f68271759178fc18e7ac4c54165bb9158272f8852256e5f8`
- `sol_prompt_render.txt`: sha256 `242c0e168f3ee510bfd41fa7294a8894cb7631e34067bcd25845ab3247939d17`
- `render_lib.py`, `renderability_checks.py`, `render_all.py`, `input_manifest.py`
- `input_manifest.json`: sha256 `e48200d75524619a8ad7edfc5972934969978f936ab623716c915757a7746f9a`, 78 blind ids, 163 input files

## 10. Amendment 1 (made before any render)

- A state can have more than 40 PNGs. A deck of 24 or more slides gives 48 or more PNGs for the before and after sides together. Such a state is judged alone in its own batch, with no PNG cap. Its PNG count and page count are reported with the results. Its pages are never truncated, dropped or split across batches.
- The 5 MiB per-PNG limit (section 3) still applies. A state whose PNG would exceed it stops the run before judging.
- The amendment was made and published before any render. Batch files, PNG counts per batch and the largest batch are reported with the results.
- The amendment changes no group, gate or threshold.

## 11. Amendment 2 (post hoc: written after the group A renders, before any judge run)

Why this is labelled post hoc. The registered checks in section 4 assume that the before slide 5 text of 57667013 is yellow (FFFF00). It is green (#9EEFBC). Yellow text appears only in the after states. Draft v1 carried the same assumption. The first group A renders showed it: `renderability_checks.py` made 1 of 4 states renderable. Its evidence is in its result file, which is not committed. This amendment corrects the predicates to test what each property does to the render: alpha 0 removes the green text, and lumMod 60000 turns the yellow into dark olive. No judge has run, and no verdict exists.

What changes. Groups, sample, judge input, prompt, batch rule and gate thresholds do not change. Only the renderability decision for group A changes, in `renderability_amendment2.py`:
- 57667013 state_19 (alpha 0): renderable if the before render has at least 20 pixels within 10 per channel of 9EEFBC inside the before slide 5 text spans, and the after render has at most 5% of that count in the same rectangles.
- 57667013 state_20 (lumMod 60000): renderable if the after render has at least 20 dark olive pixels (R 100 to 200, |R-G| at most 20, B at most 60) inside the after slide 5 text spans of colour 999900, and at most 5% as many FFFF00 pixels in those rectangles.
- 57667013 state_22: unchanged. Still renderable.
- 66399b0d state_17: not renderable under either reading. No check separates it from the before render, because the before render already has the same full-width single-cell rows (table rows 0 and 10). The render cannot show this error. It is a finding, not a gap in the check.
- 66399b0d state_01 to state_04 (cursor): not renderable, unchanged.

Evidence, from the group A renders already on disk (no re-render, no judge):

| State | Quantity | Value |
|---|---|---|
| 57667013 state_19 | green (9EEFBC) pixels in the before text spans (4 spans) | 162,883 |
| 57667013 state_19 | green pixels in the same rectangles, after | 0 |
| 57667013 state_20 | dark olive pixels in the after text spans (5 spans) | 175,574 |
| 57667013 state_20 | FFFF00 pixels in the same rectangles, after | 0 |
| 57667013 state_20 | FFFF00 pixels in the same rectangles, before | 0 |
| 57667013 state_22 | black-filled shape delta; near-black pixel delta | 6; 2,808,399 |

G1 under both readings. The judge decides nothing until the batches run, so these are the reporting rules, fixed now.
- As registered: renderable = {state_22}. G1 is decided on one state.
- Amended: renderable = {state_19, state_20, state_22}. G1 requires all three to be rejected.
- The headline claims a G1 pass only if G1 passes under both readings. Under the amended reading that means all three are rejected.
- 66399b0d state_17 is judged like every group A state. Its verdict is not counted toward G1 under either reading. It is reported with the cursor states as errors no current representation shows.

Renderer note. During the 74-state render, PyMuPDF printed "cannot create appearance stream for Screen annotations" for several PDFs. These are form-field annotations in LibreOffice output. The pages are rendered as PyMuPDF produces them. The count of such warnings is reported with the results.

## 12. Amendment 3 (made before the render restart and before any judge run)

Why. `render_all.py` stopped at state 4b462954d9bd: its start side, page 6 (`f01_p006.png`, 3000×1688 px), was 5,525,955 bytes, over the 5 MiB read limit of section 3. The stop was as registered. No judge had run, and no batch files were written. The orchestrator ruled on the remedy below.

Rule, for every packet page:
1. The page is written by PyMuPDF at 150 dpi, as in section 3. If the file is at most 5 MiB (5,242,880 bytes), it is kept as written. Nothing else changes.
2. A page over 5 MiB is re-encoded losslessly (PIL, optimize, zlib level 9). The decoded pixels must equal the rendered pixels exactly, or the run stops. If the re-encoded file is at most 5 MiB, it is kept.
3. A page still over 5 MiB after re-encoding is split losslessly into horizontal tiles: full-width strips, cut top to bottom at equal row heights. The number of strips is the smallest K from 2, up to 64, for which every strip is at most 5 MiB. Strips are named `fNN_pNNN_tK.png`, with K counted from 1 from the top. Each strip's decoded pixels must equal its row band of the rendered page. The strips together must equal the rendered page exactly. The unsplit `fNN_pNNN.png` is removed.
4. The judge input notes each tiled page in `request.txt`, under a "Notes:" heading after the file list. The note reads, for example: "start/f03_p001 is shown as 3 horizontal tiles, start/f03_p001_t1 to start/f03_p001_t3, from top to bottom. Together they make one page." This note is the only change to the judge's input text.
5. No downscaling, no lossy compression, no dropped or truncated page. The page count per file and per side is the count section 3 reports.
6. Scope. Rule 2 applies only to pages over the limit. Other packet PNGs are kept byte-identical to what PyMuPDF wrote. The group A packets from `renderability_checks.py` are all under the limit (largest 2,158,326 bytes), so they are not changed by this amendment. Re-encoding every PNG would change bytes, not pixels, and was not done.
7. Reporting. Per state, `stats.json` records the pages kept, re-encoded and tiled, and the tile count. The results report the number of files re-encoded and the number tiled, and name each tiled page. The four renderable group A states were rendered before this amendment and are not rendered again. Their stats gain these keys from their files (`kept_stats` in `render_all.py`): each file is one PNG per page, named as section 3 says, and at most the limit, so each page counts as kept.

Interpretation to confirm. "Horizontal tiles" is read here as full-width strips stacked top to bottom. A split into side-by-side columns would be a different representation and is not what this rule states.
