set -e
export DEBIAN_FRONTEND=noninteractive
python3 -m venv /root/venv5 2>/dev/null || { apt-get install -y -q python3-venv python3-pip >/tmp/apt2.log 2>&1; python3 -m venv /root/venv5; }
/root/venv5/bin/pip install -q openpyxl python-docx python-pptx pillow odfpy xlrd numpy pypdf > /tmp/pip.log 2>&1 || { tail -5 /tmp/pip.log; exit 1; }
/root/venv5/bin/python -c "import openpyxl,docx,pptx,PIL,odf,xlrd,numpy,pypdf;print('libs ok')"
