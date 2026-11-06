# Experiment 3: Where do OSWorld task outcomes live?

Date: 2026-11-06
Data: OSWorld `evaluation_examples/test_all.json` (368 Linux tasks), shallow clone of xlang-ai/OSWorld main.
Scripts: `osworld_tally.py`, `osworld_classify.py` in this folder.

## Question

Invention 3b (result transplant) commits a winning fork by copying changed result objects instead of replaying actions. What share of real computer-use tasks have outcomes stored in persistent, copyable state?

## Method

Each task's evaluator names the "result getter" that reads the outcome. Tasks were classified by getter type:

- **file_document**: outcome is a document or output file (`vm_file`, `cache_file`, cloud files, slide contents, directory listings).
- **file_settings**: outcome is persisted app or OS settings (VLC/GIMP/VS Code config, Chrome profile files, bookmarks, history, cookies, wallpaper, default apps).
- **command**: outcome read by a shell command; split by hand into persisted state (gsettings, files, installed packages, users, timezone, git) and live state (running processes, clipboard, audio volume, terminal output).
- **live_app_state**: outcome lives in a running app (browser active tab or URL, accessibility tree, VLC playback, screen size).
- **infeasible**: correct behavior is to report the task impossible.

## Results

| Category | Tasks | Share of feasible (342) |
|---|---|---|
| Document/output files | 230 | 67.3% |
| Persisted settings files | 32 | 9.4% |
| Command, persisted state | 34 | 9.9% |
| **Transplantable total** | **296** | **86.5%** |
| Live app state | 40 | 11.7% |
| Command, live state | 6 | 1.8% |
| **Replay required total** | **46** | **13.5%** |
| Infeasible (excluded) | 26 | n/a |

By domain, live state concentrates in Chrome (27 of 45 tasks: active tab, URL, page contents). LibreOffice Calc, Impress, and Writer are almost entirely file-based.

## Findings

1. **86.5% of feasible tasks have outcomes in persistent state**, so result transplant works for them without deterministic replay.
2. **The remaining 13.5% are mostly browser navigation outcomes** (the right page is open). Their commit is a cheap semantic action such as opening a URL, not a long replay.
3. **New problem found: the open-document problem.** In about 132 of 230 document tasks (heuristic match on the evaluator pressing Ctrl+S), the result exists only in the app's memory until saved. Transplant therefore needs (a) a save inside the fork and (b) the real app to reload the transplanted file. Otherwise the real app still shows the old document and could overwrite the result on its next save.
4. **New problem found: outcome checking is hand-written per task.** OSWorld uses 121 distinct evaluator functions across 368 tasks. Automatic outcome checking from a natural-language request is unsolved and is now the most important open research question for the engine.
5. **Some outcomes include the method.** Several tasks check that the user's terminal history shows a specific command (for example, converting files with `soffice --convert-to`). Transplanting only the result file would fail those checks; the history file must be transplanted too, or the task treated as replay-required.

## Caveats

- OSWorld is Linux-only in this set and skewed toward office documents. Real-world task mixes, especially browser-heavy ones, will have more live state. A Windows set (`examples_windows`: Excel, Word, PowerPoint, multi-app) exists and should be checked next.
- The Ctrl+S count is a regex heuristic over evaluator post-configuration, not a manual audit.
- Classification of the 40 command tasks was done by reading each command once.
