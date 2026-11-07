"""Cell edits and CSV output for the xlsx files in the Unit 2 workspace."""
import csv
import io
import os
import re
import zipfile

SHEET = "xl/worksheets/sheet1.xml"


def col_name(i):
    s = ""
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def col_index(col):
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def split_ref(ref):
    m = re.fullmatch(r"([A-Z]+)(\d+)", ref)
    return m.group(1), int(m.group(2))


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def csv_from_cells(cells):
    rows = {}
    for ref, v in cells.items():
        col, r = split_ref(ref)
        rows.setdefault(r, {})[col_index(col)] = v
    width = max((c for row in rows.values() for c in row), default=0)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for r in sorted(rows):
        w.writerow(_fmt(rows[r].get(c)) for c in range(1, width + 1))
    return buf.getvalue()


def write_csv(cells, path):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(csv_from_cells(cells))


def _set_value(body, ref, value):
    pat = re.compile(rb'(<c r="%s"[^>]*>\s*<v>)[^<]*(</v>)' % ref.encode())

    def repl(m):
        if b' t="' in m.group(1):
            raise ValueError(f"{ref} holds text, not a number")
        return m.group(1) + _fmt(value).encode() + m.group(2)

    text, n = pat.subn(repl, body)
    if n != 1:
        raise ValueError(f"{ref} is not a single numeric cell in sheet1.xml")
    return text


def set_number(path, ref, value):
    """Rewrite one existing numeric cell through a sibling temp file and an atomic replace."""
    tmp = path + ".otx-edit"
    try:
        with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                body = zin.read(info.filename)
                if info.filename == SHEET:
                    body = _set_value(body, ref, value)
                zout.writestr(info.filename, body)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
