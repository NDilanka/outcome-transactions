#!/bin/bash
# Derived method: reads the target from the user's notes, writes it to B2, renders the PDF.
# The output depends on an input this method reads but does not change.
set -u
PROF="file:///tmp/lo_${FORK_ID}"
T=$(sed -n 's/^target \([0-9]*\)$/\1/p' notes.txt)
python3 "$OTX_HOME/odsedit.py" budget.ods Q3 B2 "$T"
soffice -env:UserInstallation=$PROF --headless --convert-to pdf --outdir out budget.ods >/dev/null 2>&1
mv out/budget.pdf out/q3.pdf
curl -s -x http://127.0.0.1:8899 -d "Q3 budget updated (derived)" http://reports.example.com/notify >/dev/null
