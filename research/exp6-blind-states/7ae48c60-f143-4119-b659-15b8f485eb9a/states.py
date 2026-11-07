import os
import shutil
from pptx import Presentation
from pptx.util import Cm

REL_PATH = os.path.join("home", "user", "Desktop", "30_1.pptx")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def _find_by_name(slide, target_name):
    for sh in slide.shapes:
        if sh.name == target_name:
            return sh
    return None


def correct_exact_heights_all_picture_shapes(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    sl3 = prs.slides[2]
    for sh in sl3.shapes:
        if sh.name == "Google Shape;446;p18" or sh.shape_type == 13:
            sh.height = Cm(20)
    sl4 = prs.slides[3]
    _find_by_name(sl4, "Google Shape;466;p19").height = Cm(30)
    sl6 = prs.slides[5]
    _find_by_name(sl6, "Google Shape;684;p22").height = Cm(25)
    prs.save(pptx_path)


def correct_main_pictures_aspect_locked(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    targets = [
        (2, "Google Shape;446;p18", Cm(20)),
        (3, "Google Shape;466;p19", Cm(30)),
        (5, "Google Shape;684;p22", Cm(25)),
    ]
    for slide_idx, name, new_h in targets:
        sh = _find_by_name(prs.slides[slide_idx], name)
        ratio = sh.width / sh.height
        sh.height = new_h
        sh.width = int(round(new_h * ratio))
    for sh in prs.slides[2].shapes:
        if sh.shape_type == 13:
            sh.height = Cm(20)
    prs.save(pptx_path)


def wrong_changed_width_instead_of_height(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    for sh in prs.slides[2].shapes:
        if sh.name == "Google Shape;446;p18" or sh.shape_type == 13:
            sh.width = Cm(20)
    _find_by_name(prs.slides[3], "Google Shape;466;p19").width = Cm(30)
    _find_by_name(prs.slides[5], "Google Shape;684;p22").width = Cm(25)
    prs.save(pptx_path)


def wrong_heights_assigned_to_wrong_slides(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    for sh in prs.slides[2].shapes:
        if sh.name == "Google Shape;446;p18" or sh.shape_type == 13:
            sh.height = Cm(30)
    _find_by_name(prs.slides[3], "Google Shape;466;p19").height = Cm(25)
    _find_by_name(prs.slides[5], "Google Shape;684;p22").height = Cm(20)
    prs.save(pptx_path)


def wrong_partial_missed_slide_6(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    for sh in prs.slides[2].shapes:
        if sh.name == "Google Shape;446;p18" or sh.shape_type == 13:
            sh.height = Cm(20)
    _find_by_name(prs.slides[3], "Google Shape;466;p19").height = Cm(30)
    prs.save(pptx_path)


def wrong_off_by_one_slides_2_3_5(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    prs.slides[1].shapes[0].height = Cm(20)
    _find_by_name(prs.slides[2], "Google Shape;446;p18").height = Cm(30)
    prs.slides[4].shapes[0].height = Cm(25)
    prs.save(pptx_path)


def wrong_used_inches_instead_of_cm(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    inch_emu = 914400
    for sh in prs.slides[2].shapes:
        if sh.name == "Google Shape;446;p18" or sh.shape_type == 13:
            sh.height = 20 * inch_emu
    _find_by_name(prs.slides[3], "Google Shape;466;p19").height = 30 * inch_emu
    _find_by_name(prs.slides[5], "Google Shape;684;p22").height = 25 * inch_emu
    prs.save(pptx_path)
