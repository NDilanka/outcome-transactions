"""Windows helpers for the outcome-transaction experiments: free memory, file holders
(Restart Manager), Office lock files, process control, a window watchdog, and readers
for the parts of xlsx and docx files that the experiments check."""
import ctypes
import ctypes.wintypes as wt
import os
import re
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
import zipfile

import win32api
import win32gui
import win32process

WM_CLOSE = 0x0010
SS_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
PKG_NS = "{http://schemas.microsoft.com/office/2006/xmlPackage}"
HOME = os.path.expanduser("~")
PROFILE_NAMES = {os.path.basename(HOME), os.path.basename(win32api.GetShortPathName(HOME))}


def redact(text):
    """Window titles of other apps can show the profile path. The account name is not written to results."""
    for name in PROFILE_NAMES:
        text = re.sub(re.escape(name), "<user>", text, flags=re.IGNORECASE)
    return text


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD),
        ("ullTotalPhys", ctypes.c_uint64), ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64), ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64), ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


def free_mb():
    m = _MemoryStatusEx()
    m.dwLength = ctypes.sizeof(_MemoryStatusEx)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys >> 20


def wait_for_memory(min_mb, timeout_s):
    t0 = time.time()
    while free_mb() < min_mb:
        if time.time() - t0 > timeout_s:
            return False
        time.sleep(5)
    return True


class _UniqueProcess(ctypes.Structure):
    _fields_ = [("dwProcessId", wt.DWORD), ("ProcessStartTime", wt.FILETIME)]


class _RmProcessInfo(ctypes.Structure):
    _fields_ = [
        ("Process", _UniqueProcess),
        ("strAppName", ctypes.c_wchar * 256),
        ("strServiceShortName", ctypes.c_wchar * 64),
        ("ApplicationType", ctypes.c_int),
        ("AppStatus", wt.DWORD),
        ("TSSessionId", wt.DWORD),
        ("bRestartable", wt.BOOL),
    ]


_rm = ctypes.WinDLL("rstrtmgr")


def rm_holders(path):
    """Processes that Restart Manager reports as using the file: [[pid, app name]]."""
    session = wt.DWORD(0)
    key = ctypes.create_unicode_buffer(33)
    err = _rm.RmStartSession(ctypes.byref(session), 0, key)
    if err:
        return {"error": err}
    try:
        files = (ctypes.c_wchar_p * 1)(os.path.abspath(path))
        err = _rm.RmRegisterResources(session, 1, files, 0, None, 0, None)
        if err:
            return {"error": err}
        needed, count, reasons = wt.UINT(0), wt.UINT(0), wt.DWORD(0)
        _rm.RmGetList(session, ctypes.byref(needed), ctypes.byref(count), None, ctypes.byref(reasons))
        if needed.value == 0:
            return []
        arr = (_RmProcessInfo * needed.value)()
        count.value = needed.value
        err = _rm.RmGetList(session, ctypes.byref(needed), ctypes.byref(count), arr, ctypes.byref(reasons))
        if err:
            return {"error": err}
        return [[arr[i].Process.dwProcessId, arr[i].strAppName] for i in range(count.value)]
    finally:
        _rm.RmEndSession(session)


def lock_info(path):
    """Office's owner file ~$<name> next to the document, if present. Only size and readability are
    returned: the readable header holds the Windows account name, so it is not recorded."""
    d, b = os.path.split(os.path.abspath(path))
    lk = os.path.join(d, "~$" + b)
    if not os.path.exists(lk):
        return None
    try:
        with open(lk, "rb"):
            readable = True
    except PermissionError:
        readable = False
    return {"size": os.path.getsize(lk), "readable": readable}


def image_pids(image):
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    pids = set()
    for line in out.splitlines():
        parts = line.strip('"').split('","')
        if len(parts) > 1 and parts[1].isdigit():
            pids.add(int(parts[1]))
    return pids


def pid_alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


def kill_pid(pid):
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)


MAIN_CLASSES = {"XLMAIN", "XLDESK", "OpusApp"}
DIALOG_CLASSES = {"#32770"}
MAX_EVENTS = 200


class Watchdog(threading.Thread):
    """Samples every 50 ms: the foreground window, and every top-level window of one process.
    Counts foreground changes and window add/remove/visibility/minimize changes per phase, keeps
    the first MAX_EVENTS events, and closes dialogs (#32770) so a blocked COM call can return."""

    def __init__(self, pid, close=True, interval=0.05):
        super().__init__(daemon=True)
        self.pid = pid
        self.close = close
        self.interval = interval
        self.phase = "open"
        self.events = []
        self.counts = {}
        self._dialogs_seen = set()
        self._stop = threading.Event()

    def run(self):
        last_fg = None
        last_state = None
        while not self._stop.is_set():
            fg = win32gui.GetForegroundWindow()
            if fg != last_fg:
                last_fg = fg
                self._event("foreground", fg, fg_pid=self._pid_of(fg))
            wins = []
            win32gui.EnumWindows(self._collect, wins)
            state = frozenset(self._state(h) for h in wins)
            if last_state is not None:
                for s in sorted(state ^ last_state):
                    kind = "window-appeared" if s in state else "window-gone"
                    self._event(kind, s[0], cls=s[1], visible=s[2], iconic=s[3])
            last_state = state
            for h in wins:
                if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) in DIALOG_CLASSES \
                        and h not in self._dialogs_seen:
                    self._dialogs_seen.add(h)
                    self._dialog(h)
            time.sleep(self.interval)

    def stop(self):
        self._stop.set()
        self.join(timeout=5)

    def _pid_of(self, hwnd):
        try:
            return win32process.GetWindowThreadProcessId(hwnd)[1]
        except Exception:
            return None

    def _collect(self, hwnd, acc):
        if self._pid_of(hwnd) == self.pid:
            acc.append(hwnd)
        return True

    def _state(self, h):
        return (h, win32gui.GetClassName(h), bool(win32gui.IsWindowVisible(h)), bool(win32gui.IsIconic(h)))

    def _event(self, kind, hwnd, **extra):
        key = (self.phase, kind)
        self.counts[key] = self.counts.get(key, 0) + 1
        if len(self.events) < MAX_EVENTS:
            ev = {"phase": self.phase, "kind": kind, "hwnd": hwnd, "class": win32gui.GetClassName(hwnd)
                  if hwnd and kind != "window-gone" else extra.get("cls"), **{k: v for k, v in extra.items() if k != "cls"}}
            if kind in ("foreground", "window-appeared"):
                ev["title"] = win32gui.GetWindowText(hwnd)[:80]
            self.events.append(ev)

    def _dialog(self, hwnd):
        texts = []

        def child(h, _):
            t = win32gui.GetWindowText(h)
            if t:
                texts.append(t)
            return True

        try:
            win32gui.EnumChildWindows(hwnd, child, None)
        except Exception:
            pass
        key = ("dialog", self.phase)
        self.counts[key] = self.counts.get(key, 0) + 1
        self.events.append({"phase": self.phase, "kind": "dialog", "class": win32gui.GetClassName(hwnd),
                            "title": win32gui.GetWindowText(hwnd)[:80], "texts": texts[:12]})
        if self.close:
            win32gui.PostMessage(hwnd, WM_CLOSE, 0, 0)


def force_foreground(hwnd):
    """Make hwnd the foreground window. A background script cannot take focus on its own, so the
    input queue of the current foreground thread is attached for the call. Returns True on success."""
    user32 = ctypes.windll.user32
    fg = win32gui.GetForegroundWindow()
    fg_tid = win32process.GetWindowThreadProcessId(fg)[0]
    me = ctypes.windll.kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(fg_tid, me, True)
    try:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        user32.AttachThreadInput(fg_tid, me, False)
    time.sleep(0.3)
    return win32gui.GetForegroundWindow() == hwnd


def foreground_desc():
    h = win32gui.GetForegroundWindow()
    try:
        pid = win32process.GetWindowThreadProcessId(h)[1]
    except Exception:
        pid = None
    return {"hwnd": h, "class": win32gui.GetClassName(h) if h else None,
            "title": win32gui.GetWindowText(h)[:80] if h else None, "pid": pid}


def xlsx_cells(path):
    """{ref: value} for the first worksheet. Numbers are floats, text is str."""
    with zipfile.ZipFile(path) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(SS_NS + "si"):
                strings.append("".join(t.text or "" for t in si.iter(SS_NS + "t")))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    out = {}
    for c in sheet.iter(SS_NS + "c"):
        v, t = c.find(SS_NS + "v"), c.get("t")
        if t == "s" and v is not None:
            val = strings[int(v.text)]
        elif t == "inlineStr":
            val = "".join(x.text or "" for x in c.iter(SS_NS + "t"))
        elif v is not None and v.text is not None:
            val = v.text if t in ("str", "e") else float(v.text)
        else:
            continue
        out[c.get("r")] = val
    return out


def docx_paras(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    return ["".join(t.text or "" for t in p.iter(W_NS + "t")) for p in root.iter(W_NS + "p")]


def flat_opc_paras(path):
    """Paragraph texts from a Word flat OPC file (Document.WordOpenXML)."""
    root = ET.parse(path).getroot()
    for part in root.iter(PKG_NS + "part"):
        if part.get(PKG_NS + "name") == "/word/document.xml":
            data = part.find(PKG_NS + "xmlData")
            return ["".join(t.text or "" for t in p.iter(W_NS + "t")) for p in data.iter(W_NS + "p")]
    raise ValueError("no /word/document.xml part in " + path)
