import os
import shutil
import docx

REL_PATH = os.path.join("home", "user", "Desktop", "CCCH9003_Tutorial_guidelines.docx")

SENTENCES = [
    "The purpose of the tutorial is to facilitate in-depth discussions on a more specific issue related to our lectures.",
    "Discussions play an important role in learning as it helps to deepen your understanding and develop your own ideas.",
    "Besides this, if you can explain something to others clearly, then you really understand it.",
    "If you can’t, you don’t!",
    "So, the discussion is also an effective way for you to examine how much you have understood in class.",
    "The harvest of our tutorials largely depends on your active participation and contribution.",
    "Thus, be proactive and talkative!",
]


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def correct_separate_paragraphs_with_empty_paragraphs(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    p0 = doc.paragraphs[0]
    style = p0.style
    p0.text = SENTENCES[0]
    anchor = doc.paragraphs[1]
    for s in SENTENCES[1:]:
        empty_p = anchor.insert_paragraph_before("", style=style)
        sent_p = anchor.insert_paragraph_before(s, style=style)
    doc.save(docx_path)


def correct_double_newlines_within_first_paragraph(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    doc.paragraphs[0].text = "\n\n".join(SENTENCES)
    doc.save(docx_path)


def wrong_single_newline_no_empty_line_space(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    doc.paragraphs[0].text = "\n".join(SENTENCES)
    doc.save(docx_path)


def wrong_missed_exclamation_sentence_boundary(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    merged = SENTENCES[:3] + [SENTENCES[3] + " " + SENTENCES[4]] + SENTENCES[5:]
    doc.paragraphs[0].text = "\n\n".join(merged)
    doc.save(docx_path)


def wrong_two_empty_lines_between_sentences(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    doc.paragraphs[0].text = "\n\n\n".join(SENTENCES)
    doc.save(docx_path)


def wrong_separated_last_paragraph_instead_of_first(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    last_p = doc.paragraphs[-1]
    parts = [s.strip() for s in last_p.text.split(". ") if s.strip()]
    last_p.text = ".\n\n".join(parts)
    doc.save(docx_path)


def wrong_kept_only_first_sentence_deleted_rest(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    doc.paragraphs[0].text = SENTENCES[0]
    doc.save(docx_path)
