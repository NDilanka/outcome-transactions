# Blind end-state test set

`research/exp6-blind-states/` contains offline end-state generators for 34 tasks from `research/exp5-grounded/batches/`. Each covered task defines 7 end states: 2 valid completions and 5 plausible wrong completions. The generators were written from the task instructions, starting snapshots, and inspection reports alone, without reading any outcome specifications, judge prompts, or benchmark evaluators.

## Directory layout

```
research/exp6-blind-states/
	README.md
	run_all.py
	<task_id>/
		states.py
		labels.json
```

Each `<task_id>/states.py` module defines 7 functions with the signature `def <state_name>(snapshot_dir, out_dir)`. Every function copies `snapshot_dir` to `out_dir` and edits the task files in `out_dir` to produce that end state.

Each `<task_id>/labels.json` file lists the 7 state functions for that task. Every entry has three fields:

- `state`: the function name in `states.py`.
- `label`: either `"correct"` or `"wrong"`.
- `why`: one sentence that ties the label to the task instruction.

## Materialize all end states

Run `run_all.py` with the starting snapshots directory and an output directory:

```powershell
py research/exp6-blind-states/run_all.py --snapshots-dir research/exp5-grounded/snapshots --out-dir research/exp6-blind-states/materialized --verify
```

`run_all.py` writes each state to `<out_dir>/<task_id>/<state_name>/`. When `--verify` is passed, `run_all.py` checks that each task has 5 wrong states and 2 correct states, that every materialized tree differs from its starting snapshot, and that all 7 states for a task produce distinct file trees.

## Covered tasks

The 34 covered tasks produce 238 materialized end states across 10 domains:

- `libreoffice_calc`: `0326d92d-d218-48a8-9ca1-981cd6d064c7`, `1273e544-688f-496b-8d89-3e0f40aa0606`, `42e0a640-4f19-4b28-973d-729602b5a4a7`, `51719eea-10bc-4246-a428-ac7c433dd4b3`, `6054afcb-5bab-4702-90a0-b259b5d3217c`, `a9f325aa-8c05-4e4f-8341-9e4358565f4f`
- `libreoffice_impress`: `21760ecb-8f62-40d2-8d85-0cee5725cb72`, `550ce7e7-747b-495f-b122-acdc4d0b8e54`, `57667013-ea97-417c-9dce-2713091e6e2a`, `7ae48c60-f143-4119-b659-15b8f485eb9a`, `f23acfd2-c485-4b7c-a1e7-d4303ddfe864`
- `libreoffice_writer`: `66399b0d-8fda-4618-95c4-bfc6191617e9`, `6a33f9b9-0a56-4844-9c3f-96ec3ffb3ba2`, `88fe4b2d-3040-4c70-9a70-546a47764b48`, `936321ce-5236-426a-9a20-e0e3c5dc536f`, `d53ff5ee-3b1a-431e-b2be-30ed2673079b`, `ecc2413d-8a48-416e-a3a2-d30106ca36cb`
- `gimp`: `06ca5602-62ca-47f6-ad4f-da151cde54cc`, `554785e9-4523-4e7a-b8e1-8016f565f56a`, `e2dd0213-26db-4349-abe5-d5667bfd725c`, `f4aec372-4fb0-4df5-a52b-79e0e2a5d6ce`
- `multi_apps`: `26150609-0da3-4a7d-8868-0faf9c5f01bb`, `5bc63fb9-276a-4439-a7c1-9dc76401737f`, `8e116af7-7db7-4e35-a68b-b0939c066c78`, `d68204bf-11c1-4b13-b48b-d303c73d4bf6`, `f918266a-b3e0-4914-865d-4faa564f1aef`
- `os`: `23393935-50c7-4a86-aeea-2b78fd089c5c`
- `thunderbird`: `08c73485-7c6d-4681-999d-919f5c32dcfa`, `9b7bc335-06b5-4cd3-9119-1a649c478509`, `dd84e895-72fd-4023-a336-97689ded257c`, `f201fbc3-44e6-46fc-bcaa-432f9815454c`
- `vlc`: `386dbd0e-0241-4a0a-b6a2-6704fba26b1c`, `fba2c100-79e8-42df-ae74-b592418d54f4`
- `vs_code`: `6ed0a554-cbee-4b44-84ea-fd6c042f4fe1`

## Skipped tasks

Of the 60 tasks in `research/exp5-grounded/batches/`, 26 tasks are skipped.

### Tasks with starting snapshots whose outcomes require live runtime or external state

10 tasks have downloaded files in `research/exp5-grounded/snapshots/`, but their outcomes cannot be built as offline file trees:

- `15c3b339-88f7-4a86-ab16-e71c58dcb01e`: The instruction enters an email address and password in the Thunderbird account setup dialog and stays on that dialog without submitting. The outcome lives in an open GUI window.
- `22a4636f-8179-4357-8e87-d1743ece1f81`: The instruction converts `Meeting-Agenda.docx` to `Meeting-Agenda.pdf` and uploads it to a Google Drive folder named `meetings`. The upload destination is remote cloud state.
- `2b9493d7-49b8-493a-a71b-56cd1f4d6908`: The instruction force-quits a frozen LibreOffice Writer process that holds `large_file.odt`. The outcome is OS process table state.
- `4d117223-a354-47fb-8b45-62ab1390a95f`: The instruction runs `setup.sh` and sets POSIX mode `0644` on regular files without touching directory permissions. The snapshot holds only `setup.sh`, and POSIX mode bits do not round-trip on Windows NTFS.
- `53ad5833-3455-407b-bbc6-45b4c79ab8fb`: The instruction opens `/home/user/project` in a running VS Code window. The snapshot directory is empty and the outcome is live editor window state.
- `a74b607e-6bb5-4ea8-8a7c-5d97c7bbcd2a`: The instruction installs a local Chrome extension from Desktop into a running Chrome instance. The snapshot contains only the unpacked extension on Desktop, not a Chrome user profile directory.
- `b52b40a5-ad70-4c53-b5b0-5650a8387052`: The instruction merges PDF email attachments into `attachment_full.pdf` and uploads the merged PDF to Google Drive. The upload destination is remote cloud state.
- `d38192b0-17dc-4e1d-99c3-786d0117de77`: The instruction attaches `~/aws-bill.pdf` to an open Thunderbird compose window and leaves the window open without sending or closing it. The outcome is in-memory GUI window state.
- `efcf0d81-0835-4880-b2fd-d866e8bc2294`: The instruction sets the desktop wallpaper from a playing VLC video. The outcome is desktop environment `gsettings` or live VLC window state outside the snapshot files.
- `f8cfa149-d1c1-4215-8dac-4a0932bad3c2`: The instruction copies a spreadsheet cell value and searches it in Chrome. The outcome is an open browser tab.

### Tasks without starting file snapshots

16 tasks have no starting files in `research/exp5-grounded/snapshots/` and act on live browsers, desktop settings, running processes, or empty workspaces:

- `02a2dc82-f926-4d7c-bf8a-7dd66ffe23f1`: Adds an Amazon item to a shopping cart in Chrome.
- `27702dca-320d-4293-9e42-2f2fb3cfa287`: Opens an accessibility menu in Chrome.
- `2a729127-247b-4d40-96fb-4fc793fb4bf6`: Pins a web page to the Chrome taskbar or bookmarks bar.
- `5e7cf373-239d-4c8a-ab02-d9f81dc7129f`: Looks up a bus schedule on a live website in Chrome.
- `95f9bbba-73f7-4c72-be8b-2eed2eb2c4f6`: Searches a flight status on a live website in Chrome.
- `9941fbbf-0fb5-4012-a847-c6b6ebfae23b`: Changes Chrome search engine settings in a live browser profile.
- `d2c8dfd6-7223-4ab5-b28f-5ef9ff9bfd82`: Clears browsing history or cookies in a live Chrome profile.
- `f52ff104-6ce6-42c2-b262-cb3fb4fb3db4`: Changes font size settings in a live Chrome profile.
- `09052f59-4fc1-4c9c-a2d8-c74f13bf7ff6`: Creates a GIMP canvas from scratch with no starting snapshot.
- `7b9f8f82-a370-482b-8242-054c5f80a2f3`: Exports a blank or newly drawn GIMP image with no starting snapshot.
- `71c992ca-0c6b-4d58-922f-4b02967120c2`: Changes GNOME desktop notification banners via `gsettings`.
- `94d93643-a988-464f-9d0d-3a6a9f2213b6`: Checks system disk or memory state in a terminal with no starting files.
- `b2be8bf2-0b44-4d34-b085-e76e1f2f179c`: Modifies system favorite apps in GNOME `dconf` or `gsettings`.
- `ce2f9119-0631-4287-b73e-970f1d7cf2c7`: Changes VLC interface preferences with no starting snapshot directory.
- `2c4d2f91-7840-4c93-b7c1-f022f11a9114`: Installs a VS Code extension in a live editor instance with no starting snapshot.
- `a41ef48b-2257-4c70-9c74-96cd0fb5b95b`: Changes VS Code color theme in a live editor instance with no starting snapshot.
