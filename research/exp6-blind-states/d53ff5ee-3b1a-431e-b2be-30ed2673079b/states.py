import os
import shutil
import docx

REL_PATH = os.path.join("home", "user", "Desktop", "presentation_instruction_2023_Feb.docx")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def correct_all_document_text_lowercase(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    for p in doc.paragraphs:
        for r in p.runs:
            r.text = r.text.lower()
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.text = r.text.lower()
    doc.save(docx_path)


def correct_all_paragraphs_lowercase(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    for p in doc.paragraphs:
        for r in p.runs:
            r.text = r.text.lower()
    doc.save(docx_path)


def wrong_partial_only_first_allcaps_sentence(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    p7 = doc.paragraphs[7]
    target = "PREPARE A PRESENTATION ABOUT 2-3 MINUTES BEFORE YOUR PRESENTATION DATE."
    for r in p7.runs:
        if target in r.text:
            r.text = r.text.replace(target, target.lower())
    doc.save(docx_path)


def wrong_converted_all_text_to_uppercase(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    for p in doc.paragraphs:
        for r in p.runs:
            r.text = r.text.upper()
    doc.save(docx_path)


def wrong_converted_to_title_case(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    for p in doc.paragraphs:
        for r in p.runs:
            r.text = r.text.title()
    doc.save(docx_path)


def wrong_deleted_allcaps_paragraph(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    doc.paragraphs[7].text = ""
    doc.save(docx_path)


def wrong_saved_to_new_file_original_untouched(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    for p in doc.paragraphs:
        for r in p.runs:
            r.text = r.text.lower()
    alt_path = os.path.join(os.path.dirname(docx_path), "presentation_instruction_lowercase.docx")
    doc.save(alt_path)
