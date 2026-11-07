import os
import shutil
import tarfile

TGZ_REL = os.path.join("home", "user", "thunderbird-profile.tar.gz")
PREFS_REL = os.path.join(
    "home", "user", ".thunderbird", "t5q2a5hp.default-release", "prefs.js"
)


def _prepare_and_extract(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    tgz_path = os.path.join(out_dir, TGZ_REL)
    user_dir = os.path.join(out_dir, "home", "user")
    with tarfile.open(tgz_path, "r:gz") as tf:
        members = [m for m in tf.getmembers() if not (m.issym() or m.islnk())]
        tf.extractall(user_dir, members=members, filter="data")
    return os.path.join(out_dir, PREFS_REL), tgz_path, user_dir


def _repack_tgz(tgz_path, user_dir):
    tb_dir = os.path.join(user_dir, ".thunderbird")
    with tarfile.open(tgz_path, "w:gz") as tf:
        tf.add(tb_dir, arcname=".thunderbird")


def correct_apply_incoming_filters_boolean_true(snapshot_dir, out_dir):
    prefs_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(prefs_path, "a", encoding="utf-8", newline="\n") as f:
        f.write('user_pref("mail.server.default.applyIncomingFilters", true);\n')
    _repack_tgz(tgz_path, user_dir)


def correct_apply_incoming_filters_string_true(snapshot_dir, out_dir):
    prefs_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(prefs_path, "a", encoding="utf-8", newline="\n") as f:
        f.write('user_pref("mail.server.default.applyIncomingFilters", "true");\n')
    _repack_tgz(tgz_path, user_dir)


def wrong_set_to_false(snapshot_dir, out_dir):
    prefs_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(prefs_path, "a", encoding="utf-8", newline="\n") as f:
        f.write('user_pref("mail.server.default.applyIncomingFilters", false);\n')
    _repack_tgz(tgz_path, user_dir)


def wrong_server1_instead_of_default(snapshot_dir, out_dir):
    prefs_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(prefs_path, "a", encoding="utf-8", newline="\n") as f:
        f.write('user_pref("mail.server.server1.applyIncomingFilters", true);\n')
    _repack_tgz(tgz_path, user_dir)


def wrong_typo_missing_trailing_s(snapshot_dir, out_dir):
    prefs_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(prefs_path, "a", encoding="utf-8", newline="\n") as f:
        f.write('user_pref("mail.server.default.applyIncomingFilter", true);\n')
    _repack_tgz(tgz_path, user_dir)


def wrong_integer_zero_disabled(snapshot_dir, out_dir):
    prefs_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(prefs_path, "a", encoding="utf-8", newline="\n") as f:
        f.write('user_pref("mail.server.default.applyIncomingFilters", 0);\n')
    _repack_tgz(tgz_path, user_dir)


def wrong_wiped_existing_prefs_js(snapshot_dir, out_dir):
    prefs_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(prefs_path, "w", encoding="utf-8", newline="\n") as f:
        f.write('user_pref("mail.server.default.applyIncomingFilters", true);\n')
    _repack_tgz(tgz_path, user_dir)
