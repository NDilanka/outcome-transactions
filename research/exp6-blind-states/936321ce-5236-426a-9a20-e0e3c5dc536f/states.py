import os
import shutil
import docx

REL_PATH = os.path.join("home", "user", "Desktop", "Graphemes_Sound_Letter_Patterns.docx")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def correct_exact_comma_split_table_in_place(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    target_ps = doc.paragraphs[4:9]
    rows_data = [p.text.split(",") for p in target_ps]
    tbl = doc.add_table(rows=5, cols=4)
    for r_idx, row in enumerate(rows_data):
        for c_idx, val in enumerate(row):
            tbl.cell(r_idx, c_idx).text = val
    target_ps[0]._p.addprevious(tbl._tbl)
    for p in target_ps:
        p._p.getparent().remove(p._p)
    doc.save(docx_path)


def correct_trimmed_comma_split_table_in_place(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    target_ps = doc.paragraphs[4:9]
    rows_data = [[cell.strip() for cell in p.text.split(",")] for p in target_ps]
    tbl = doc.add_table(rows=5, cols=4)
    for r_idx, row in enumerate(rows_data):
        for c_idx, val in enumerate(row):
            tbl.cell(r_idx, c_idx).text = val
    target_ps[0]._p.addprevious(tbl._tbl)
    for p in target_ps:
        p._p.getparent().remove(p._p)
    doc.save(docx_path)


def wrong_table_added_but_paragraphs_kept(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    target_ps = doc.paragraphs[4:9]
    rows_data = [p.text.split(",") for p in target_ps]
    tbl = doc.add_table(rows=5, cols=4)
    for r_idx, row in enumerate(rows_data):
        for c_idx, val in enumerate(row):
            tbl.cell(r_idx, c_idx).text = val
    target_ps[0]._p.addprevious(tbl._tbl)
    doc.save(docx_path)


def wrong_partial_missed_header_paragraph(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    target_ps = doc.paragraphs[5:9]
    rows_data = [p.text.split(",") for p in target_ps]
    tbl = doc.add_table(rows=4, cols=4)
    for r_idx, row in enumerate(rows_data):
        for c_idx, val in enumerate(row):
            tbl.cell(r_idx, c_idx).text = val
    target_ps[0]._p.addprevious(tbl._tbl)
    for p in target_ps:
        p._p.getparent().remove(p._p)
    doc.save(docx_path)


def wrong_table_appended_at_document_end(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    target_ps = doc.paragraphs[4:9]
    rows_data = [p.text.split(",") for p in target_ps]
    tbl = doc.add_table(rows=5, cols=4)
    for r_idx, row in enumerate(rows_data):
        for c_idx, val in enumerate(row):
            tbl.cell(r_idx, c_idx).text = val
    for p in target_ps:
        p._p.getparent().remove(p._p)
    doc.save(docx_path)


def wrong_transposed_4_rows_5_cols(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    target_ps = doc.paragraphs[4:9]
    rows_data = [p.text.split(",") for p in target_ps]
    tbl = doc.add_table(rows=4, cols=5)
    for r_idx in range(5):
        for c_idx in range(4):
            tbl.cell(c_idx, r_idx).text = rows_data[r_idx][c_idx]
    target_ps[0]._p.addprevious(tbl._tbl)
    for p in target_ps:
        p._p.getparent().remove(p._p)
    doc.save(docx_path)


def wrong_single_column_table_commas_not_split(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    target_ps = doc.paragraphs[4:9]
    tbl = doc.add_table(rows=5, cols=1)
    for r_idx, p in enumerate(target_ps):
        tbl.cell(r_idx, 0).text = p.text
    target_ps[0]._p.addprevious(tbl._tbl)
    for p in target_ps:
        p._p.getparent().remove(p._p)
    doc.save(docx_path)
