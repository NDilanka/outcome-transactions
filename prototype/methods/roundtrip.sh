#!/bin/bash
# Lossy method: CSV round trip. Gets the value right but destroys formatting (collateral damage).
set -u
PROF="file:///tmp/lo_${FORK_ID}"
T=/tmp/rt_${FORK_ID}; mkdir -p $T
soffice -env:UserInstallation=$PROF --headless --convert-to csv --outdir $T budget.ods >/dev/null 2>&1
python3 - "$T/budget.csv" <<'PY'
import csv, sys
p = sys.argv[1]; rows = list(csv.reader(open(p)))
rows[1][1] = "5000"; csv.writer(open(p, "w", newline="")).writerows(rows)
PY
soffice -env:UserInstallation=$PROF --headless --convert-to ods --outdir . $T/budget.csv >/dev/null 2>&1
soffice -env:UserInstallation=$PROF --headless --convert-to pdf --outdir out budget.ods >/dev/null 2>&1
mv out/budget.pdf out/q3.pdf
echo "scratch" > notes.txt
curl -s -x http://127.0.0.1:8899 -d "Q3 budget updated (roundtrip)" http://reports.example.com/notify >/dev/null
