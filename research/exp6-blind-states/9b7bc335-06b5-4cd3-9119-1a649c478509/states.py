import os
import shutil
import tarfile

TGZ_REL = os.path.join("home", "user", "thunderbird-profile.tar.gz")
IMAP_RULES_REL = os.path.join(
    "home",
    "user",
    ".thunderbird",
    "t5q2a5hp.default-release",
    "ImapMail",
    "outlook.office365.com",
    "msgFilterRules.dat",
)
LOCAL_RULES_REL = os.path.join(
    "home",
    "user",
    ".thunderbird",
    "t5q2a5hp.default-release",
    "Mail",
    "Local Folders",
    "msgFilterRules.dat",
)


def _prepare_and_extract(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    tgz_path = os.path.join(out_dir, TGZ_REL)
    user_dir = os.path.join(out_dir, "home", "user")
    with tarfile.open(tgz_path, "r:gz") as tf:
        members = [m for m in tf.getmembers() if not (m.issym() or m.islnk())]
        tf.extractall(user_dir, members=members, filter="data")
    return (
        os.path.join(out_dir, IMAP_RULES_REL),
        os.path.join(out_dir, LOCAL_RULES_REL),
        tgz_path,
        user_dir,
    )


def _repack_tgz(tgz_path, user_dir):
    tb_dir = os.path.join(user_dir, ".thunderbird")
    with tarfile.open(tgz_path, "w:gz") as tf:
        tf.add(tb_dir, arcname=".thunderbird")


def correct_imap_forward_all_filter_type17(snapshot_dir, out_dir):
    imap_rules, _, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    content = (
        'version="9"\n'
        'logging="no"\n'
        'name="Forward All"\n'
        'enabled="yes"\n'
        'type="17"\n'
        'action="Forward"\n'
        'actionValue="anonym-x2024@gmail.com"\n'
        'condition="ALL"\n'
    )
    with open(imap_rules, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    _repack_tgz(tgz_path, user_dir)


def correct_imap_and_local_forward_all_filter(snapshot_dir, out_dir):
    imap_rules, local_rules, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    content = (
        'version="9"\n'
        'logging="no"\n'
        'name="Forward to Gmail"\n'
        'enabled="yes"\n'
        'type="17"\n'
        'action="Forward"\n'
        'actionValue="anonym-x2024@gmail.com"\n'
        'condition="ALL"\n'
    )
    with open(imap_rules, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    with open(local_rules, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    _repack_tgz(tgz_path, user_dir)


def wrong_forwarded_to_outlook_instead_of_gmail(snapshot_dir, out_dir):
    imap_rules, _, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    content = (
        'version="9"\n'
        'logging="no"\n'
        'name="Forward All"\n'
        'enabled="yes"\n'
        'type="17"\n'
        'action="Forward"\n'
        'actionValue="anonym-x2024@outlook.com"\n'
        'condition="ALL"\n'
    )
    with open(imap_rules, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    _repack_tgz(tgz_path, user_dir)


def wrong_filter_disabled(snapshot_dir, out_dir):
    imap_rules, _, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    content = (
        'version="9"\n'
        'logging="no"\n'
        'name="Forward All"\n'
        'enabled="no"\n'
        'type="17"\n'
        'action="Forward"\n'
        'actionValue="anonym-x2024@gmail.com"\n'
        'condition="ALL"\n'
    )
    with open(imap_rules, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    _repack_tgz(tgz_path, user_dir)


def wrong_action_delete_instead_of_forward(snapshot_dir, out_dir):
    imap_rules, _, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    content = (
        'version="9"\n'
        'logging="no"\n'
        'name="Forward All"\n'
        'enabled="yes"\n'
        'type="17"\n'
        'action="Delete"\n'
        'condition="ALL"\n'
    )
    with open(imap_rules, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    _repack_tgz(tgz_path, user_dir)


def wrong_condition_restrictive_not_all(snapshot_dir, out_dir):
    imap_rules, _, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    content = (
        'version="9"\n'
        'logging="no"\n'
        'name="Forward Urgent"\n'
        'enabled="yes"\n'
        'type="17"\n'
        'action="Forward"\n'
        'actionValue="anonym-x2024@gmail.com"\n'
        'condition="AND (subject,contains,urgent)"\n'
    )
    with open(imap_rules, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    _repack_tgz(tgz_path, user_dir)


def wrong_only_in_local_folders_imap_untouched(snapshot_dir, out_dir):
    _, local_rules, tgz_path, user_dir = _prepare_and_extract(snapshot_dir, out_dir)
    content = (
        'version="9"\n'
        'logging="no"\n'
        'name="Forward All"\n'
        'enabled="yes"\n'
        'type="17"\n'
        'action="Forward"\n'
        'actionValue="anonym-x2024@gmail.com"\n'
        'condition="ALL"\n'
    )
    with open(local_rules, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    _repack_tgz(tgz_path, user_dir)
