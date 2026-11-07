import os
import shutil

DESKTOP_REL = os.path.join("home", "user", "Desktop")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    desktop_dir = os.path.join(out_dir, DESKTOP_REL)
    photos_dir = os.path.join(desktop_dir, "photos")
    cpjpg_dir = os.path.join(desktop_dir, "cpjpg")
    os.makedirs(cpjpg_dir, exist_ok=True)
    return photos_dir, cpjpg_dir


def correct_copy_four_jpgs_flat_preserve_meta(snapshot_dir, out_dir):
    photos_dir, cpjpg_dir = _prepare(snapshot_dir, out_dir)
    for root, _, files in os.walk(photos_dir):
        for fname in files:
            if fname.endswith(".jpg"):
                shutil.copy2(os.path.join(root, fname), os.path.join(cpjpg_dir, fname))


def correct_copy_four_jpgs_content(snapshot_dir, out_dir):
    photos_dir, cpjpg_dir = _prepare(snapshot_dir, out_dir)
    for root, _, files in os.walk(photos_dir):
        rel = os.path.relpath(root, photos_dir)
        for fname in sorted(files):
            if fname.endswith(".jpg"):
                dst_dir = os.path.join(cpjpg_dir, rel)
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copy2(os.path.join(root, fname), os.path.join(dst_dir, fname))


def wrong_moved_instead_of_copied(snapshot_dir, out_dir):
    photos_dir, cpjpg_dir = _prepare(snapshot_dir, out_dir)
    for root, _, files in os.walk(photos_dir):
        for fname in files:
            if fname.endswith(".jpg"):
                shutil.move(os.path.join(root, fname), os.path.join(cpjpg_dir, fname))


def wrong_copied_png_file_as_well(snapshot_dir, out_dir):
    photos_dir, cpjpg_dir = _prepare(snapshot_dir, out_dir)
    for root, _, files in os.walk(photos_dir):
        for fname in files:
            shutil.copy2(os.path.join(root, fname), os.path.join(cpjpg_dir, fname))


def wrong_partial_missed_nested_vacation_subfolders(snapshot_dir, out_dir):
    photos_dir, cpjpg_dir = _prepare(snapshot_dir, out_dir)
    events_dir = os.path.join(photos_dir, "events")
    for fname in os.listdir(events_dir):
        if fname.endswith(".jpg"):
            shutil.copy2(os.path.join(events_dir, fname), os.path.join(cpjpg_dir, fname))


def wrong_copied_nested_subdirectories_not_flat(snapshot_dir, out_dir):
    photos_dir, cpjpg_dir = _prepare(snapshot_dir, out_dir)
    shutil.copytree(photos_dir, os.path.join(cpjpg_dir, "photos"), dirs_exist_ok=True)


def wrong_created_empty_zero_byte_jpgs(snapshot_dir, out_dir):
    photos_dir, cpjpg_dir = _prepare(snapshot_dir, out_dir)
    for root, _, files in os.walk(photos_dir):
        for fname in files:
            if fname.endswith(".jpg"):
                open(os.path.join(cpjpg_dir, fname), "wb").close()
