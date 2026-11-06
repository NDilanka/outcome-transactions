#!/bin/bash
# Computer-use method: drive the LibreOffice GUI with keystrokes inside the fork.
set -u
D=$((200 + FORK_NUM))
PROF="file:///tmp/lo_${FORK_ID}"
Xvfb :$D -screen 0 1280x800x24 -nolisten tcp >/dev/null 2>&1 & XP=$!
sleep 1.5
export DISPLAY=:$D SAL_USE_VCLPLUGIN=gen
openbox >/dev/null 2>&1 & OP=$!
soffice -env:UserInstallation=$PROF --calc --norestore --nologo budget.ods >/dev/null 2>&1 &
for i in $(seq 1 90); do sleep 1; W=$(xdotool search --name 'budget.ods' 2>/dev/null | tail -1); [ -n "$W" ] && break; done
sleep 4
xdotool windowactivate --sync $W; xdotool windowfocus --sync $W; sleep 0.5
if [ "${OTX_NULL:-0}" = 1 ]; then sleep 2; pkill -f "lo_${FORK_ID}"; sleep 2; kill $OP $XP 2>/dev/null; exit 0; fi
M0=$(stat -c %Y budget.ods)
xdotool key --delay 30 ctrl+Home Right Down
xdotool type --delay 30 5000
xdotool key Return ctrl+s
for i in $(seq 1 30); do sleep 0.5; [ "$(stat -c %Y budget.ods)" != "$M0" ] && break; done
sleep 1
pkill -f "lo_${FORK_ID}" ; sleep 2
soffice -env:UserInstallation=$PROF --headless --convert-to pdf --outdir out budget.ods >/dev/null 2>&1
mv out/budget.pdf out/q3.pdf
curl -s -x http://127.0.0.1:8899 -d "Q3 budget updated (gui)" http://reports.example.com/notify >/dev/null
kill $OP $XP 2>/dev/null
exit 0
