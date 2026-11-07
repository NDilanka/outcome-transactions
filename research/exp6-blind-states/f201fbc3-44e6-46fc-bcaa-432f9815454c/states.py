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


def correct_id1_auto_quote_false(snapshot_dir, out_dir):
    prefs_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(prefs_path, "a", encoding="utf-8", newline="\n") as f:
        f.write('user_pref("mail.identity.id1.auto_quote", false);\n')
    _repack_tgz(tgz_path, user_dir)


def correct_id1_auto_quote_false_sorted(snapshot_dir, out_dir):
    prefs_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(prefs_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_line = 'user_pref("mail.identity.id1.auto_quote", false);\n'
    inserted = False
    out_lines = []
    for line in lines:
        if not inserted and 'user_pref("mail.identity.id1.' in line:
            out_lines.append(new_line)
            inserted = True
        out_lines.append(line)
    if not inserted:
        out_lines.append(new_line)
    with open(prefs_path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(out_lines)
    _repack_tgz(tgz_path, user_dir)


def wrong_auto_quote_set_to_true(snapshot_dir, out_dir):
    prefs_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(prefs_path, "a", encoding="utf-8", newline="\n") as f:
        f.write('user_pref("mail.identity.id1.auto_quote", true);\n')
    _repack_tgz(tgz_path, user_dir)


def wrong_id2_instead_of_id1(snapshot_dir, out_dir):
    prefs_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(prefs_path, "a", encoding="utf-8", newline="\n") as f:
        f.write('user_pref("mail.identity.id2.auto_quote", false);\n')
    _repack_tgz(tgz_path, user_dir)


def wrong_string_false_instead_of_boolean(snapshot_dir, out_dir):
    prefs_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(prefs_path, "a", encoding="utf-8", newline="\n") as f:
        f.write('user_pref("mail.identity.id1.auto_quote", "false");\n')
    _repack_tgz(tgz_path, user_dir)


def wrong_changed_reply_on_top_instead_of_auto_quote(snapshot_dir, out_dir):
    prefs_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(prefs_path, "a", encoding="utf-8", newline="\n") as f:
        f.write('user_pref("mail.identity.id1.reply_on_top", 0);\n')
    _repack_tgz(tgz_path, user_dir)


def wrong_deleted_id1_identity_settings(snapshot_dir, out_dir):
    prefs_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(prefs_path, "r", encoding="utf-8") as f:
        lines = [l for l in f.readlines() if "mail.identity.id1." not in l]
    lines.append('user_pref("mail.identity.id1.auto_quote", false);\n')
    with open(prefs_path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(lines)
    _repack_tgz(tgz_path, user_dir)
