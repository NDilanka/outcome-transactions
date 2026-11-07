import os
import shutil
from lxml import etree
from pptx import Presentation

REL_PATH = os.path.join("home", "user", "Desktop", "New_Club_Spring_2018_Training.pptx")
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def _set_paragraph_strike(paragraph, strike_val="sngStrike", also_def_rpr=False):
    for run in paragraph.runs:
        rPr = run._r.get_or_add_rPr()
        rPr.set("strike", strike_val)
    if also_def_rpr:
        pPr = paragraph._p.get_or_add_pPr()
        def_rpr = pPr.find(f"{{{A_NS}}}defRPr")
        if def_rpr is None:
            def_rpr = etree.SubElement(pPr, f"{{{A_NS}}}defRPr")
        def_rpr.set("strike", strike_val)


def correct_slide5_first_two_lines_strike(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    body = prs.slides[4].shapes[1]
    _set_paragraph_strike(body.text_frame.paragraphs[0], "sngStrike")
    _set_paragraph_strike(body.text_frame.paragraphs[1], "sngStrike")
    prs.save(pptx_path)


def correct_slide5_run_and_defrpr_strike(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    body = prs.slides[4].shapes[1]
    _set_paragraph_strike(body.text_frame.paragraphs[0], "sngStrike", also_def_rpr=True)
    _set_paragraph_strike(body.text_frame.paragraphs[1], "sngStrike", also_def_rpr=True)
    prs.save(pptx_path)


def wrong_only_first_line_struck(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    body = prs.slides[4].shapes[1]
    _set_paragraph_strike(body.text_frame.paragraphs[0], "sngStrike")
    prs.save(pptx_path)


def wrong_all_lines_on_slide5_struck(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    body = prs.slides[4].shapes[1]
    for p in body.text_frame.paragraphs:
        _set_paragraph_strike(p, "sngStrike")
    prs.save(pptx_path)


def wrong_struck_slide1_title_and_subtitle(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    for sh in prs.slides[0].shapes:
        if sh.has_text_frame:
            for p in sh.text_frame.paragraphs:
                _set_paragraph_strike(p, "sngStrike")
    prs.save(pptx_path)


def wrong_underlined_instead_of_strikethrough(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    body = prs.slides[4].shapes[1]
    for idx in (0, 1):
        for run in body.text_frame.paragraphs[idx].runs:
            rPr = run._r.get_or_add_rPr()
            rPr.set("u", "sng")
    prs.save(pptx_path)


def wrong_first_two_lines_deleted_instead_of_struck(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    body = prs.slides[4].shapes[1]
    body.text_frame.paragraphs[0].runs[0].text = ""
    body.text_frame.paragraphs[1].runs[0].text = ""
    prs.save(pptx_path)
