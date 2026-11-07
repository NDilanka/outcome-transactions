"""Create the Exp 8 attempt folders: one per (task, method, condition).

Each attempt folder under RUN/<code>/ holds:
  TASK.md   the only instructions the agent under test reads (request text, UI state, method hint, rules)
  input/    read-only copy of the starting file (or LibreOffice profile folder)
  work/     the only folder the agent writes to (solve.py, scratch/, DONE.txt)

The code is random, so folder names do not reveal the task. The mapping to task, method and
condition is written to PRIV/map.json, outside the repository, and is not read until ground truth is recorded.
"""
import glob, hashlib, json, os, secrets, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SNAP = os.path.join(REPO, "research", "exp5-grounded", "snapshots")
RUN = "/home/factory-user/exp8/run"
PRIV = "/home/factory-user/exp8/private"
VENV_PY = "/home/factory-user/venvs/exp8/bin/python"
SYS_PY = "/usr/bin/python3"
LIBS_VENV = "python-docx, openpyxl, python-pptx, odfpy, lxml, pandas, pyyaml"
LIBS_SYS = "uno (LibreOffice bridge), lxml, odf"

# short id, kind, file name (None for the profile task), UI-context key
TASKS = [
    ("0326d92d", "xlsx", "SalesRep.xlsx", None),
    ("1273e544", "xlsx", "NetIncome.xlsx", None),
    ("42e0a640", "xlsx", "NetIncome.xlsx", None),
    ("51719eea", "xlsx", "BoomerangSales.xlsx", None),
    ("6054afcb", "xlsx", "Date_Budget_Variance_HideNA.xlsx", None),
    ("a9f325aa", "xlsx", "Movie_title_garbage_clean.xlsx", None),
    ("21760ecb", "pptx", "Ch4 Video Effect.pptx", "21760ecb"),
    ("2cd43775", "profile", None, None),
    ("550ce7e7", "pptx", "New_Club_Spring_2018_Training.pptx", "550ce7e7"),
    ("57667013", "pptx", "1_2.pptx", None),
    ("7ae48c60", "pptx", "30_1.pptx", None),
    ("f23acfd2", "pptx", "69_4.pptx", "f23acfd2"),
    ("66399b0d", "docx", "Table_Of_Work_Effort_Instructions.docx", "66399b0d"),
    ("6a33f9b9", "odt", "sample-recruitment-phone-script.odt", None),
    ("88fe4b2d", "docx", "CCCH9003_Tutorial_guidelines.docx", None),
    ("936321ce", "docx", "Graphemes_Sound_Letter_Patterns.docx", None),
    ("d53ff5ee", "docx", "presentation_instruction_2023_Feb.docx", None),
    ("ecc2413d", "docx", "Sample_Statutory_Declaration.docx", "ecc2413d"),
]

# Live UI state, derived from each task's setup steps (research/exp8-direct/ui_probe.py) and stated as facts.
UI_BLOCKS = {
    "66399b0d": "- LibreOffice Writer has this document open.\n"
                "- The text cursor is in the empty last paragraph of the document, below the table titled \"TABLE OF WORK EFFORT\". The table is above the cursor.\n"
                "- Nothing is selected.",
    "550ce7e7": "- LibreOffice Impress has this presentation open in Normal view.\n"
                "- Slide 5 of 7 is the active slide (selected in the slide panel).\n"
                "- Nothing is selected on the slide.",
    "21760ecb": "- LibreOffice Impress has this presentation open in Normal view.\n"
                "- Slide 1 of 24 is the active slide.\n"
                "- Nothing is selected on the slide.",
    "f23acfd2": "- LibreOffice Impress has this presentation open in Normal view.\n"
                "- Slide 1 of 1 is the active slide.\n"
                "- Nothing is selected on the slide.",
    "ecc2413d": "- LibreOffice Writer has this document open.\n"
                "- The text cursor is at the start of the document (page 1).\n"
                "- Nothing is selected.",
}

# Method hints. Attempt m (1..4) of each kind gets METHODS[kind][m-1].
DOC_METHODS = [
    ("A: high-level library", "Use the standard high-level Python library for this file type. Do not use LibreOffice.", "venv"),
    ("B: second library", "Use a different route from the usual high-level library: pandas with the openpyxl engine for .xlsx; for .docx, .pptx and .odt, unzip with zipfile and edit the XML parts with lxml. Do not use python-docx, openpyxl, python-pptx or odfpy. Do not use LibreOffice.", "venv"),
    ("C: headless LibreOffice", "Drive headless LibreOffice through the UNO bridge and save the document in its original format. Start your own LibreOffice for the run with a unique -env:UserInstallation folder and a named pipe (--accept=\"pipe,name=<unique>;urp;\"); do not use a TCP socket, because the run has no network. Close the document and stop that LibreOffice before the program exits.", "sys"),
    ("D: minimal XML edit", "Make the smallest possible change: unzip the file, change only the XML text that the request needs, leave every other part byte-identical, and rezip with the same part order. Do not parse and rewrite whole parts unless needed. Do not use LibreOffice.", "venv"),
]
PROFILE_METHODS = [
    ("A: lxml", "Edit the profile's registrymodifications.xcu with lxml. Do not use LibreOffice.", "venv"),
    ("B: ElementTree", "Edit the profile's registrymodifications.xcu with the standard library xml.etree.ElementTree. Do not use LibreOffice.", "venv"),
    ("C: headless LibreOffice", "Change the setting through LibreOffice's configuration API via the UNO bridge, running headless with your own unique -env:UserInstallation folder that is a copy of the profile, then make sure the change is written to the profile's registrymodifications.xcu. Use a named pipe, not TCP. Stop LibreOffice before the program exits.", "sys"),
    ("D: minimal text edit", "Make the smallest possible change to registrymodifications.xcu as plain text, leaving the rest of the file byte-identical. Do not use LibreOffice.", "venv"),
]

TASK_MD = """# Task

A user sent this request about a file on their computer:

> {request}
{ui}
## Output

Write one Python 3 program at `{work}/solve.py`. The harness runs it on a fresh copy of the user's file, as:

    {interp} {work}/solve.py {target}

`{target}` is the path of that copy. {target_note} The program must change it in place so that the request is carried out, and nothing else in it changes. The run has no network and no display.

## Files

- Starting copy, read-only, do not modify: `{input}`
- Your working folder, the only place you write: `{work}`
- Python for solve.py: `{interp}`. Libraries available there: {libs}

## Method for this attempt

{method_name}: {method}

## Rules

1. Test on copies you make under `{work}/scratch/`. Never change the starting copy.
2. solve.py must work from scratch on any fresh copy of the starting file, and must be self-contained.
3. Do not use a GUI, a display, or the network.
4. When finished, write `{work}/DONE.txt` in two to four sentences: what solve.py changes, and any part of the request you could not do or had to interpret.
5. Then stop.
"""

PROMPT = ("Read the file {md} and complete the task it describes, exactly as written. "
          "Work only inside the folders it names. Do not open any other file under /home/factory-user/exp8 "
          "or /home/factory-user/repos.")


def snap_dir(short):
    hits = glob.glob(os.path.join(SNAP, short + "*"))
    assert len(hits) == 1, (short, hits)
    return hits[0]


def snap_file(short, name):
    hits = glob.glob(os.path.join(snap_dir(short), "**", name), recursive=True)
    assert len(hits) == 1, (short, name, hits)
    return hits[0]


def full_id(short):
    ids = [t["id"] for t in json.load(open(os.path.join(REPO, "research", "exp4b", "blind_tasks.json")))]
    hits = [i for i in ids if i.startswith(short)]
    assert len(hits) == 1, (short, hits)
    return hits[0]


def make_profile(dst):
    """Create a fresh LibreOffice user profile for the settings-only task (2cd43775)."""
    tmp = "/tmp/exp8_profile_make"
    shutil.rmtree(tmp, ignore_errors=True)
    subprocess.run(["soffice", f"-env:UserInstallation=file://{tmp}", "--headless", "--terminate_after_init"],
                   check=True, timeout=180, capture_output=True)
    shutil.copytree(os.path.join(tmp, "user"), dst)
    assert os.path.exists(os.path.join(dst, "registrymodifications.xcu")), "profile has no registrymodifications.xcu"


def readonly_tree(path):
    for root, dirs, files in os.walk(path):
        for f in files:
            os.chmod(os.path.join(root, f), 0o444)
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o555)
    os.chmod(path, 0o555)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_hash(path):
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(path)):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f)
            h.update(os.path.relpath(p, path).encode())
            h.update(sha256(p).encode())
    return h.hexdigest()


def build(short, kind, fname, ui_key, method_idx, condition, requests, code):
    method_table = PROFILE_METHODS if kind == "profile" else DOC_METHODS
    method_name, method, interp_kind = method_table[method_idx - 1]
    interp = VENV_PY if interp_kind == "venv" else SYS_PY
    libs = LIBS_VENV if interp_kind == "venv" else LIBS_SYS
    base = os.path.join(RUN, code)
    os.makedirs(os.path.join(base, "work"), exist_ok=True)
    inp = os.path.join(base, "input")
    if kind == "profile":
        os.makedirs(inp, exist_ok=True)
        make_profile(os.path.join(inp, "user"))
        src_hash = tree_hash(os.path.join(inp, "user"))
        target = os.path.join(base, "input", "user")
        target_note = ("For this task the target is a LibreOffice user profile folder, named `user`. "
                       "It is the folder that holds `registrymodifications.xcu`. The program changes the settings in that folder.")
        input_path = os.path.join(base, "input", "user")
        target_arg = "<path of the profile folder `user`>"
        target_name = "user"
    else:
        os.makedirs(inp, exist_ok=True)
        src = snap_file(short, fname)
        shutil.copy2(src, os.path.join(inp, fname))
        src_hash = sha256(os.path.join(inp, fname))
        input_path = os.path.join(inp, fname)
        target_arg = f"<path of the copy of {fname}>"
        target_note = f"It is a copy of the user's file, named `{fname}`."
        target_name = fname
    readonly_tree(inp)
    ui = ""
    if ui_key and condition == "ui":
        ui = "\n## Live UI state when the user sent the request\n\n" + UI_BLOCKS[ui_key] + "\n"
    md = os.path.join(base, "TASK.md")
    with open(md, "w") as f:
        f.write(TASK_MD.format(request=requests[short], ui=ui, work=os.path.join(base, "work"),
                               interp=interp, target=target_arg, target_note=target_note,
                               input=input_path, libs=libs, method_name=method_name, method=method))
    return {
        "code": code, "short": short, "full_id": full_id(short), "kind": kind, "file": target_name,
        "method_idx": method_idx, "method": method_name, "condition": condition,
        "interp": interp, "input_path": input_path, "input_hash": src_hash, "ui_block": bool(ui),
        "task_md": md, "work": os.path.join(base, "work"), "run_base": base,
    }


def main():
    tasks = {t["id"]: t for t in json.load(open(os.path.join(REPO, "research", "exp4b", "blind_tasks.json")))}
    requests = {}
    for short, *_ in TASKS:
        requests[short] = [v for k, v in tasks.items() if k.startswith(short)][0]["instruction"]
    os.makedirs(RUN, exist_ok=True)
    os.makedirs(PRIV, exist_ok=True)
    entries = []
    for short, kind, fname, ui_key in TASKS:
        conds = ["ui" if ui_key else "none"]
        if short in ("66399b0d", "550ce7e7", "21760ecb"):
            conds = ["ui", "noui"]  # primary with UI context, ablation without it
        for condition in conds:
            for m in range(1, 5):
                code = secrets.token_hex(4)
                while os.path.exists(os.path.join(RUN, code)):
                    code = secrets.token_hex(4)
                entries.append(build(short, kind, fname, ui_key, m, condition, requests, code))
    json.dump(entries, open(os.path.join(PRIV, "map.json"), "w"), indent=1)
    print(f"{len(entries)} attempts written; primary {sum(e['condition'] != 'noui' for e in entries)}, ablation {sum(e['condition'] == 'noui' for e in entries)}")


if __name__ == "__main__":
    sys.exit(main())
