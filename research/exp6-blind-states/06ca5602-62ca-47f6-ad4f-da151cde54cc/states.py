import os
import shutil
from PIL import Image

REL_PATH = os.path.join("home", "user", "Desktop", "computer.png")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def correct_adaptive_palette_256(snapshot_dir, out_dir):
    png_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path)
    pal = img.convert("RGB").convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
    pal.save(png_path, optimize=True)


def correct_mediancut_quantize_palette(snapshot_dir, out_dir):
    png_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path)
    pal = img.convert("RGB").quantize(
        colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE
    )
    pal.save(png_path)


def wrong_grayscale_mode_L_instead_of_palette(snapshot_dir, out_dir):
    png_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path).convert("L")
    img.save(png_path, optimize=True)


def wrong_rgb_mode_not_palette_indexed(snapshot_dir, out_dir):
    png_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path).convert("RGB")
    img.save(png_path)


def wrong_1bit_bilevel_black_white(snapshot_dir, out_dir):
    png_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path).convert("1")
    img.save(png_path)


def wrong_palette_but_resized_half_dimensions(snapshot_dir, out_dir):
    png_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path).resize((360, 240))
    pal = img.convert("RGB").convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
    pal.save(png_path, optimize=True)


def wrong_saved_as_jpg_left_png_rgba(snapshot_dir, out_dir):
    png_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path).convert("RGB")
    jpg_path = os.path.join(os.path.dirname(png_path), "computer.jpg")
    img.save(jpg_path, quality=75)
