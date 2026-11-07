import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SNAPSHOTS = os.path.abspath(
    os.path.join(HERE, "..", "exp5-grounded", "snapshots")
)
DEFAULT_OUT = os.path.join(HERE, "materialized")


def tree_digest(root_dir):
    entries = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames.sort()
        filenames.sort()
        rel_dir = os.path.relpath(dirpath, root_dir).replace("\\", "/")
        entries.append(("D", rel_dir, b""))
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            rel_file = os.path.relpath(fpath, root_dir).replace("\\", "/")
            if os.path.islink(fpath):
                entries.append(("L", rel_file, os.readlink(fpath).encode("utf-8", errors="replace")))
                continue
            h = hashlib.sha256()
            with open(fpath, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
            entries.append(("F", rel_file, h.digest()))
    return entries


def load_states_module(task_dir, task_id):
    states_path = os.path.join(task_dir, "states.py")
    spec = importlib.util.spec_from_file_location(f"states_{task_id}", states_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def discover_tasks(base_dir):
    tasks = []
    for name in sorted(os.listdir(base_dir)):
        task_dir = os.path.join(base_dir, name)
        if os.path.isdir(task_dir) and os.path.isfile(os.path.join(task_dir, "states.py")):
            tasks.append(name)
    return tasks


def main():
    parser = argparse.ArgumentParser(
        description="Materialize all blind end states from input snapshots."
    )
    parser.add_argument(
        "--snapshots-dir",
        default=DEFAULT_SNAPSHOTS,
        help="Path to the snapshots directory containing <task_id>/ folders.",
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT,
        help="Output directory where <task_id>/<state_name>/ trees are written.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify that every materialized state differs from its starting snapshot.",
    )
    args = parser.parse_args()

    snapshots_dir = os.path.abspath(args.snapshots_dir)
    out_dir = os.path.abspath(args.out_dir)
    tasks = discover_tasks(HERE)

    total_states = 0
    for task_id in tasks:
        task_dir = os.path.join(HERE, task_id)
        labels_path = os.path.join(task_dir, "labels.json")
        with open(labels_path, "r", encoding="utf-8") as f:
            labels = json.load(f)

        wrong_count = sum(1 for item in labels if item["label"] == "wrong")
        correct_count = sum(1 for item in labels if item["label"] == "correct")
        assert wrong_count == 5 and correct_count == 2, (
            f"{task_id}: expected 5 wrong and 2 correct states, got {wrong_count} wrong and {correct_count} correct"
        )

        snap_task_dir = os.path.join(snapshots_dir, task_id)
        if not os.path.isdir(snap_task_dir):
            raise FileNotFoundError(f"Missing snapshot directory: {snap_task_dir}")

        snap_digest = tree_digest(snap_task_dir) if args.verify else None
        seen_digests = {}
        mod = load_states_module(task_dir, task_id)

        for item in labels:
            state_name = item["state"]
            fn = getattr(mod, state_name, None)
            if fn is None:
                raise AttributeError(f"{task_id}: missing function {state_name} in states.py")

            state_out = os.path.join(out_dir, task_id, state_name)
            if os.path.exists(state_out):
                shutil.rmtree(state_out)
            fn(snap_task_dir, state_out)
            total_states += 1

            if args.verify:
                state_digest = tree_digest(state_out)
                if state_digest == snap_digest:
                    raise AssertionError(
                        f"{task_id}/{state_name} did not modify any file relative to the snapshot"
                    )
                digest_key = repr(state_digest)
                if digest_key in seen_digests:
                    raise AssertionError(
                        f"{task_id}/{state_name} produced the same file tree as {seen_digests[digest_key]}"
                    )
                seen_digests[digest_key] = state_name

        print(f"OK {task_id}: {len(labels)} states materialized")

    print(f"Done: {len(tasks)} tasks, {total_states} states materialized to {out_dir}")


if __name__ == "__main__":
    main()
