import os
import shutil
import struct

REL_PATH = os.path.join("home", "user", "Desktop", "orange_background.xcf")
THANKS_OFFSET_POS = 1165
BG_OFFSET_POS = 8724


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def _patch_offset(xcf_path, pos, dx, dy):
    with open(xcf_path, "rb") as f:
        data = bytearray(f.read())
    prop_type, prop_len = struct.unpack(">II", data[pos : pos + 8])
    assert prop_type == 15 and prop_len == 8
    struct.pack_into(">ii", data, pos + 8, dx, dy)
    with open(xcf_path, "wb") as f:
        f.write(data)


def correct_left_side_dx_120(snapshot_dir, out_dir):
    xcf_path = _prepare(snapshot_dir, out_dir)
    _patch_offset(xcf_path, THANKS_OFFSET_POS, 120, 702)


def correct_left_side_dx_240(snapshot_dir, out_dir):
    xcf_path = _prepare(snapshot_dir, out_dir)
    _patch_offset(xcf_path, THANKS_OFFSET_POS, 240, 702)


def wrong_moved_to_right_side(snapshot_dir, out_dir):
    xcf_path = _prepare(snapshot_dir, out_dir)
    _patch_offset(xcf_path, THANKS_OFFSET_POS, 1650, 702)


def wrong_moved_background_layer_instead(snapshot_dir, out_dir):
    xcf_path = _prepare(snapshot_dir, out_dir)
    _patch_offset(xcf_path, BG_OFFSET_POS, -500, 0)


def wrong_moved_up_vertically_not_left(snapshot_dir, out_dir):
    xcf_path = _prepare(snapshot_dir, out_dir)
    _patch_offset(xcf_path, THANKS_OFFSET_POS, 976, 80)


def wrong_moved_completely_off_canvas_left(snapshot_dir, out_dir):
    xcf_path = _prepare(snapshot_dir, out_dir)
    _patch_offset(xcf_path, THANKS_OFFSET_POS, -600, 702)


def wrong_hidden_layer_without_moving(snapshot_dir, out_dir):
    xcf_path = _prepare(snapshot_dir, out_dir)
    with open(xcf_path, "rb") as f:
        data = bytearray(f.read())
    # Set PROP_VISIBLE (at offset 1057: type=8, len=4, val=1) to 0 while keeping dx=976, dy=702
    assert data[1057 : 1057 + 12] == b"\x00\x00\x00\x08\x00\x00\x00\x04\x00\x00\x00\x01"
    struct.pack_into(">I", data, 1057 + 8, 0)
    with open(xcf_path, "wb") as f:
        f.write(data)
