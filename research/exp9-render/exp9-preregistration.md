# Experiment 9 preregistration: do rendered pages catch what the file dumps drop?

Status: DRAFT for orchestrator confirmation. Written before any render, judge call or Exp 9 verdict exists. Not locked. The lock commit (below) freezes the decisions after the open items in section 8 are settled. No render or judge run has happened.

## 1. Why

Exp 7 found 8 corrected wrong accepts that the combined policy committed (spec ACCEPT and Sol judge accept). Each turns on a property that no reader, checker or judge packet exposes: text alpha, text luminance, a shape fill, a merged table cell, or the insertion cursor. A reviewer from a third lab, which saw only the request and the raw files, accepted all 8 as well. The blind spot is in what the readers see, not only in the packet. Exp 9 tests a different representation: rendered pages. The judge sees pictures only.

## 2. Questions

- Primary: how many of the 8 corrected wrong accepts does the render judge reject? Counted separately for the renderable and the non-renderable states (section 4).
- Cost: the render judge's false-reject rate on correct states, its reject rate on the random wrong sample, and render time per state.

## 3. Frozen before data

Representation
- Renderer: LibreOffice 24.2.7.2 headless. Each state gets its own user profile (`-env:UserInstallation` pointing to a fresh directory), so no profile is shared. Export to PDF with `--convert-to pdf`.
- Rasteriser: PyMuPDF, every page to PNG at 120 dpi. The version is pinned in the lock commit. `pdftoppm` is not installed on this machine, so PyMuPDF (or an approved alternative) must be confirmed first (section 8).
- Pages: every page of every office document is rendered. No page cap. Each file present in the before or the after state is rendered on each side where it exists. Files that are the same on both sides are still rendered.
- Judge input: the request text, then the before and after PNGs. Nothing else. No XML dumps, inspector output, diff text, file sizes, labels, Exp 7 verdicts, spec output, reviewer output or adjudication notes.
- Inputs: before = `research/exp5-grounded/snapshots/<task>`; after = the normalised states the Exp 7 executor and Sol judge saw (`/tmp/exp7/states_norm/<task>/<state>`). The lock commit records the sha256 of every rendered input file.

Judge
- Judge: Sol (`pv-sol-xhigh`), the judge of Exp 6 and Exp 7. Same instruction text as those runs; the only change is the input description (page images instead of packets). The instruction text is not in the repository (section 8).
- Verdict format unchanged: accept or reject, confidence high, medium or low, and a reason.
- Batches of 4 states or fewer. Batch membership: sort the salted blind ids and cut them into consecutive groups of 4, so no batch is built from one group or one task. If a batch exceeds the judge's image limit, split it further. Splits depend only on image counts, never on verdicts.
- One judge run. A rerun is labelled post hoc.

Blinding
- Blind ids are fresh and salted: `bid9 = sha256(SALT + "|exp9|" + task + "|" + state)[:12]`. The Exp 7 ids (`sha256("exp7-" + task|state)`, unsalted) are not used.
- SALT is 32 random bytes, held privately. Its commitment is `sha256(SALT text)` = `4bd21c633107aafa13ad58023c7bc7c1d9647889c5a7706067825d1195a19e19`. SALT is revealed only after the judge run and scoring.

## 4. States

| Group | Definition | n | Pool | Seed | sha256 of sorted "task\|state" list |
|---|---|---|---|---|---|
| A | The 8 corrected wrong accepts of the combined policy (corrected WRONG, spec ACCEPT, Sol accept) | 8 | fixed | none | `ed413c66d9016879ea2bad8f5864bcaa8e55133c92b06d16cabe5b97896142fe` |
| B | Corrected CORRECT states on the same tasks as A (57667013, 66399b0d) | 5 | fixed | none | `094409b65de8809a23175ff042f14ea2a04f98ad0507212dca577ef737cb0305` |
| C | Seeded random sample of corrected WRONG states not in A | 40 | 300 | `exp9-sample-C-v1` | `25e4837ba8640ef21d77e2f0042215b01ecf1f721ea32b30f9f6e9c5fb739b1a` |
| D | Seeded random sample of corrected CORRECT states on other tasks (added, see section 8) | 25 | 59 | `exp9-sample-D-v1` | `81f7ca3b13b07262e76fafb5a9f6c1dc0ae1ab7e8df17207c33d1949986adfb9` |

Total: 78 states. The correct comparison set for the cost gate is B plus D: 30 states.

Group A members and renderability:

| Task | State | Adjudicated property | Renderable | Check that decides it (PyMuPDF, after vs before PDF) |
|---|---|---|---|---|
| 57667013 | 19 | Slide 5 text alpha 0 (text invisible) | yes | Slide 5 text runs have opacity 0 in the after PDF and are opaque in the before PDF |
| 57667013 | 20 | Slide 5 text luminance lumMod 60000 (dark olive, not FFFF00) | yes | Slide 5 text colour in the after PDF is not FFFF00; in the before PDF it is FFFF00 |
| 57667013 | 22 | Six slide 5 shapes with solid black fill | yes | The after PDF has at least six black filled rectangles on slide 5 that the before PDF lacks |
| 66399b0d | 17 | Inserted table with a gridSpan=7 row (one visible cell) | yes | In the after PDF, one row of the new table is drawn as a single cell spanning the table width |
| 66399b0d | 01 to 04 | Cursor position of the inserted table (not recorded in the file) | no | Not a render property. The docx XML records no cursor (checked in Exp 7). Reported separately. |

Expected renderable count r = 4. A renderable state whose check fails becomes non-renderable and is reported that way. The checks are code, committed before any render.

The barDir property (chart orientation, 0326d92d state_08) is not one of the eight, so it is outside the primary count. If state_08 is drawn into group D, its render will show horizontal bars, and a judge rejection on that state counts as a false reject.

Sampling procedure (Python 3.12.3):
```python
import random
pool = sorted(pool_states, key=lambda s: s["task"] + "|" + s["state"])
sample = random.Random("exp9-sample-C-v1").sample(pool, 40)   # C; D uses 25 and "exp9-sample-D-v1"
```
Commitment: `sha256("\n".join(sorted(task + "|" + state for each member)))`. Members are published at unblinding. Anyone with the Exp 7 corrected table can recompute them from the seed.

## 5. Gates (pre-registered)

G1, detection. The render judge rejects the renderable group A states.
- Requested threshold: at least 6 of 7 renderable wrong accepts.
- Count problem: only 4 of the 8 are renderable (section 4), not 7. The 4 cursor states cannot be rendered. Six of seven cannot apply to 4 states.
- Proposed threshold, pending confirmation: reject all renderable states (4 of 4). Out of 4 states, 4 of 4 is the only count that keeps the rate at or above 6/7; 3 of 4 is 75%.
- Cursor-state rejects are counted and reported separately. They do not count toward G1. A cursor-state reject that cites table placement at the document end is reported as a placement reading, not as detection of the cursor property.

G2, cost. The render judge's false-reject rate on the correct comparison set (B plus D, 30 states) is at or below Sol's rate on the same 30 states.
- Sol's rate, from the primary Sol run (`judge_verdicts`, not the cap-fix rerun): 9 of 30 = 30.0%. B: 1 of 5. D: 8 of 25.
- Compare point rates as written. Report exact 95% binomial intervals for both. With 30 states the comparison has little power, and this is stated in the results.

Earns a place: G1 and G2 both pass. If either fails, the render key does not earn a place, and the result is reported as is.

## 6. Secondary and cost measurements

- Render judge on group C (40): reject count, and whether each reject cites the adjudicated property.
- Render time per state, measured in a fresh process: convert before and after, rasterise all pages, and include the LibreOffice cold start for the first state with a new profile. Report median, 90th percentile and maximum over the 78 states, with the largest state named. Also report images per state and per batch.
- Judge cost: images and, if the provider gives them, tokens per batch.

## 7. Limits stated in advance

- Spreadsheets render as print output. Hidden rows and columns and cells outside the print range are not shown. Counted by file type.
- PDF exports do not carry transitions or animations. Exp 7 transition verdicts (21760ecb) cannot be checked by renders.
- LibreOffice is the only renderer. PowerPoint and Word behaviour is not verified.
- Group A has 4 renderable states. Any result describes those states.

## 8. Open items (must be settled before the lock commit)

1. Sol instruction text. The Exp 6 and Exp 7 Sol prompt is not in the repository. The orchestrator's judge runner holds it. The exact text must be committed or hashed at lock, and the input-description change must be its only edit.
2. Image input. Confirm that `pv-sol-xhigh` accepts image input. This is not assumed. If it does not, the judge is a different vision model. Then G2 compares different judges, and the gate reading must be redone before the run.
3. G1 threshold. Confirm "reject all 4 renderable" (or give another integer). The requested "6 of 7" cannot apply to 4 states.
4. Group D. Confirm adding 25 correct states from other tasks. Group B alone has 5 states, which cannot give a meaningful false-reject comparison. D is added by the author of this draft, not in the original design.
5. Rasteriser. `pdftoppm` is not installed. Confirm PyMuPDF in the venv (`/home/factory-user/venvs/exp6`) and pin its version. No install has been done.
6. Renderability checks. Written and committed before any render.

Run order after confirmation: (1) lock commit with the decisions above, the instruction text or its hash, the check code and a sha256 manifest of inputs; (2) renderability checks on group A; (3) render all 78 states and time each; (4) batch and run the judge, saving verdicts verbatim; (5) score, reveal SALT and publish results as `exp9-results.md`.

Nothing in this document depends on any render or judge output.
