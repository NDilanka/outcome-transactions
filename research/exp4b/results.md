# Experiment 4b: Blind Outcome Specifications vs. Official OSWorld Evaluators

## 1. Headline Summary

Across all **66 OSWorld tasks** spanning 10 domains, outcome specifications written blindly from the user instruction and VM starting-state setup (`generated_specs.yaml`) were judged against the official OSWorld evaluator configurations (`official_evaluators.json`) and their underlying Python metric implementations (`desktop_env/evaluators/metrics/` and `getters/`), without crediting `fuzzy:` prose predicates:

- **Equivalent (`20 / 66`, `30.3%`)**: Accept and reject essentially the same task outcomes on the target artifact.
- **Stricter (`30 / 66`, `45.5%`)**: Check everything the official evaluator checks plus additional target properties, behavioral probes, or anti-cheating invariants.
  - **Reasonably stricter (`24 / 30` stricter tasks, `36.4%` of all tasks)**: Close genuine holes in the official evaluators without rejecting valid solutions.
  - **Over-strict / risk of false rejection (`6 / 30` stricter tasks, `9.1%` of all tasks)**: Include at least one overly tight threshold or assumption that could reject a valid solution.
- **Looser (`7 / 66`, `10.6%`)**: Miss a requirement enforced by the official evaluator (would accept some states the official evaluator rejects).
- **Different (`6 / 66`, `9.1%`)**: Check a mutually incompatible or differently conceived interpretation of the prompt. In **5 of the 6 cases**, the blind specification is more faithful to the user instruction than the official evaluator; in **1 of 6** (`6054afcb`), the official evaluator is more faithful.
- **Unverifiable (`3 / 66`, `4.5%`)**: Cannot be evaluated deterministically by code as written because the core task outcome depends on inspecting an unprovided runtime file and is delegated to `fuzzy:` prose or an unimplementable OCR/semantic reader.

Combined, **50 / 66 (`75.8%`)** of the blind specifications are either **equivalent (`30.3%`)** or **stricter (`45.5%`)** than the official benchmark evaluators, and **44 / 66 (`66.7%`)** are equivalent or *reasonably* stricter without false-rejection risk.

Additionally:
- **`official_uses_reference_file` (`25 / 66`, `37.9%`)**: Over a third of official evaluators rely on comparing against a gold reference file (`.xlsx`, `.pptx`, `.docx`, `.odt`, `.pdf`, `.png`, `.txt`, `.json`) downloaded at evaluation time. Despite having no access to these reference files, the blind specs achieved `equivalent` (`9/25`) or `stricter` (`8/25`) on **17 / 25 (`68.0%`)** of reference-file tasks by expressing outcomes relationally against `before(...)`. However, all 3 `unverifiable` specs and 3 of the 7 `looser` specs occurred on reference-file tasks where the gold output depended on hidden input file contents.
- **`footprint_adds_value` (`56 / 66`, `84.8%`)**: In 56 of 66 tasks, the blind specification's `footprint:` (or explicit non-target preservation predicates) catches collateral damage that the official evaluator completely ignores (e.g., deleting document body text when inserting a table, moving instead of copying files, stripping document formatting during case conversion, or breaking `chmod` directory traversal bits).

---

## 2. Counts and Shares per Verdict (Overall and by Domain)

### Overall Verdict Breakdown

| Verdict | Count | Share (%) | Notes |
| :--- | ---: | ---: | :--- |
| `stricter` | 30 | 45.5% | 24 reasonable (`36.4%`), 6 potentially over-strict (`9.1%`) |
| `equivalent` | 20 | 30.3% | Same target outcome acceptance; 16/20 add valuable footprint checks |
| `looser` | 7 | 10.6% | 2 actually fairer to underspecified prompts (`f8cfa149`, `b52b40a5`); 5 genuine omissions |
| `different` | 6 | 9.1% | Blind spec more faithful in 5/6; official more faithful in 1/6 (`6054afcb`) |
| `unverifiable` | 3 | 4.5% | All 3 in `multi_apps` where task inputs (`calculator.py`, `tilearray.png`, receipt images) were unseen |
| **Total** | **66** | **100.0%** | `official_uses_reference_file`: 25 (`37.9%`); `footprint_adds_value`: 56 (`84.8%`) |

### Per-Domain Verdict Breakdown

| Domain | Tasks | `equivalent` | `stricter` | `looser` | `different` | `unverifiable` | `official_uses_reference_file` | `footprint_adds_value` |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `chrome` | 6 | 3 (50.0%) | 2 (33.3%) | 0 (0.0%) | 1 (16.7%) | 0 (0.0%) | 0 / 6 (0.0%) | 6 / 6 (100.0%) |
| `gimp` | 6 | 1 (16.7%) | 2 (33.3%) | 2 (33.3%) | 1 (16.7%) | 0 (0.0%) | 0 / 6 (0.0%) | 5 / 6 (83.3%) |
| `libreoffice_calc` | 6 | 3 (50.0%) | 2 (33.3%) | 0 (0.0%) | 1 (16.7%) | 0 (0.0%) | 6 / 6 (100.0%) | 2 / 6 (33.3%) |
| `libreoffice_impress` | 6 | 2 (33.3%) | 3 (50.0%) | 1 (16.7%) | 0 (0.0%) | 0 (0.0%) | 4 / 6 (66.7%) | 3 / 6 (50.0%) |
| `libreoffice_writer` | 6 | 1 (16.7%) | 4 (66.7%) | 1 (16.7%) | 0 (0.0%) | 0 (0.0%) | 5 / 6 (83.3%) | 6 / 6 (100.0%) |
| `multi_apps` | 12 | 1 (8.3%) | 6 (50.0%) | 2 (16.7%) | 0 (0.0%) | 3 (25.0%) | 6 / 12 (50.0%) | 10 / 12 (83.3%) |
| `os` | 6 | 2 (33.3%) | 3 (50.0%) | 0 (0.0%) | 1 (16.7%) | 0 (0.0%) | 0 / 6 (0.0%) | 6 / 6 (100.0%) |
| `thunderbird` | 6 | 2 (33.3%) | 3 (50.0%) | 1 (16.7%) | 0 (0.0%) | 0 (0.0%) | 0 / 6 (0.0%) | 6 / 6 (100.0%) |
| `vlc` | 6 | 3 (50.0%) | 3 (50.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 2 / 6 (33.3%) | 6 / 6 (100.0%) |
| `vs_code` | 6 | 2 (33.3%) | 2 (33.3%) | 0 (0.0%) | 2 (33.3%) | 0 (0.0%) | 2 / 6 (33.3%) | 6 / 6 (100.0%) |
| **Total** | **66** | **20 (30.3%)** | **30 (45.5%)** | **7 (10.6%)** | **6 (9.1%)** | **3 (4.5%)** | **25 / 66 (37.9%)** | **56 / 66 (84.8%)** |

---

## 3. Most Common Failure Patterns of the Blind Specifications

When the blind specifications fail—either by being `unverifiable`, `looser`, over-strict (`stricter` with false-rejection risk), or misinterpreting the task (`different` where official is more faithful)—their failures cluster into four recurring patterns:

### Pattern 1: Delegating Core Verification of Unseen Runtime Artifacts to `fuzzy:` Prose or Magic Readers (4 tasks: `f918266a`, `d68204bf`, `8e116af7`, `554785e9`)
When the task outcome depends on semantic, perceptual, or code-level properties of files downloaded during VM setup (which the blind spec writer cannot see), the spec writer sometimes pushes the real verification burden into `fuzzy:` prose or into an oracle-like reader that presupposes solving the AI task itself:
- **Unseen code completion (`f918266a`, `unverifiable`)**: Unable to inspect `calculator.py` inside `calculator.zip`, the spec checks in `must:` only that `calculator.py` parses, lacks obvious `TODO`/`pass` markers, exits with `0`, and writes non-empty stdout to `log.txt`. The actual correctness of the implemented functions and `log.txt` output is relegated to `fuzzy:`.
- **Unseen perceptual ordering (`d68204bf`, `unverifiable`)**: Asked to split `tilearray.png` vertically into 3 sections and reorder them "from warmest to coolest", `must:` only checks that `rearranged.png` is *one of the 6 horizontal permutations* of the 3 slices, leaving "ordered from warmest to coolest overall color temperature" in `fuzzy:` and using a vague `terminal.command_history.executed_commands.any_Matches(kind='image_vertical_split_and_horizontal_reorder', ...)` predicate.
- **Unseen OCR + category inference (`8e116af7`, `unverifiable`)**: Asked to transcribe 5 receipt images (`receipt-1.jpg`..`receipt-5.png`) into `my_bookkeeping.xlsx`, `must:` invokes a hypothetical `receipts('/home/user/Desktop/receipt-*.{jpg,png}').extracted_transactions.as_rows(...)` reader and uses `fuzzy:` to require accurate OCR and inferred expense categories.
- **Image structural preservation pushed to `fuzzy:` (`554785e9`, `looser`)**: For photo vibrancy enhancement, the official evaluator checks both mean HSV saturation increase *and* Hue/Value channel `SSIM >= 0.9`. The blind spec checks `mean_hsv_saturation > before` in `must:`, but places "while preserving structural content, natural edges, and the subject's appearance" into `fuzzy:`, making its code-checkable `must:` accept any high-saturation image of matching size.

### Pattern 2: Over-Specifying Thresholds, Secondary Settings, or Geometric Anchors That Reject Valid Solutions (6 tasks: `f4aec372`, `2cd43775`, `7b6c7e24`, `cabb3bae`, `57667013`, `3ce045a0`)
Without seeing the official evaluator's tolerances or how applications serialize state, the blind spec sometimes invents overly tight constraints:
- **Zero-margin geometric tolerance and anchor mismatch (`f4aec372`, `gimp`)**: Require centering the yellow triangle to `visible_bounds.center_xy within(1 pixel)` of the canvas center. The official evaluator uses the polygon contour centroid (`cv2.moments`) with a **5% canvas dimension tolerance** (~40–96 px) to accommodate manual mouse dragging in GIMP. A 1px tolerance on bounding-box center rejects valid manual drag placements.
- **Requiring an unrequested secondary checkbox (`2cd43775`, `libreoffice_impress`)**: For "Enable auto-save every 3min", the blind spec requires both `recovery.auto_save.enabled == true` (`AutoSaveTimeIntervall == 3`) *and* `save_original_document_automatically.value_if_supported == true` (`UserAutoSave`). In LibreOffice, `UserAutoSave` ("Automatically save the document too") is a separate checkbox from AutoRecovery that the official evaluator does not expect.
- **Expanding scope beyond standard user action (`7b6c7e24`, `chrome`)**: For "clean up the tracking things stored by Amazon", the official evaluator only checks that `.amazon.com` rows are deleted from Chrome's `Cookies` SQLite table. The blind spec requires zero cookies across all Amazon domains *plus* zero `localStorage`/`IndexedDB`, `sessionStorage`, `service_workers`, and `CacheStorage` for Amazon origins.
- **Assuming e-commerce search results are strictly monotonic without sponsored tiles (`cabb3bae`, `chrome`)**: Requires `results.displayed_current_prices ordered_by(ascending)` in addition to `sort.effective_order == 'price_ascending'`, which can fail on live retail sites that inject sponsored product cards at the top of sorted results.
- **Checking unrendered empty-paragraph properties (`57667013`, `libreoffice_impress`)**: Requires empty paragraphs on Slide 5 to also have default font color `#FFFF00`, which can fail when an agent selects and recolors all visible text runs without altering trailing empty paragraph defaults.
- **Fixing a specific accessibility toggle threshold (`3ce045a0`, `os`)**: Requires `text-scaling-factor >= 1.25` (Ubuntu's "Large Text" toggle), which rejects valid manual scaling factors like `1.15` or `1.20` accepted by the official evaluator.

### Pattern 3: Missing Application-Specific Config Dependencies or Structural Encodings (4 tasks: `08c73485`, `06ca5602`, `f23acfd2`, `88fe4b2d`)
- **Hidden app-specific config coupling (`08c73485`, `thunderbird`, `looser`)**: To apply incoming message filters to IMAP subfolders in Thunderbird, setting `mail.server.default.applyIncomingFilters = true` alone is insufficient unless `mail.imap.use_status_for_biff = false` is also set. The official evaluator checks both; the blind spec only checks `applyIncomingFilters`.
- **Omitting pixel-similarity invariant after color-mode conversion (`06ca5602`, `gimp`, `looser`)**: When converting `computer.png` to indexed palette mode, the blind spec checks `base_color_mode == 'indexed'`, `0 < palette.color_count <= 256`, and `canvas.size == before`, forgetting to require `pixels similarity>=0.90 before(...)` (`SSIM >= 0.9` in the official checker).
- **Allowing alternative visual encodings where the official gold file requires one specific DOM/XML representation (`88fe4b2d`, `libreoffice_writer`; `f23acfd2`, `libreoffice_impress`)**: In `88fe4b2d`, the blind spec explicitly allows soft line breaks or paragraph spacing that render as one blank line between sentences, whereas `compare_docx_files(..., ignore_blanks=False)` requires empty paragraph elements (`""`). In `f23acfd2`, the blind spec accepts any visible bullet glyph and level, whereas `compare_pptx_files` requires the specific bullet characters and level `0` in the 4 gold files.

### Pattern 4: Hyper-Literal Disambiguation of Pragmatic Domain Instructions (1 task: `6054afcb`)
- **Cell-level text hiding vs. row hiding (`6054afcb`, `libreoffice_calc`, `different`)**: The prompt states: *"Notice the N/A entries in rows? They make the sheet look untidy. Please hide them in the table for now. Do not delete any cells and filter is not needed."* Because the prompt says "Do not delete any cells" and refers to "N/A entries", the blind spec requires making the `N/A` cell text invisible (e.g., via custom format `;;;` or matching font/background color) while explicitly forbidding hiding rows (`row_and_column_structure == before`). In spreadsheet practice, "in rows ... filter is not needed" means hiding the rows containing `N/A` via **Hide Rows** rather than AutoFilter, which is what the official gold file tests.

---

## 4. Cases Where the Blind Specification Is Arguably Better Than the Official Checker

A striking finding of this comparison is how frequently the official OSWorld evaluators are **under-specified, brittle, or broken**, and how often the blind specification is substantially more faithful to the task instruction. Key examples include:

### A. Official Checkers That Omit Core Requirements of the Prompt (Caught by `stricter` Blind Specs)
1. **`5bc63fb9` (`multi_apps` — Filter Gemini responses into `gemini_results.docx`, separate by blank line, and highlight `"Iliad"`)**:
   - **Official flaw**: Because `compare_highlighted_text` in `metrics/docs.py` was deprecated (`# Docx file saved in the ubuntu cannot use this function to compare highlight, don't know why, deprecated`), the official evaluator uses `compare_docx_files_and_ignore_new_lines`, which strips all blank paragraphs, collapses all whitespace, and **never checks whether `"Iliad"` is highlighted or whether paragraphs are separated by a blank line**.
   - **Blind spec advantage**: Checks paragraph text equality against Gemini's JSON responses, requires `empty_rendered_lines_between_consecutive_nonempty_paragraphs == 1`, and verifies that every case-sensitive match of `'Iliad'` (and no other text) is highlighted.
2. **`15c3b339` (`thunderbird` — Fill in email and password `"password"` in account setup and stay on page)**:
   - **Official flaw**: `check_accessibility_tree` searches for a UI node containing `"anonym-x2024@outlook.com"` and a node whose `name` contains `"password"`/`"Password"`. Because the password input widget itself is named `"Password"` in Thunderbird's accessibility tree (and masks typed text), **the official evaluator passes even if the agent never types a password at all**!
   - **Blind spec advantage**: Explicitly checks `fields.password.secret_value == 'password'`, `completed == false`, and `persisted_account_identities == before`.
3. **`26150609` (`multi_apps` — Tweak Snake game code so the snake can eat food)**:
   - **Official flaw**: `test.py` steps the snake toward the food and returns `True` at the exact frame `snake.positions[0] == food.position`. It only tests grid coordinate alignment and **never checks whether the food is eaten, whether the snake grows, or whether new food spawns**.
   - **Blind spec advantage**: Tests `food_consumption_events == 1`, `snake_length_delta == 1`, and `replacement_food_on_grid_and_not_on_snake == true`.
4. **`66399b0d` & `936321ce` (`libreoffice_writer` — Insert 7x5 table at cursor; convert comma-separated text to table)**:
   - **Official flaw**: `compare_docx_tables` only inspects `doc.tables`. In `66399b0d`, an agent can delete the entire document text and insert a 5x7 table anywhere and still score `1.0`. In `936321ce`, an agent can leave the un-converted comma-separated lines duplicated in the document body and still score `1.0`.
   - **Blind spec advantage**: Verifies cursor-anchor placement, removal of the original comma-delimited text block, and full preservation of surrounding document prose.
5. **`ecc2413d` (`libreoffice_writer` — Insert a blank page right after the current page)**:
   - **Official flaw**: `contains_page_break` only checks that the total count of `<w:br w:type="page"/>` XML tags anywhere in the document equals `5`—ignoring where the break was inserted, whether it produced a blank page, or whether document content was deleted.
   - **Blind spec advantage**: Verifies `rendered_page_count == before + 1`, that page `k + 1` has zero visible body content, and that pages `1..k` and `k+2..end` match the original pages.
6. **`0326d92d` (`libreoffice_calc` — `SalesRep.xlsx` Total bar chart + Growth line chart omitting Jan)**:
   - **Official flaw**: `compare_table` passes `chart_props: ["type", "title"]`, which checks **only** chart type and title—never checking what cells, series, or x-axis categories the charts plot (ignoring the prompt's explicit instruction that *"Jan should be omitted in the chart as well"*).
   - **Blind spec advantage**: Verifies both charts' plotted `series_values` and `categories` (`['Jan'..'Jun']` for `Total` and `['Feb'..'Jun']` for `Growth`).
7. **`69acbb55` (`multi_apps` — Configure environment for `instructor-embedding` in `/home/user`)**:
   - **Official flaw**: Only runs `python -c "from InstructorEmbedding import INSTRUCTOR;"` in the default shell without checking whether `/home/user/instructor-embedding` was even cloned.
   - **Blind spec advantage**: Checks both the git repository clone at `/home/user/instructor-embedding` and the Python import probe.
8. **`23393935` (`os` — Recursively copy `.jpg` files from `photos` to `cpjpg`)**:
   - **Official flaw**: `check_moved_jpgs` only checks that the 4 filenames exist in `cpjpg` via `os.listdir`—accepting empty `touch` files or `mv` commands that delete the originals from `photos`.
   - **Blind spec advantage**: Verifies SHA-256 content hashes and requires `/home/user/Desktop/photos` to remain completely untouched.
9. **`a5bbbcd5` & `386dbd0e` (`vlc` — Minimal interface in window mode; global play/pause shortcut while PDF reader focused)**:
   - **Official flaw**: Only check `qt-minimal-view=1` or `global-key-play-pause != ""` in `vlcrc`, ignoring whether VLC is in windowed vs. fullscreen mode (`a5bbbcd5`) or whether the chosen global hotkey conflicts with the desktop environment (`386dbd0e`).
   - **Blind spec advantage**: Checks `window_mode == 'windowed'` and uses behavioral probes (`application_probe`, `hotkey_probe`) to verify the requirement end-to-end.
10. **`53ad5833` (`vs_code` — Open `/home/user/project` in VS Code)**:
    - **Official flaw**: Uses `compare_config(..., containment_ok=True)` to check only whether the substring `"project"` appears in `/home/user/OpenProject.txt` (matching any folder whose name contains `"project"`).
    - **Blind spec advantage**: Verifies canonical workspace root path equality (`['/home/user/project']`) and file preservation.

### B. Official Checkers That Are Brittly Over-Fit to One Syntactic Representation (`different` or `looser` Blind Specs)
11. **`a96b564e` (`chrome` — FlightAware Discussions > General > topic with most replies)**:
    - Official hardcodes `https://discussions.flightaware.com/t/the-banter-thread/4412`, which breaks if another topic overtakes it on the live web or if Discourse appends a post-scroll suffix (`/4412/12`). The blind spec queries the live category maximum and canonicalizes Discourse topic URLs.
12. **`ea98c5d7` & `6ed0a554` (`vs_code` — Remove `ctrl+f` for Explorer Tree view Find; add `/home/user/data1` and `/home/user/data2` to workspace)**:
    - Official uses literal Python dict/list equality on `keybindings.json` (requiring `when: "listFocus && listSupportsFind"` verbatim) and `project.code-workspace` (requiring relative paths `[{"path": "project"}, {"path": "data1"}, {"path": "data2"}]` in exact order, even though the prompt specifies absolute paths `/home/user/data1` and `/home/user/data2`). The blind specs check effective keybinding resolution in Explorer focus and canonical path set equality.
13. **`5812b315` (`os` — Create SSH user `charles` who is only allowed to access `/home/test1`)**:
    - Official only checks that `charles`'s home directory in `/etc/passwd` is `/home/test1` and is writable by `charles`—which provides zero access confinement over SSH. The blind spec checks actual OpenSSH `ChrootDirectory /home/test1` confinement.
14. **`f8cfa149` & `b52b40a5` (`multi_apps` — Search Cell B6 in Chrome; merge PDF attachments from "Paper Recommendation")**:
    - Official requires Google Search (`google.com/search?q=nereida.*`) when the prompt only says *"search it in Chrome"*, and requires one arbitrary attachment concatenation order in `attachment_full_gold.pdf` when the prompt specifies no order. The blind specs accept any search engine and any whole-document attachment permutation.

---

## 5. Limitations of This Comparison

1. **Assumed Semantic Reader Layer vs. Executed Python Code**:
   The generated specifications in `generated_specs.yaml` are declarative assertions written against a conceptual semantic reader API (`before(...)`, `document(...)`, `spreadsheet(...)`, `gimp.active_image...`, `vlc.hotkey_probe(...)`). While 63 of the 66 specs express deterministic, code-checkable properties (once `fuzzy:` clauses are discounted), evaluating them in production requires implementing those domain readers reliably. By contrast, the official evaluators are already concrete Python functions, and many of their bugs stem from real-world library limitations (e.g., `python-docx` / `odfpy` highlight parsing quirks in `5bc63fb9`, or AT-SPI masking password values in `15c3b339`).
2. **Inability to Inspect Downloaded Setup Files Directly**:
   Because the blind spec writer only saw `starting_state_setup` URLs/commands and not the bytes inside downloaded files, and because this static review did not download external HuggingFace cache archives, comparison on reference-file tasks relies on the official evaluator code (`metrics/*.py`) and task setup structure (`blind_tasks.json`, `official_evaluators.json`). This also explains why all 3 `unverifiable` tasks occurred when task correctness was latent inside downloaded code or images (`calculator.zip`, `tilearray.png`, `receipt-*.jpg`).
3. **Strictness of `footprint:` Invariants Under Benign System Noise**:
   In 56 of 66 tasks (`84.8%`), the blind spec's `footprint:` adds valuable protection against collateral damage. However, if implemented as a naive byte-level diff rather than the spec's `.semantic_state` reader, background OS/browser noise (such as Chrome updating cache timestamps or LibreOffice touching recent-documents lists in `registrymodifications.xcu`) could cause false rejections unless the reader properly scopes `.semantic_state` to user-meaningful settings.
