import os
import shutil
from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor

REL_PATH = os.path.join("home", "user", "Desktop", "1_2.pptx")
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def _iter_text_shapes(shapes):
    for sh in shapes:
        if getattr(sh, "has_text_frame", False) and sh.text_frame.text.strip():
            yield sh
        if hasattr(sh, "shapes"):
            yield from _iter_text_shapes(sh.shapes)


def _set_shape_font_color(shape, rgb_hex, also_def_rpr=False):
    color = RGBColor.from_string(rgb_hex)
    for p in shape.text_frame.paragraphs:
        for r in p.runs:
            r.font.color.rgb = color
        if also_def_rpr:
            pPr = p._p.get_or_add_pPr()
            def_rpr = pPr.find(f"{{{A_NS}}}defRPr")
            if def_rpr is None:
                def_rpr = etree.SubElement(pPr, f"{{{A_NS}}}defRPr")
            for child in list(def_rpr):
                if child.tag.endswith("Fill"):
                    def_rpr.remove(child)
            solid = etree.SubElement(def_rpr, f"{{{A_NS}}}solidFill")
            srgb = etree.SubElement(solid, f"{{{A_NS}}}srgbClr")
            srgb.set("val", rgb_hex)


def correct_slide5_all_textboxes_yellow(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    for sh in _iter_text_shapes(prs.slides[4].shapes):
        _set_shape_font_color(sh, "FFFF00", also_def_rpr=False)
    prs.save(pptx_path)


def correct_slide5_yellow_runs_and_defrpr(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    for sh in _iter_text_shapes(prs.slides[4].shapes):
        _set_shape_font_color(sh, "FFFF00", also_def_rpr=True)
    prs.save(pptx_path)


def wrong_only_first_textbox_yellow(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    text_shapes = list(_iter_text_shapes(prs.slides[4].shapes))
    _set_shape_font_color(text_shapes[0], "FFFF00")
    prs.save(pptx_path)


def wrong_light_yellow_variation(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    for sh in _iter_text_shapes(prs.slides[4].shapes):
        _set_shape_font_color(sh, "FFFF99")
    prs.save(pptx_path)


def wrong_slide4_instead_of_slide5(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    for sh in _iter_text_shapes(prs.slides[3].shapes):
        _set_shape_font_color(sh, "FFFF00")
    prs.save(pptx_path)


def wrong_changed_shape_fill_instead_of_font(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    for sh in _iter_text_shapes(prs.slides[4].shapes):
        sh.fill.solid()
        sh.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0x00)
    prs.save(pptx_path)


def wrong_yellow_applied_to_all_slides(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    for sl in prs.slides:
        for sh in _iter_text_shapes(sl.shapes):
            _set_shape_font_color(sh, "FFFF00")
    prs.save(pptx_path)
