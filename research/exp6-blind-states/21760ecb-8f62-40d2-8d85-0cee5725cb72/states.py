import os
import shutil
from lxml import etree
from pptx import Presentation

REL_PATH = os.path.join("home", "user", "Desktop", "Ch4 Video Effect.pptx")
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def _set_transition(slide, effect_tag="dissolve", attrs=None):
    sld = slide._element
    for child in list(sld):
        if child.tag.endswith("transition"):
            sld.remove(child)
    tr = etree.SubElement(sld, f"{{{P_NS}}}transition")
    if attrs:
        for k, v in attrs.items():
            tr.set(k, v)
    etree.SubElement(tr, f"{{{P_NS}}}{effect_tag}")


def correct_dissolve_transition_slide1(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    _set_transition(prs.slides[0], "dissolve")
    prs.save(pptx_path)


def correct_dissolve_transition_with_speed_attrs(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    _set_transition(prs.slides[0], "dissolve", {"spd": "med", "advClick": "1"})
    prs.save(pptx_path)


def wrong_fade_transition_slide1(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    _set_transition(prs.slides[0], "fade")
    prs.save(pptx_path)


def wrong_dissolve_on_slide2_instead(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    _set_transition(prs.slides[1], "dissolve")
    prs.save(pptx_path)


def wrong_dissolve_applied_to_all_slides(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    for sl in prs.slides:
        _set_transition(sl, "dissolve")
    prs.save(pptx_path)


def wrong_wipe_transition_slide1(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    _set_transition(prs.slides[0], "wipe")
    prs.save(pptx_path)


def wrong_dissolve_slide1_but_title_text_cleared(snapshot_dir, out_dir):
    pptx_path = _prepare(snapshot_dir, out_dir)
    prs = Presentation(pptx_path)
    _set_transition(prs.slides[0], "dissolve")
    prs.slides[0].shapes[0].text_frame.clear()
    prs.save(pptx_path)
