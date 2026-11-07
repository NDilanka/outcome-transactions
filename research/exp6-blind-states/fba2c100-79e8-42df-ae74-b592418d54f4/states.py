import os
import shutil
import subprocess
from PIL import Image

DESKTOP_REL = os.path.join("home", "user", "Desktop")
VIDEO_NAME = "Interstellar Movie - Official Trailer.mp4"


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    desktop = os.path.join(out_dir, DESKTOP_REL)
    return os.path.join(desktop, VIDEO_NAME), os.path.join(desktop, "interstellar.png")


def _extract_frame(video_path, out_path, timestamp_sec, exact_seek=False):
    if exact_seek:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(max(0.0, timestamp_sec - 2.0)),
            "-i",
            video_path,
            "-ss",
            str(min(2.0, timestamp_sec)),
            "-frames:v",
            "1",
            out_path,
        ]
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(timestamp_sec),
            "-i",
            video_path,
            "-frames:v",
            "1",
            out_path,
        ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def correct_frame_at_120_5s_fast_seek(snapshot_dir, out_dir):
    video_path, png_path = _prepare(snapshot_dir, out_dir)
    _extract_frame(video_path, png_path, 120.5, exact_seek=False)


def correct_frame_at_120_5s_exact_seek(snapshot_dir, out_dir):
    video_path, png_path = _prepare(snapshot_dir, out_dir)
    _extract_frame(video_path, png_path, 120.5, exact_seek=True)
    img = Image.open(png_path)
    img.save(png_path, optimize=True)


def wrong_captured_at_0_seconds_start(snapshot_dir, out_dir):
    video_path, png_path = _prepare(snapshot_dir, out_dir)
    _extract_frame(video_path, png_path, 0.5, exact_seek=False)


def wrong_captured_at_12_05_seconds_decimal_error(snapshot_dir, out_dir):
    video_path, png_path = _prepare(snapshot_dir, out_dir)
    _extract_frame(video_path, png_path, 12.05, exact_seek=False)


def wrong_saved_in_home_instead_of_desktop(snapshot_dir, out_dir):
    video_path, _ = _prepare(snapshot_dir, out_dir)
    home_png = os.path.join(out_dir, "home", "user", "interstellar.png")
    _extract_frame(video_path, home_png, 120.5, exact_seek=False)


def wrong_saved_as_jpg_named_interstellar_jpg(snapshot_dir, out_dir):
    video_path, png_path = _prepare(snapshot_dir, out_dir)
    jpg_path = os.path.join(os.path.dirname(png_path), "interstellar.jpg")
    _extract_frame(video_path, jpg_path, 120.5, exact_seek=False)


def wrong_blank_black_image(snapshot_dir, out_dir):
    _, png_path = _prepare(snapshot_dir, out_dir)
    img = Image.new("RGB", (1920, 1080), (0, 0, 0))
    img.save(png_path)
