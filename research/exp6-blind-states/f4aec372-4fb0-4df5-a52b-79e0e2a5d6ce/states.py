import os
import shutil
import struct
from PIL import Image, ImageDraw

PNG_REL = os.path.join("home", "user", "Desktop", "Triangle_On_The_Side.png")
XCF_REL = os.path.join("home", "user", "Desktop", "Triangle_On_The_Side.xcf")
XCF_OFFSET_POS = 561


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, PNG_REL), os.path.join(out_dir, XCF_REL)


def _patch_xcf_offsets(xcf_path, dx, dy):
    with open(xcf_path, "rb") as f:
        data = bytearray(f.read())
    prop_type, prop_len = struct.unpack(">II", data[XCF_OFFSET_POS : XCF_OFFSET_POS + 8])
    assert prop_type == 15 and prop_len == 8
    struct.pack_into(">ii", data, XCF_OFFSET_POS + 8, dx, dy)
    with open(xcf_path, "wb") as f:
        f.write(data)


def _move_triangle_png(png_path, new_x, new_y, clear_old=True, recolor_rgb=None):
    img = Image.open(png_path).convert("RGBA")
    patch = img.crop((28, 72, 28 + 348, 72 + 203)).copy()
    if recolor_rgb is not None:
        px = patch.load()
        for y in range(patch.height):
            for x in range(patch.width):
                r, g, b, a = px[x, y]
                if r > 200 and g > 150 and b < 100:
                    px[x, y] = (*recolor_rgb, a)
    if clear_old:
        draw = ImageDraw.Draw(img)
        draw.rectangle([28, 72, 28 + 348, 72 + 203], fill=(255, 255, 255, 255))
    img.paste(patch, (new_x, new_y))
    img.save(png_path)


def correct_centered_exact_226_299(snapshot_dir, out_dir):
    png_path, xcf_path = _prepare(snapshot_dir, out_dir)
    _move_triangle_png(png_path, 226, 299, clear_old=True)
    _patch_xcf_offsets(xcf_path, 226, 299)


def correct_centered_layer_226_298(snapshot_dir, out_dir):
    png_path, xcf_path = _prepare(snapshot_dir, out_dir)
    _move_triangle_png(png_path, 226, 298, clear_old=True)
    _patch_xcf_offsets(xcf_path, 226, 298)


def wrong_only_horizontally_centered(snapshot_dir, out_dir):
    png_path, xcf_path = _prepare(snapshot_dir, out_dir)
    _move_triangle_png(png_path, 226, 72, clear_old=True)
    _patch_xcf_offsets(xcf_path, 226, 72)


def wrong_moved_to_bottom_right_corner(snapshot_dir, out_dir):
    png_path, xcf_path = _prepare(snapshot_dir, out_dir)
    _move_triangle_png(png_path, 424, 570, clear_old=True)
    _patch_xcf_offsets(xcf_path, 424, 570)


def wrong_duplicated_triangle_left_original(snapshot_dir, out_dir):
    png_path, xcf_path = _prepare(snapshot_dir, out_dir)
    _move_triangle_png(png_path, 226, 299, clear_old=False)


def wrong_centered_but_recolored_blue(snapshot_dir, out_dir):
    png_path, xcf_path = _prepare(snapshot_dir, out_dir)
    _move_triangle_png(png_path, 226, 299, clear_old=True, recolor_rgb=(0, 80, 255))
    _patch_xcf_offsets(xcf_path, 226, 299)


def wrong_erased_triangle_all_white(snapshot_dir, out_dir):
    png_path, xcf_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    draw.rectangle([28, 72, 28 + 348, 72 + 203], fill=(255, 255, 255, 255))
    img.save(png_path)
    _patch_xcf_offsets(xcf_path, -500, -500)
