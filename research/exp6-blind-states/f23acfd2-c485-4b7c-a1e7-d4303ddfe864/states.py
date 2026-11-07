import os
import shutil
from lxml import etree
from pptx import Presentation

REL_PATH = os.path.join("home", "user", "Desktop", "69_4.pptx")
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def _set_bullet_char(shape, bullet_char="•", include_font=False):
    for p in shape.text_frame.paragraphs:
        pPr = p._p.get_or_add_pPr()
        for child in list(pPr):
            if child.tag.endswith(("buNone", "buChar", "buAutoNum", "buFont")):
                pPr.remove(child)
        if include_font:
            bu_font = etree.SubElement(pPr, f"{{{A_NS}}}buFont")
            bu_font.set("typeface", "OpenSymbol")
            bu_font.set("pitchFamily", "2")
            bu_font.set("charset", "2")
        bu_char = etree.SubElement(pPr, f"{{{A_NS}}}buChar")
        bu_char.set("char", bullet_char)


def correct_bullet_char_disc(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    body = prs.slides[0].shapes[1]
    _set_bullet_char(body, "•", include_font=True)
    prs.save(pptx_path)


def correct_bullet_char_simple(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    body = prs.slides[0].shapes[1]
    _set_bullet_char(body, "•", include_font=False)
    prs.save(pptx_path)


def wrong_bullet_on_title_only(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    title = prs.slides[0].shapes[0]
    _set_bullet_char(title, "•", include_font=True)
    prs.save(pptx_path)


def wrong_numbered_list_instead_of_bullet(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    body = prs.slides[0].shapes[1]
    for p in body.text_frame.paragraphs:
        pPr = p._p.get_or_add_pPr()
        for child in list(pPr):
            if child.tag.endswith(("buNone", "buChar", "buAutoNum")):
                pPr.remove(child)
        bu_num = etree.SubElement(pPr, f"{{{A_NS}}}buAutoNum")
        bu_num.set("type", "arabicPeriod")
    prs.save(pptx_path)


def wrong_literal_hyphen_kept_bunone(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    body = prs.slides[0].shapes[1]
    run = body.text_frame.paragraphs[0].runs[0]
    run.text = "- " + run.text
    prs.save(pptx_path)


def wrong_bullet_added_but_content_deleted(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    body = prs.slides[0].shapes[1]
    _set_bullet_char(body, "•", include_font=True)
    body.text_frame.paragraphs[0].runs[0].text = ""
    prs.save(pptx_path)


def wrong_bullet_on_both_title_and_content(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    _set_bullet_char(prs.slides[0].shapes[0], "•", include_font=True)
    _set_bullet_char(prs.slides[0].shapes[1], "•", include_font=True)
    prs.save(pptx_path)
