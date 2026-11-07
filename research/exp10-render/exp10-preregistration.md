# Experiment 10 preregistration: does a render judge catch what the text judge accepts?

Status: written before any Exp 10 render. The lock commit on branch `exp10-render` adds this file with the scripts and prompt in section 11. Its hash is in the message to the orchestrator. One scratch render of a single Exp 8 docx attempt ran before the lock, to check the pipeline. Its output is outside the repository, was not packeted, was not judged, and is not used.

## 0. Decisions for the orchestrator to approve before any render

1. Profile states. The 4 attempts of the auto-save request (2cd43775) are LibreOffice profile folders, not office files. They are not rendered and get no packet. Under the undecided rule the render verdict on them is reject. This makes the render key remove the wrong commit 083c86e1 by construction. The gate is therefore also scored with 2cd43775 removed from every policy (section 7).
2. Live UI block. Exp 8 gave the judge a live UI block for the 20 attempts in condition `ui`. The render judge gets the same text, appended to request.txt under the heading "Live UI state:". The 12 ablation attempts (condition `noui`) get no block. The block is needed to read the request (for example "right after this one" in ecc2413d).
3. Prompt. `sol_prompt_render.txt` is used unchanged (sha256 242c0e16...). The UI block sits inside the request text, which the prompt already describes as "the request with its file list, and page images".
4. Gate. Section 7 proposes a gate on two bases. The gate is fixed here, before any judge run.
5. Row check. Section 6 defines the table row check. Its results go into this file as Addendum A before any packet is published.

## 1. Why

Exp 9 tested the render judge on Exp 7 states. Its predicates were written after the first group A renders (Amendment 2), and its states were chosen from Exp 7 adjudications. Exp 10 tests the render judge on the Exp 8 real-agent outputs. Those outputs were produced by agents that never saw the render, and their labels (GT v4) were set in Exp 8. Exp 8's text packets did not show pagination, and three of the wrong accepts are a missing blank page that a render can show.

## 2. Questions

- (a) Of the 7 wrong accepts of Sol's first pass (GT v4, strict auto-save reading), how many does the render judge reject? Split by the renderability flag in section 5. Also reported: the 6 wrong accepts that survive Exp 8's post hoc Sol self-consistency key (the same 7 without 083c86e1). The key is not used for any primary number.
- (b) Joint table, render judge against Sol's first pass, over the 80 rendered states (section 4): wrong states (both reject, render only, Sol only, both accept), and correct states (the same four cells, where "reject" on a correct state is a false reject). The 4 profile states are reported separately with Sol's verdict only.
- (c) Commit policies on the 18 requests, scored against GT v4: A (Sol), R (render), A AND R. Each policy is scored as zero-click correct commits (G0), wrong commits, and CONFIRM (no commit).
- Cost: the render judge's false-reject rate on the correct states, with exact (Clopper-Pearson) 95% intervals, and render time per state (section 8).

## 3. Frozen before data

Representation (same as Exp 9 section 3, with the Exp 10 inputs):
- Renderer: LibreOffice 24.2.7.2 headless (`/usr/bin/soffice`). Each state gets a new user profile (cold start, included in the timing). Each office file is copied to a private work directory before conversion, then converted to PDF.
- Rasteriser: PyMuPDF 2.1, from PyPI into venv `/home/factory-user/venvs/exp10`. The venv named in Exp 9 (`exp6`) no longer exists, so this version is pinned here. Every page is rendered at 150 dpi with alpha off. Each PNG passes the chunk check (only IHDR, pHYs, IDAT and IEND).
- Oversize pages: `render_lib.py` at commit 4bc82d0 (Amendment 3 of Exp 9, section 12 of its prereg). A page over 5 MiB is re-encoded losslessly, then cut into full-width strips if still over. Pixels are checked at each step. Oversize states are judged alone (Exp 9 Amendment 1). No page is downscaled, dropped or truncated.
- Packet: one directory per blind id, `request.txt` plus `start/` and `end/`. `request.txt` holds the request text (the Exp 8 instruction, the same text as the Exp 4b task file, checked equal for all 66 tasks), then the Live UI block for condition `ui`, then the file list, then notes for tiled pages. Image names carry no task, state, code or label.
- Inputs: start = the attempt's input file (Exp 8 `run/<code>/input`). End = the attempt's end state (Exp 8 `exec/<code>/result.json`, `end_state`). Each side has one office file. The renderer hashes both sides before and after rendering and stops on any change. `input_manifest.json` holds the sha256 of every input file, keyed by blind id.
- Leak check: `exp10_run.py` checks every `request.txt` for task ids, attempt codes, run paths, and judge, spec or executor words, and checks that each packet holds only `request.txt`, `start/` and `end/`. Packets are not published unless it passes.
- Batches: sorted blind ids in groups of 4. A group over 40 PNGs is split into consecutive runs in order while the total stays at or under 40. A state over 40 PNGs is alone in its batch. Splits depend only on PNG counts, never on verdicts.

Judge:
- Judge: Sol (`pv-sol-xhigh`), with `sol_prompt_render.txt` unchanged. Verdict format unchanged: accept or reject, confidence high, medium or low, one sentence of reason, one entry per packet.
- One judge run. The orchestrator runs the batches and saves each verdict file verbatim. A rerun is labelled post hoc.
- Undecided: a missing, unparseable or unmatched verdict, or no packet (the 4 profile states). Undecided counts as reject for R and A AND R.

Blinding:
- Blind id: `bid10 = sha256(SALT + "|exp10|" + attempt code)[:12]`. Fresh: it is not the Exp 8 id (`sha256("exp8|" + code)`, unsalted) and not the Exp 9 id.
- SALT: 32 random bytes as 64 hex characters, in a private file (mode 600, outside the repository). Commitment: `sha256(SALT text)` with no final newline = `a3bdd873ee37ff981732b87d04d0a7fd04b6f2a18a04d705fc927744789ec07d`. SALT is revealed only after scoring.
- The blind map (blind id to attempt code) stays private until scoring.

Reference (GT and Sol's first pass), held privately, hashes committed here:
- `final_gt_v4.tsv`: sha256 `a5b9ac92493c7ff8063269d0aff5bf66964c61873f5aa25e5043fb98f51a4e94`. The strict auto-save reading overrides 083c86e1, 81a65c80 and a9e34228 to W, as in Exp 8 `metrics.py` (`AUTOSAVE_STRICT_W`). Sensitivity reading: all four auto-save candidates C.
- Sol's first-pass verdicts (`judge_by_code.tsv`): sha256 `6f7553781a0f8ebdfbf40e7b4ed87131d171e49ce220091727b961b6aef85d37`.

## 4. States

| Group | Definition | Count |
|---|---|---|
| Primary | 18 requests, 4 methods each (condition `none` or `ui`) | 72 |
| Ablation | 3 requests (66399b0d, 550ce7e7, 21760ecb), condition `noui` | 12 |
| Rendered | Office attempts: 68 primary + 12 ablation | 80 |
| Not rendered | Profile attempts: 4 (2cd43775, methods 1 to 4) | 4 |

GT v4 strict over the 84 attempts: 70 C and 14 W. Office states: 69 C and 11 W. Profile states: 1 C (76604199) and 3 W (083c86e1, 81a65c80, a9e34228).

Sol's first pass over the 84: 64 accept, 20 reject. Wrong accepts: 7 (section 5). Correct states rejected: 13 of 70.

Policy set: the 72 primary attempts on 18 requests. The 12 ablation attempts are not in any policy. They are in the joint table (b) and in the render cost measures.

## 5. Renderability, fixed before any render

The 7 wrong accepts of Sol's first pass:

| Attempt | GT v4 | Sol first pass | Renderable | Rule |
|---|---|---|---|---|
| 2cd43775, method 1 | W (strict) | accept, high | no | Profile folder, not rendered (section 0). The setting is not on any page. |
| 66399b0d, method 4 (ui) | W | accept, low | no | Cursor position. The file does not record the cursor, and the UI block is the only record. Same rule as Exp 9 cursor states. |
| d53ff5ee, method 2 | W | accept, high | no | Request reading: lowercased ordinary-case words. The text is visible on the page, but whether it is wrong depends on how "all uppercase text" is read (GT ruling d53ff5ee, option a). No pre-registered predicate. |
| d53ff5ee, method 4 | W | accept, high | no | Same as method 2. |
| ecc2413d, method 1 (ui) | W | accept, low | yes | Page count (predicate below). |
| ecc2413d, method 2 (ui) | W | accept, low | yes | Same. |
| ecc2413d, method 4 (ui) | W | accept, low | yes | Same. |

Predicate for ecc2413d (renderable). The request asks for "a blank page right after this one", with the cursor on page 1. The defect is that no blank page is added. The state is renderable if its end render has the same number of pages as its start render (the render shows no added page). The correct method 3 has one page more than its start render, and it is not in this set. Expected: 7 pages each side for methods 1, 2 and 4. The render count is checked before judging, and any difference is reported.

Other wrong states (the rest of the 14) are not classified here. Their verdicts are reported in (b) without a renderability flag.

Limits of the classification: a state marked not renderable can still be rejected by the render judge. Such a reject is reported as a reject on a non-renderable state, not as a render detection.

## 6. Table row check (orchestrator addendum for Exp 10)

Why. In Exp 9, one bordered docx table drew 3 of its 5 rows in the render, and the cause was not found. A render that drops rows shows the judge less than the file holds. The check finds that before judging.

Scope. Docx tables only. All 24 docx attempts have a table on both sides. The pptx and odt files of Exp 8 contain no tables (pptx has no table shapes, odt has no table element). Xlsx files have no tables. Spreadsheet print output is covered by the Exp 9 limits.

Test (`exp10_rowcheck.py`). For each table row, a cell counts if its text has at least 3 characters after whitespace is removed. A row with at least one such cell is checkable. It is drawn if each of its checkable cell texts appears in the text of the rendered PDF pages (whitespace removed). A row with no checkable cell is reported as not checkable. This is a text presence test, not a border test: "drawn" means the row's text is in the render. Output holds row numbers and counts only.

Result. Addendum A to this file lists every mismatch: blind id, side, table, row numbers, file row count, and rows not checkable. It is written after the render and before any packet is published. Mismatched states are not removed from judging. Each mismatch is inspected before results are written, and its cause is reported. A mismatch is a render limit, not the attempt's defect.

## 7. Policies, scoring and gate

Policies. Each request has 4 candidates (primary attempts, method order 1 to 4). A candidate is accepted by a judge if its verdict is accept. Undecided is reject.
- A (Sol): commit the candidate Sol accepts with the highest Sol confidence (high, then medium, then low). Ties go to the lower method number.
- R (render): commit the candidate the render judge accepts with the highest render confidence. Ties go to the lower method number.
- A AND R: among candidates both judges accept, commit the highest Sol confidence, then the highest render confidence, then the lower method number.

Scoring against GT v4 strict. A commit is correct if GT is C, wrong if W. No commit is CONFIRM. G0 is the count of correct commits (zero clicks correct). Scores are on 18 requests. Sensitivity: the same counts with 2cd43775 scored under the all-C auto-save reading.

Gate (proposal, fixed here). The render key earns a second-key place only if both bases pass.
- Basis 18 (all requests): A AND R removes at least 2 of A's 3 wrong commits, and keeps at least 12 of A's 13 correct zero-click commits. "Removes" means the request has no wrong commit after A AND R (CONFIRM or correct).
- Basis 17 (2cd43775 excluded from all three policies, because no render exists for its candidates): A has 2 wrong commits (de97694c, 476b080a). A AND R must remove both, and keep at least 12 of A's 13 correct commits.

A's 3 wrong commits are 083c86e1 (2cd43775), de97694c (d53ff5ee, method 2) and 476b080a (ecc2413d, method 1). A's 13 correct commits are on 13 requests.

Reporting rule. Basis 18 credits the render with 083c86e1 by construction (section 0), so basis 17 is the test of the render itself.

## 8. Costs and measures (not gates)

- Render time per state: wall clock of `render_state` (profile, cold start, conversion, rasterising and PNG checks). Median, 90th percentile and maximum over the 80 states, and the largest state named.
- PNGs per state, PNGs per batch, the largest PNG in bytes, pages kept, re-encoded and tiled (Amendment 3 counts), and the number of states judged alone.
- The render judge's reject rate on the 69 office correct states, with the exact 95% interval; Sol's reject rate on the same states, for comparison.
- Judge tokens per batch, if the provider reports them.

## 9. Limits stated in advance

- Same model (Sol) as the text judge, with pictures in place of text. One judge run. Judge variance is measured only by Exp 8's text rerun (4 of 84 verdicts flipped).
- LibreOffice is the only renderer. Word is not checked.
- The ecc2413d ground truth (GT v4 ruling 1c) is set by a LibreOffice render. Agreement on that task is therefore not independent of the GT.
- The render cannot show a profile setting (2cd43775) or a cursor position (66399b0d). Neither is renderable.
- Spreadsheets render as print output. Hidden rows and cells outside the print range do not appear.
- 18 requests and 80 rendered states. The sample is small, and the results describe these states.
- A reject on small text is a reject the render made at 150 dpi.

## 10. Run order

1. Lock commit (this file, the scripts and the prompt). Hash sent to the orchestrator.
2. `exp10_run.py`: renders the 80 office attempts, writes packets, batches, stats and the input manifest, and runs the leak check.
3. `exp10_rowcheck.py`: table row check. Addendum A is added to this file.
4. Orphan branch `exp10-packets` with only `packets/` and `batches/`. Pushed, hash sent to the orchestrator.
5. The orchestrator runs the judge batches and saves each verdict file verbatim.
6. Score with `exp10_score.py`, committed before scoring. Reveal SALT. Publish `exp10-results.md`.

Nothing in this file depends on any render or judge output, except Addendum A, which is written before any packet is judged.

## 11. Lock contents

- `exp10-preregistration.md` (this file)
- `render_lib.py`: copied from commit 4bc82d0 of `research/exp9-render/render_lib.py`, unchanged, sha256 `2d9ad5d14ab3b9b3dfe2e1d0982e65606d980faf8d3039cec437c4124f554022`
- `exp10_run.py`: sha256 `4f653e2b05653af4558f820d947641db18d5ed77c015087e315a60f411cae195`
- `exp10_rowcheck.py`: sha256 `7002fdb752352c7d9a7673ed82c9cce5bf45d8d3a8553d056563dbe10493ff10`
- `sol_prompt_render.txt`: sha256 `242c0e168f3ee510bfd41fa7294a8894cb7631e34067bcd25845ab3247939d17`
- Salt commitment: `a3bdd873ee37ff981732b87d04d0a7fd04b6f2a18a04d705fc927744789ec07d`

## Addendum A (table row check)

To be added after the render and before any packet is published.
