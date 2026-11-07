"""Builds the real workspace for a Unit 2 run: budget.xlsx, notes.txt, and out/.keep.

budget.xlsx has a bold header row, 40 item rows, numeric Q1..Q3 in B..D, and the sheet name Q3.
The default mode takes the package of windows/unit1/base/budget.xlsx as the template and rewrites its
sheet, strings, styles, and sheet name. --excel builds the same layout through Excel COM.

  py -3 make_workspace.py <dir> [--excel]
"""
import os
import sys
import zipfile
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(os.path.dirname(HERE), "unit1", "base", "budget.xlsx")
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
HEADER = ["Item", "Q1", "Q2", "Q3"]
ROWS = 40
SHEET = "Q3"
STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<styleSheet xmlns="{NS}">'
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/><family val="2"/></font>'
    '<font><b/><sz val="11"/><name val="Calibri"/><family val="2"/></font></fonts>'
    '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
    '</styleSheet>'
).encode()


def item_values(i):
    """Q1..Q3 for item i. Item 0's Q1 is 1000, the starting value the unit 1 agent edit expects in B2."""
    q1 = 1000 if i == 0 else 200 + 7 * i
    return q1, 300 + 5 * i, 400 + 3 * i


def grid():
    cells = {f"{c}1": h for c, h in zip("ABCD", HEADER)}
    for i in range(ROWS):
        r = i + 2
        cells[f"A{r}"] = f"item{i}"
        cells.update({f"{c}{r}": v for c, v in zip("BCD", item_values(i))})
    return cells


def _sheet_xml():
    header = "".join(f'<c r="{c}1" s="1" t="s"><v>{k}</v></c>' for k, c in enumerate("ABCD"))
    rows = [f'<row r="1">{header}</row>']
    for i in range(ROWS):
        r = i + 2
        cells = [f'<c r="A{r}" t="s"><v>{len(HEADER) + i}</v></c>']
        cells += [f'<c r="{c}{r}"><v>{v}</v></c>' for c, v in zip("BCD", item_values(i))]
        rows.append(f'<row r="{r}">{"".join(cells)}</row>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<worksheet xmlns="{NS}" xmlns:r="{RNS}">'
            f'<dimension ref="A1:D{ROWS + 1}"/>'
            '<sheetViews><sheetView tabSelected="1" workbookViewId="0"/></sheetViews>'
            '<sheetFormatPr defaultRowHeight="15"/>'
            f'<sheetData>{"".join(rows)}</sheetData>'
            '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>'
            '</worksheet>').encode()


def _shared_strings():
    strings = HEADER + [f"item{i}" for i in range(ROWS)]
    items = "".join(f"<si><t>{escape(s)}</t></si>" for s in strings)
    n = len(strings)
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<sst xmlns="{NS}" count="{n}" uniqueCount="{n}">{items}</sst>').encode()


def _swap(body, old, new):
    if body.count(old) != 1:
        raise ValueError(f"expected exactly one {old!r} in the template part")
    return body.replace(old, new)


def _part(name, body):
    if name == "xl/worksheets/sheet1.xml":
        return _sheet_xml()
    if name == "xl/sharedStrings.xml":
        return _shared_strings()
    if name == "xl/styles.xml":
        return STYLES
    if name == "xl/workbook.xml":
        return _swap(body, b'name="Budget"', f'name="{SHEET}"'.encode())
    if name == "docProps/app.xml":
        return _swap(body, b"<vt:lpstr>Budget</vt:lpstr>", f"<vt:lpstr>{SHEET}</vt:lpstr>".encode())
    return body


def build_template(xlsx):
    with zipfile.ZipFile(TEMPLATE) as zin, zipfile.ZipFile(xlsx, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            zout.writestr(info.filename, _part(info.filename, zin.read(info.filename)))


def build_excel(xlsx):
    from excel_com import ExcelSession

    with ExcelSession() as xl:
        wb = xl.app.Workbooks.Add()
        ws = wb.Worksheets(1)
        ws.Name = SHEET
        for ref, v in grid().items():
            ws.Range(ref).Value = v
        ws.Range("A1:D1").Font.Bold = True
        wb.SaveAs(os.path.abspath(xlsx), 51)
        xl.claim(xlsx)


def build(ws, excel=False):
    xlsx = os.path.join(ws, "budget.xlsx")
    if os.path.exists(xlsx):
        raise FileExistsError(xlsx)
    os.makedirs(os.path.join(ws, "out"), exist_ok=True)
    if excel:
        build_excel(xlsx)
    else:
        build_template(xlsx)
    with open(os.path.join(ws, "notes.txt"), "w", encoding="utf-8", newline="") as f:
        f.write("meeting notes\n")
    with open(os.path.join(ws, "out", ".keep"), "w", encoding="utf-8", newline=""):
        pass


if __name__ == "__main__":
    build(os.path.abspath(sys.argv[1]), excel="--excel" in sys.argv[2:])
