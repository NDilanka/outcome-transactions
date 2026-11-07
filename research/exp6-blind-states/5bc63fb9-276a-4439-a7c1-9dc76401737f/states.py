import json
import os
import re
import shutil
import docx
from docx.enum.text import WD_COLOR_INDEX

DESKTOP_REL = os.path.join("home", "user", "Desktop")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    desktop = os.path.join(out_dir, DESKTOP_REL)
    return os.path.join(desktop, "llm_answers.json"), os.path.join(desktop, "gemini_results.docx")


def _load_model_responses(json_path, model_key="GEMINI", keys=("declare_ans", "question_ans")):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    results = []
    for item in data.values():
        for section in item.values():
            for k in keys:
                if k in section and model_key in section[k]:
                    results.append(section[k][model_key])
    return results


def _add_highlighted_paragraph(doc, text, word="Iliad", highlight_color=WD_COLOR_INDEX.YELLOW):
    p = doc.add_paragraph()
    parts = re.split(f"({re.escape(word)})", text)
    for part in parts:
        if not part:
            continue
        run = p.add_run(part)
        if part == word and highlight_color is not None:
            run.font.highlight_color = highlight_color
    return p


def correct_six_gemini_paragraphs_yellow_highlight(snapshot_dir, out_dir):
    json_path, docx_path = _prepare(snapshot_dir, out_dir)
    responses = _load_model_responses(json_path, "GEMINI")
    doc = docx.Document()
    for resp in responses:
        _add_highlighted_paragraph(doc, resp, "Iliad", WD_COLOR_INDEX.YELLOW)
    doc.save(docx_path)


def correct_gemini_responses_case_insensitive_yellow(snapshot_dir, out_dir):
    json_path, docx_path = _prepare(snapshot_dir, out_dir)
    responses = _load_model_responses(json_path, "GEMINI")
    doc = docx.Document()
    for resp in responses:
        p = doc.add_paragraph()
        parts = re.split(r"(Iliad)", resp.strip(), flags=re.IGNORECASE)
        for part in parts:
            if not part:
                continue
            run = p.add_run(part)
            run.font.name = "Liberation Serif"
            if part.lower() == "iliad":
                run.font.highlight_color = WD_COLOR_INDEX.YELLOW
    doc.save(docx_path)


def wrong_extracted_gpt4_instead_of_gemini(snapshot_dir, out_dir):
    json_path, docx_path = _prepare(snapshot_dir, out_dir)
    responses = _load_model_responses(json_path, "GPT-4")
    doc = docx.Document()
    for resp in responses:
        _add_highlighted_paragraph(doc, resp, "Iliad", WD_COLOR_INDEX.YELLOW)
    doc.save(docx_path)


def wrong_no_highlight_on_iliad(snapshot_dir, out_dir):
    json_path, docx_path = _prepare(snapshot_dir, out_dir)
    responses = _load_model_responses(json_path, "GEMINI")
    doc = docx.Document()
    for resp in responses:
        doc.add_paragraph(resp)
    doc.save(docx_path)


def wrong_highlighted_green_instead_of_yellow(snapshot_dir, out_dir):
    json_path, docx_path = _prepare(snapshot_dir, out_dir)
    responses = _load_model_responses(json_path, "GEMINI")
    doc = docx.Document()
    for resp in responses:
        _add_highlighted_paragraph(doc, resp, "Iliad", WD_COLOR_INDEX.BRIGHT_GREEN)
    doc.save(docx_path)


def wrong_partial_only_declare_ans_extracted(snapshot_dir, out_dir):
    json_path, docx_path = _prepare(snapshot_dir, out_dir)
    responses = _load_model_responses(json_path, "GEMINI", keys=("declare_ans",))
    doc = docx.Document()
    for resp in responses:
        _add_highlighted_paragraph(doc, resp, "Iliad", WD_COLOR_INDEX.YELLOW)
    doc.save(docx_path)


def wrong_saved_in_home_instead_of_desktop(snapshot_dir, out_dir):
    json_path, docx_path = _prepare(snapshot_dir, out_dir)
    responses = _load_model_responses(json_path, "GEMINI")
    doc = docx.Document()
    for resp in responses:
        _add_highlighted_paragraph(doc, resp, "Iliad", WD_COLOR_INDEX.YELLOW)
    home_docx = os.path.join(out_dir, "home", "user", "gemini_results.docx")
    doc.save(home_docx)
