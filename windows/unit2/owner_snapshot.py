"""Owner-mediated snapshot for Excel workspaces.

The workbook is opened in Excel, and Excel writes the copy with SaveCopyAs. That copy is the fork base, the same
as the Unit 1 snapshot taken from an open document. The real file is not saved, and its hashes are returned as the
change baseline for commit detection.
"""
import os
import shutil
import tempfile

import backend as B
import otx_win
from excel_com import ExcelSession


def owner_snapshot(real_dir, snap_dir):
    """Copy the tree, replace budget.xlsx with the owner's copy, and return the real tree's hashes."""
    real_xlsx = os.path.join(real_dir, "budget.xlsx")
    src = B.tree_hashes(real_dir)
    shutil.copytree(real_dir, snap_dir)
    tmp = tempfile.mkdtemp(prefix="otx-owner-")
    try:
        out = os.path.join(tmp, "budget.xlsx")
        with ExcelSession() as xl:
            wb = xl.open(real_xlsx)
            wb.SaveCopyAs(os.path.abspath(out))
            wb.Close(False)
        if B.tree_hashes(real_dir) != src:
            raise RuntimeError("real tree changed during owner snapshot")
        if otx_win.xlsx_cells(out) != otx_win.xlsx_cells(real_xlsx):
            raise RuntimeError("owner copy differs from the real file in cell values")
        shutil.move(out, os.path.join(snap_dir, "budget.xlsx"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return src
