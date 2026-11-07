"""Excel COM sessions for the Office path. A session stops only the Excel processes that hold the files it
opened or claimed, so a user's own Excel window is never killed. win32com is imported when a session starts."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "unit1"))
from otx_win import image_pids, kill_pid, pid_alive, rm_holders  # noqa: E402
from xlsx_edit import col_name  # noqa: E402

EXCEL = "EXCEL.EXE"


def holder_pids(path):
    holders = rm_holders(path)
    if not isinstance(holders, list):
        return set()
    running = image_pids(EXCEL)
    return {pid for pid, _ in holders if pid in running}


def com_cells(ws):
    ur = ws.UsedRange
    cells = {}
    for r in range(ur.Row, ur.Row + ur.Rows.Count):
        for c in range(ur.Column, ur.Column + ur.Columns.Count):
            v = ws.Cells(r, c).Value
            if v is not None:
                cells[f"{col_name(c)}{r}"] = v
    return cells


class ExcelSession:
    def __init__(self):
        self.app = None
        self.pids = set()

    def __enter__(self):
        import win32com.client

        self.app = win32com.client.DispatchEx("Excel.Application")
        self.app.Visible = False
        self.app.DisplayAlerts = False
        return self

    def open(self, path):
        wb = self.app.Workbooks.Open(os.path.abspath(path))
        self.claim(path)
        return wb

    def claim(self, path):
        """Record the Excel pids that hold `path` while it is open, so exit stops exactly those."""
        self.pids |= holder_pids(path)

    def __exit__(self, *exc):
        try:
            if self.app is not None:
                self.app.Quit()
        finally:
            for pid in sorted(self.pids):
                if pid_alive(pid):
                    kill_pid(pid)
        return False
