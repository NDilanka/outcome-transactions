import os
import shutil
import docx

REL_PATH = os.path.join("home", "user", "Desktop", "Table_Of_Work_Effort_Instructions.docx")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def correct_add_table_5_rows_7_cols_at_end(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    doc.add_table(rows=5, cols=7)
    doc.save(docx_path)


def correct_add_table_5_rows_7_cols_at_cursor_paragraph(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    tbl = doc.add_table(rows=5, cols=7)
    doc.paragraphs[-1]._p.addprevious(tbl._tbl)
    doc.save(docx_path)


def wrong_swapped_7_rows_5_cols(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    doc.add_table(rows=7, cols=5)
    doc.save(docx_path)


def wrong_inserted_at_top_of_document(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    tbl = doc.add_table(rows=5, cols=7)
    doc.paragraphs[0]._p.addprevious(tbl._tbl)
    doc.save(docx_path)


def wrong_off_by_one_4_rows_7_cols(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    doc.add_table(rows=4, cols=7)
    doc.save(docx_path)


def wrong_deleted_existing_table(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    old_tbl = doc.tables[0]._tbl
    old_tbl.getparent().remove(old_tbl)
    doc.add_table(rows=5, cols=7)
    doc.save(docx_path)


def wrong_populated_table_not_empty(snapshot_dir, out_dir):
    docx_path = _prepare(snapshot_dir, out_dir)
    doc = docx.Document(docx_path)
    tbl = doc.add_table(rows=5, cols=7)
    headers = ["Name", "Role", "Y1", "Y2", "Y3", "Y4", "Total"]
    for idx, text in enumerate(headers):
        tbl.cell(0, idx).text = text
    doc.save(docx_path)
