#!/bin/bash
# Programmatic method: edit the document structure directly, render the PDF headless.
set -u
PROF="file:///tmp/lo_${FORK_ID}"
python3 "$OTX_HOME/odsedit.py" budget.ods B2 5000
soffice -env:UserInstallation=$PROF --headless --convert-to pdf --outdir out budget.ods >/dev/null 2>&1
mv out/budget.pdf out/q3.pdf
curl -s -x http://127.0.0.1:8899 -d "Q3 budget updated (direct)" http://reports.example.com/notify >/dev/null
