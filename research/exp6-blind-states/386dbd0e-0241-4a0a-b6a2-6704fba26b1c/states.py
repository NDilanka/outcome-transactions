import os
import shutil

REL_PATH = os.path.join("home", "user", ".config", "vlc", "vlcrc")

BASE_VLCRC = (
    "###\n"
    "###  vlc 3.0.16 configuration file\n"
    "###\n\n"
    "[main] # main program\n\n"
    "# Play/Pause (string)\n"
    "#global-key-play-pause=\n\n"
    "# Play/Pause (string)\n"
    "#key-play-pause=Space\n\n"
    "# Stop (string)\n"
    "#global-key-stop=\n\n"
    "# Stop (string)\n"
    "#key-stop=s\n"
)


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    vlcrc_path = os.path.join(out_dir, REL_PATH)
    os.makedirs(os.path.dirname(vlcrc_path), exist_ok=True)
    if not os.path.exists(vlcrc_path):
        with open(vlcrc_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(BASE_VLCRC)
    return vlcrc_path


def _replace_in_vlcrc(vlcrc_path, old_str, new_str):
    with open(vlcrc_path, "r", encoding="utf-8") as f:
        text = f.read()
    assert old_str in text
    text = text.replace(old_str, new_str, 1)
    with open(vlcrc_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def correct_global_key_play_pause_ctrl_alt_space(snapshot_dir, out_dir):
    vlcrc_path = _prepare(snapshot_dir, out_dir)
    _replace_in_vlcrc(
        vlcrc_path,
        "#global-key-play-pause=",
        "global-key-play-pause=Ctrl+Alt+Space",
    )


def correct_global_key_play_pause_pause_key(snapshot_dir, out_dir):
    vlcrc_path = _prepare(snapshot_dir, out_dir)
    _replace_in_vlcrc(
        vlcrc_path,
        "#global-key-play-pause=",
        "global-key-play-pause=Pause",
    )


def wrong_modified_local_key_not_global(snapshot_dir, out_dir):
    vlcrc_path = _prepare(snapshot_dir, out_dir)
    _replace_in_vlcrc(
        vlcrc_path,
        "#key-play-pause=Space",
        "key-play-pause=Ctrl+Alt+Space",
    )


def wrong_left_commented_out(snapshot_dir, out_dir):
    vlcrc_path = _prepare(snapshot_dir, out_dir)
    _replace_in_vlcrc(
        vlcrc_path,
        "#global-key-play-pause=",
        "#global-key-play-pause=Ctrl+Alt+Space",
    )


def wrong_set_global_key_stop_instead_of_play_pause(snapshot_dir, out_dir):
    vlcrc_path = _prepare(snapshot_dir, out_dir)
    _replace_in_vlcrc(
        vlcrc_path,
        "#global-key-stop=",
        "global-key-stop=Ctrl+Alt+Space",
    )


def wrong_uncommented_but_empty_value(snapshot_dir, out_dir):
    vlcrc_path = _prepare(snapshot_dir, out_dir)
    _replace_in_vlcrc(
        vlcrc_path,
        "#global-key-play-pause=",
        "global-key-play-pause=",
    )


def wrong_conflicting_system_hotkey_alt_f4(snapshot_dir, out_dir):
    vlcrc_path = _prepare(snapshot_dir, out_dir)
    _replace_in_vlcrc(
        vlcrc_path,
        "#global-key-play-pause=",
        "global-key-play-pause=Alt+F4",
    )
