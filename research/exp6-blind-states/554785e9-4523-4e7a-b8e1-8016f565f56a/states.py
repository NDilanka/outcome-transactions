import os
import shutil
from PIL import Image, ImageEnhance, ImageOps

REL_PATH = os.path.join("home", "user", "Desktop", "woman_sitting_by_the_tree2.png")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def correct_color_saturation_boost_1_35(snapshot_dir, out_dir):
    png_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path).convert("RGB")
    out = ImageEnhance.Color(img).enhance(1.35)
    out.save(png_path)


def correct_color_and_contrast_vibrancy_boost(snapshot_dir, out_dir):
    png_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path).convert("RGB")
    out = ImageEnhance.Color(img).enhance(1.5)
    out = ImageEnhance.Contrast(out).enhance(1.08)
    out.save(png_path)


def wrong_desaturated_to_grayscale(snapshot_dir, out_dir):
    png_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path).convert("RGB")
    out = ImageEnhance.Color(img).enhance(0.0)
    out.save(png_path)


def wrong_reduced_saturation_dull(snapshot_dir, out_dir):
    png_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path).convert("RGB")
    out = ImageEnhance.Color(img).enhance(0.5)
    out.save(png_path)


def wrong_inverted_negative_colors(snapshot_dir, out_dir):
    png_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path).convert("RGB")
    out = ImageOps.invert(img)
    out.save(png_path)


def wrong_extreme_overblown_brightness(snapshot_dir, out_dir):
    png_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path).convert("RGB")
    out = ImageEnhance.Brightness(img).enhance(2.8)
    out.save(png_path)


def wrong_saved_to_new_file_original_untouched(snapshot_dir, out_dir):
    png_path = _prepare(snapshot_dir, out_dir)
    img = Image.open(png_path).convert("RGB")
    out = ImageEnhance.Color(img).enhance(1.4)
    alt_path = os.path.join(os.path.dirname(png_path), "woman_sitting_by_the_tree2_enhanced.png")
    out.save(alt_path)
