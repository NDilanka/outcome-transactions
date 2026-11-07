import json
import os
import shutil

USER_REL = os.path.join("home", "user")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    user_dir = os.path.join(out_dir, USER_REL)
    for sub in ("project", "data1", "data2"):
        os.makedirs(os.path.join(user_dir, sub), exist_ok=True)
    return user_dir


def correct_workspace_relative_paths(snapshot_dir, out_dir):
    user_dir = _prepare(snapshot_dir, out_dir)
    ws_path = os.path.join(user_dir, "project.code-workspace")
    payload = {
        "folders": [
            {"path": "project"},
            {"path": "data1"},
            {"path": "data2"},
        ],
        "settings": {},
    }
    with open(ws_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent="\t")
        f.write("\n")


def correct_workspace_absolute_paths(snapshot_dir, out_dir):
    user_dir = _prepare(snapshot_dir, out_dir)
    ws_path = os.path.join(user_dir, "project.code-workspace")
    payload = {
        "folders": [
            {"path": "/home/user/project"},
            {"path": "/home/user/data1"},
            {"path": "/home/user/data2"},
        ],
        "settings": {},
    }
    with open(ws_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent="\t")
        f.write("\n")


def wrong_partial_only_data1_added(snapshot_dir, out_dir):
    user_dir = _prepare(snapshot_dir, out_dir)
    ws_path = os.path.join(user_dir, "project.code-workspace")
    payload = {
        "folders": [
            {"path": "project"},
            {"path": "data1"},
        ],
        "settings": {},
    }
    with open(ws_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent="\t")
        f.write("\n")


def wrong_saved_inside_project_subdir(snapshot_dir, out_dir):
    user_dir = _prepare(snapshot_dir, out_dir)
    ws_path = os.path.join(user_dir, "project", "project.code-workspace")
    payload = {
        "folders": [
            {"path": "."},
            {"path": "../data1"},
            {"path": "../data2"},
        ],
        "settings": {},
    }
    with open(ws_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent="\t")
        f.write("\n")


def wrong_typo_data3_instead_of_data2(snapshot_dir, out_dir):
    user_dir = _prepare(snapshot_dir, out_dir)
    ws_path = os.path.join(user_dir, "project.code-workspace")
    payload = {
        "folders": [
            {"path": "project"},
            {"path": "data1"},
            {"path": "data3"},
        ],
        "settings": {},
    }
    with open(ws_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent="\t")
        f.write("\n")


def wrong_invalid_json_syntax(snapshot_dir, out_dir):
    user_dir = _prepare(snapshot_dir, out_dir)
    ws_path = os.path.join(user_dir, "project.code-workspace")
    with open(ws_path, "w", encoding="utf-8", newline="\n") as f:
        f.write('{"folders": [/home/user/data1, /home/user/data2]\n')


def wrong_empty_folders_list(snapshot_dir, out_dir):
    user_dir = _prepare(snapshot_dir, out_dir)
    ws_path = os.path.join(user_dir, "project.code-workspace")
    payload = {
        "folders": [],
        "settings": {},
    }
    with open(ws_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent="\t")
        f.write("\n")
