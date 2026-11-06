"""Create the starting workspace: budget.ods with a bold header row and notes.txt."""
import os, subprocess, sys
ws = sys.argv[1]
os.makedirs(ws, exist_ok=True)
rows = ['<table:table-row>' + ''.join(
    f'<table:table-cell table:style-name="hdr" office:value-type="string"><text:p>{h}</text:p></table:table-cell>'
    for h in ["Item", "Q1", "Q2", "Q3"]) + '</table:table-row>']
for i in range(40):
    cells = f'<table:table-cell office:value-type="string"><text:p>item{i}</text:p></table:table-cell>'
    for k in (3, 5, 7):
        v = i * k + k
        cells += f'<table:table-cell office:value-type="float" office:value="{v}"><text:p>{v}</text:p></table:table-cell>'
    rows.append(f'<table:table-row>{cells}</table:table-row>')
fods = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.spreadsheet">
<office:automatic-styles>
 <style:style style:name="hdr" style:family="table-cell"><style:text-properties fo:font-weight="bold"/></style:style>
</office:automatic-styles>
<office:body><office:spreadsheet><table:table table:name="Q3">
<table:table-column table:number-columns-repeated="4"/>
{"".join(rows)}
</table:table></office:spreadsheet></office:body></office:document>'''
open(os.path.join("/tmp", "budget.fods"), "w").write(fods)
subprocess.run(["soffice", "-env:UserInstallation=file:///tmp/lo_setup", "--headless", "--convert-to", "ods",
                "--outdir", ws, "/tmp/budget.fods"], check=True, capture_output=True)
open(os.path.join(ws, "notes.txt"), "w").write("meeting notes\n")
os.makedirs(os.path.join(ws, "out"), exist_ok=True)
open(os.path.join(ws, "out", ".keep"), "w").write("")
