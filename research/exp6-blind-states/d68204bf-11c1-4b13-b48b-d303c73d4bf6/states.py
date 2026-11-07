import os
import shutil
from PIL import Image

DESKTOP_REL = os.path.join("home", "user", "Desktop")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    desktop = os.path.join(out_dir, DESKTOP_REL)
    return os.path.join(desktop, "tilearray.png"), os.path.join(desktop, "rearranged.png")


def _cut_vertical_sections(img, bounds=((0, 320), (320, 641), (641, 962))):
    h = img.height
    return [img.crop((x0, 0, x1, h)) for x0, x1 in bounds]


def _concat_horizontal(sections, total_w=962, total_h=1280):
    out = Image.new("RGB", (total_w, total_h))
    x = 0
    for sec in sections:
        out.paste(sec, (x, 0))
        x += sec.width
    return out


def correct_warmest_to_coolest_by_temp_2_1_0(snapshot_dir, out_dir):
    src_path, dst_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(src_path)
    secs = _cut_vertical_sections(img)
    out = _concat_horizontal([secs[2], secs[1], secs[0]], img.width, img.height)
    out.save(dst_path)


def correct_warmest_to_coolest_by_red_2_0_1(snapshot_dir, out_dir):
    src_path, dst_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(src_path)
    secs = _cut_vertical_sections(img)
    out = _concat_horizontal([secs[2], secs[0], secs[1]], img.width, img.height)
    out.save(dst_path)


def wrong_coolest_to_warmest_reversed(snapshot_dir, out_dir):
    src_path, dst_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(src_path)
    secs = _cut_vertical_sections(img)
    out = _concat_horizontal([secs[1], secs[0], secs[2]], img.width, img.height)
    out.save(dst_path)


def wrong_cut_horizontally_instead_of_vertically(snapshot_dir, out_dir):
    src_path, dst_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(src_path)
    w = img.width
    h_secs = [
        img.crop((0, 0, w, 426)),
        img.crop((0, 426, w, 853)),
        img.crop((0, 853, w, 1280)),
    ]
    out = Image.new("RGB", (img.width, img.height))
    y = 0
    for sec in [h_secs[2], h_secs[1], h_secs[0]]:
        out.paste(sec, (0, y))
        y += sec.height
    out.save(dst_path)


def wrong_resolution_960_instead_of_962(snapshot_dir, out_dir):
    src_path, dst_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(src_path)
    secs = _cut_vertical_sections(img, bounds=((0, 320), (320, 640), (640, 960)))
    out = _concat_horizontal([secs[2], secs[1], secs[0]], 960, img.height)
    out.save(dst_path)


def wrong_overwrote_tilearray_missing_rearranged(snapshot_dir, out_dir):
    src_path, _ = _prepare(snapshot_dir, out_dir)
    img = Image.open(src_path)
    secs = _cut_vertical_sections(img)
    out = _concat_horizontal([secs[2], secs[1], secs[0]], img.width, img.height)
    out.save(src_path)


def wrong_duplicated_warmest_section_three_times(snapshot_dir, out_dir):
    src_path, dst_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(src_path)
    secs = _cut_vertical_sections(img)
    out = Image.new("RGB", (img.width, img.height))
    out.paste(secs[2].resize((320, img.height)), (0, 0))
    out.paste(secs[2], (320, 0))
    out.paste(secs[2], (641, 0))
    out.save(dst_path)
