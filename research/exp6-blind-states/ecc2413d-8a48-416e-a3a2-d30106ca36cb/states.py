import os
import shutil
import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

REL_PATH = os.path.join("home", "user", "Desktop", "Sample_Statutory_Declaration.docx")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def _make_page_break_run():
    r = OxmlElement("w:r")
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "page")
    r.append(br)
    return r


def correct_new_page_break_paragraph_after_page1(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    p5 = doc.paragraphs[5]
    new_p = p5.insert_paragraph_before("")
    new_p._p.append(_make_page_break_run())
    doc.save(docx_path)


def correct_page_break_appended_to_page1_end(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    p4 = doc.paragraphs[4]
    p4._p.append(_make_page_break_run())
    doc.save(docx_path)


def wrong_blank_page_before_first_page(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    p0 = doc.paragraphs[0]
    new_p = p0.insert_paragraph_before("")
    new_p._p.append(_make_page_break_run())
    doc.save(docx_path)


def wrong_blank_page_at_end_of_document(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    doc.add_page_break()
    doc.save(docx_path)


def wrong_line_break_instead_of_page_break(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    p5 = doc.paragraphs[5]
    new_p = p5.insert_paragraph_before("")
    r = OxmlElement("w:r")
    br = OxmlElement("w:br")
    r.append(br)
    new_p._p.append(r)
    doc.save(docx_path)


def wrong_blank_page_after_second_page(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    p70 = doc.paragraphs[70]
    p70._p.append(_make_page_break_run())
    doc.save(docx_path)


def wrong_first_page_content_deleted(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    for idx in range(5):
        doc.paragraphs[idx].text = ""
    doc.save(docx_path)
