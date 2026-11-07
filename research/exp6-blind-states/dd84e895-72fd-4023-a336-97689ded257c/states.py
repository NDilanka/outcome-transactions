import os
import shutil
import tarfile

TGZ_REL = os.path.join("home", "user", "thunderbird-profile.tar.gz")
BILLS_REL = os.path.join(
    "home",
    "user",
    ".thunderbird",
    "t5q2a5hp.default-release",
    "Mail",
    "Local Folders",
    "Bills",
)
TRASH_REL = os.path.join(
    "home",
    "user",
    ".thunderbird",
    "t5q2a5hp.default-release",
    "Mail",
    "Local Folders",
    "Trash",
)


def _prepare_and_extract(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    tgz_path = os.path.join(out_dir, TGZ_REL)
    user_dir = os.path.join(out_dir, "home", "user")
    with tarfile.open(tgz_path, "r:gz") as tf:
        members = [m for m in tf.getmembers() if not (m.issym() or m.islnk())]
        tf.extractall(user_dir, members=members, filter="data")
    return os.path.join(out_dir, BILLS_REL), tgz_path, user_dir


def _repack_tgz(tgz_path, user_dir):
    tb_dir = os.path.join(user_dir, ".thunderbird")
    with tarfile.open(tgz_path, "w:gz") as tf:
        tf.add(tb_dir, arcname=".thunderbird")


def correct_both_messages_starred_0005(snapshot_dir, out_dir):
    bills_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(bills_path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("X-Mozilla-Status: 0001", "X-Mozilla-Status: 0005")
    with open(bills_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    _repack_tgz(tgz_path, user_dir)


def correct_both_messages_starred_and_msf_refreshed(snapshot_dir, out_dir):
    bills_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(bills_path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("X-Mozilla-Status: 0001", "X-Mozilla-Status: 0005")
    with open(bills_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    msf_path = bills_path + ".msf"
    if os.path.exists(msf_path):
        os.remove(msf_path)
    _repack_tgz(tgz_path, user_dir)


def wrong_only_first_email_starred(snapshot_dir, out_dir):
    bills_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(bills_path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("X-Mozilla-Status: 0001", "X-Mozilla-Status: 0005", 1)
    with open(bills_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    _repack_tgz(tgz_path, user_dir)


def wrong_marked_deleted_0009_instead_of_starred(snapshot_dir, out_dir):
    bills_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(bills_path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("X-Mozilla-Status: 0001", "X-Mozilla-Status: 0009")
    with open(bills_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    _repack_tgz(tgz_path, user_dir)


def wrong_starred_trash_instead_of_bills(snapshot_dir, out_dir):
    _, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    trash_path = os.path.join(out_dir, TRASH_REL)
    with open(trash_path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("X-Mozilla-Status: 0001", "X-Mozilla-Status: 0005")
    with open(trash_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    _repack_tgz(tgz_path, user_dir)


def wrong_deleted_bills_messages(snapshot_dir, out_dir):
    bills_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(bills_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("")
    _repack_tgz(tgz_path, user_dir)


def wrong_marked_unread_0000_not_starred(snapshot_dir, out_dir):
    bills_path, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    with open(bills_path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("X-Mozilla-Status: 0001", "X-Mozilla-Status: 0000")
    with open(bills_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    _repack_tgz(tgz_path, user_dir)
