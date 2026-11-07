"""Materialise and check every exp7 blind end state.

    py run_all.py --snapshots-dir <dir> --out-dir <dir> [--verify] [--task <id>]

Layout written: <out-dir>/<task_id>/<state_name>/ holds a copy of the task's
snapshot with that end state applied.

--verify reports four failures per state: it does not exist, it is byte
identical to the untouched snapshot, its whole output tree is identical to
another state in the same task, or a produced document will not open.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import openpyxl  # noqa: E402
import docx  # noqa: E402
import pptx  # noqa: E402

DEFAULT_SNAPSHOTS = "D:/dev/interface-compiler/research/exp5-grounded/snapshots"


def load_states_module(task_dir):
    module_path = os.path.join(task_dir, "states.py")
    spec = importlib.util.spec_from_file_location("states_" + os.path.basename(task_dir).replace("-", "_"), module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def state_functions(module):
    names = [n for n in dir(module) if n.startswith("state_") and callable(getattr(module, n))]
    return [(n, getattr(module, n)) for n in sorted(names)]


def tree_hash(root):
    digest = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            digest.update(os.path.relpath(full, root).replace(os.sep, "/").encode("utf-8"))
            digest.update(b"\0")
            with open(full, "rb") as fh:
                for block in iter(lambda: fh.read(1 << 20), b""):
                    digest.update(block)
            digest.update(b"\0")
    return digest.hexdigest()


def open_error(full_path):
    ext = os.path.splitext(full_path)[1].lower()
    try:
        if ext == ".xlsx":
            wb = openpyxl.load_workbook(full_path)
            wb.close()
        elif ext == ".docx":
            docx.Document(full_path)
        elif ext == ".pptx":
            pptx.Presentation(full_path)
        elif ext == ".odt":
            import zipfile
            with zipfile.ZipFile(full_path) as z:
                bad = z.testzip()
                if bad:
                    return "corrupt member %s" % bad
                if z.read("mimetype").strip() != b"application/vnd.oasis.opendocument.text":
                    return "mimetype member is not an ODT type"
    except Exception as exc:  # noqa: BLE001 - the point is to report any open failure
        return "%s: %s" % (type(exc).__name__, exc)
    return None


def documents(root):
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if os.path.splitext(name)[1].lower() in (".xlsx", ".docx", ".pptx", ".odt"):
                out.append(os.path.join(dirpath, name))
    return out


def check_labels(task_dir, names, problems):
    label_path = os.path.join(task_dir, "labels.json")
    if not os.path.exists(label_path):
        problems.append("%s: labels.json missing" % os.path.basename(task_dir))
        return
    with open(label_path, encoding="utf-8") as fh:
        labels = json.load(fh)
    labelled = [entry["state"] for entry in labels]
    if sorted(labelled) != sorted(names):
        problems.append("%s: labels.json states do not match states.py functions" % os.path.basename(task_dir))
    wrong = sum(1 for e in labels if e.get("label") == "wrong")
    correct = sum(1 for e in labels if e.get("label") == "correct")
    if os.path.basename(task_dir) in KNOWN and (wrong, correct) != (18, 4):
        problems.append("%s: expected 18 wrong and 4 correct, found %d/%d" % (os.path.basename(task_dir), wrong, correct))
    for entry in labels:
        if entry.get("label") not in ("wrong", "correct"):
            problems.append("%s: bad label on %s" % (os.path.basename(task_dir), entry.get("state")))
        if not entry.get("why"):
            problems.append("%s: missing why on %s" % (os.path.basename(task_dir), entry.get("state")))


KNOWN = set()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots-dir", default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--task", default=None, help="only this task id")
    args = parser.parse_args(argv)

    task_ids = sorted(
        d for d in os.listdir(HERE)
        if os.path.isdir(os.path.join(HERE, d)) and os.path.exists(os.path.join(HERE, d, "states.py"))
    )
    if args.task:
        task_ids = [t for t in task_ids if t == args.task]
    KNOWN.update(task_ids)

    problems = []
    summary = []
    for task_id in task_ids:
        task_dir = os.path.join(HERE, task_id)
        snapshot_dir = os.path.join(args.snapshots_dir, task_id)
        if not os.path.isdir(snapshot_dir):
            problems.append("%s: snapshot directory missing" % task_id)
            continue
        module = load_states_module(task_dir)
        functions = state_functions(module)
        baseline_dir = os.path.join(args.out_dir, task_id, "_snapshot")
        if args.verify:
            shutil.rmtree(baseline_dir, ignore_errors=True)
            sys.path.insert(0, HERE)
            from statekit import copy_snapshot
            copy_snapshot(snapshot_dir, baseline_dir)
            baseline_hash = tree_hash(baseline_dir)
            check_labels(task_dir, [n for n, _ in functions], problems)
        hashes = {}
        for name, fn in functions:
            state_dir = os.path.join(args.out_dir, task_id, name)
            try:
                fn(snapshot_dir, state_dir)
            except Exception:
                problems.append("%s/%s: generator raised\n%s" % (task_id, name, traceback.format_exc()))
                continue
            if not os.path.isdir(state_dir):
                problems.append("%s/%s: generator produced no output directory" % (task_id, name))
                continue
            if not args.verify:
                continue
            digest = tree_hash(state_dir)
            if digest == baseline_hash:
                problems.append("%s/%s: identical to the untouched snapshot" % (task_id, name))
            if digest in hashes:
                problems.append("%s/%s: same output tree as %s" % (task_id, name, hashes[digest]))
            hashes[digest] = name
            for document in documents(state_dir):
                error = open_error(document)
                if error:
                    problems.append("%s/%s: %s does not open (%s)" % (
                        task_id, name, os.path.relpath(document, state_dir), error))
        if args.verify:
            shutil.rmtree(baseline_dir, ignore_errors=True)
        summary.append((task_id, len(functions)))

    for task_id, count in summary:
        print("%s: %d states materialised" % (task_id, count))
    print("total states: %d" % sum(c for _, c in summary))
    if args.verify:
        if problems:
            print("\n%d problem(s):" % len(problems))
            for problem in problems:
                print("  " + problem.replace("\n", "\n  "))
            return 1
        print("verify: every state differs from its snapshot, states within a task are distinct, all documents open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
