"""Snapshot and fork runner for the Windows backend.

A fork is a copy of the snapshot, run in a subprocess with a private temp folder inside the fork,
proxy variables pointed at a dead port, and an in-process socket guard. The guard is not OS-level
isolation: on Windows nothing stops the process from opening sockets below Python.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, "fork_runner.py")
SCRATCH = ".otx-scratch"
PROXY = "http://127.0.0.1:9"
SNAPSHOT_METHOD = "copy (NTFS has no block clone)"
ISOLATION = "in-process socket guard only; OS-level network isolation not applied on Windows"
ENV_KEYS = ("TEMP", "TMP", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "PYTHONDONTWRITEBYTECODE",
            "OTX_REFUSE_OFFICE")
PROXY_NAMES = ("http_proxy", "https_proxy", "all_proxy", "no_proxy")


def refuse_office_com():
    """Make Office COM dispatch raise in this process. win32com is imported here, not at module import."""
    import win32com.client

    def refused(*args, **kwargs):
        raise RuntimeError("Office COM is disabled for this run")

    win32com.client.Dispatch = refused
    win32com.client.DispatchEx = refused


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_hashes(root):
    out = {}
    for dp, dns, fns in os.walk(root):
        if os.path.relpath(dp, root) == "." and SCRATCH in dns:
            dns.remove(SCRATCH)
        for fn in fns:
            full = os.path.join(dp, fn)
            out[os.path.relpath(full, root).replace(os.sep, "/")] = _sha256(full)
    return out


def changed_paths(before, after):
    b, a = tree_hashes(before), tree_hashes(after)
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def _tree_bytes(root):
    if not os.path.isdir(root):
        return 0
    return sum(os.path.getsize(os.path.join(dp, fn)) for dp, _, fns in os.walk(root) for fn in fns)


def divergence_bytes(before, after):
    return sum(os.path.getsize(os.path.join(after, k)) for k in changed_paths(before, after)
               if os.path.exists(os.path.join(after, k)))


def snapshot(real_dir, snap_dir):
    """Copy the live tree and return its hashes. Raises if the source changed during the copy."""
    src = tree_hashes(real_dir)
    shutil.copytree(real_dir, snap_dir)
    dst = tree_hashes(snap_dir)
    if dst != src:
        moved = sorted(k for k in set(src) | set(dst) if src.get(k) != dst.get(k))
        raise RuntimeError(f"snapshot differs from source: {moved}")
    return dst


def fork_env(scratch, refuse_office=False):
    env = {k: v for k, v in os.environ.items() if k.lower() not in PROXY_NAMES}
    env.update(TEMP=scratch, TMP=scratch, HTTP_PROXY=PROXY, HTTPS_PROXY=PROXY, ALL_PROXY=PROXY,
               NO_PROXY="", PYTHONDONTWRITEBYTECODE="1", OTX_REFUSE_OFFICE="1" if refuse_office else "0")
    return env


def _run_runner(method, fork_dir, env, timeout_s):
    cmd = [sys.executable, RUNNER, method, fork_dir]
    try:
        p = subprocess.run(cmd, cwd=fork_dir, env=env, capture_output=True, text=True, timeout=timeout_s)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -9, "", f"timeout after {timeout_s}s"


def _guard_status(out):
    first = out.splitlines()[0] if out.strip() else ""
    try:
        st = json.loads(first)
    except ValueError:
        return {"network_guard": "missing"}
    return st if isinstance(st, dict) and "network_guard" in st else {"network_guard": "missing"}


def run_fork(method, snap_dir, fork_dir, timeout_s=240, refuse_office=False):
    fork_dir = os.path.abspath(fork_dir)
    if os.path.exists(fork_dir):
        raise FileExistsError(fork_dir)
    shutil.copytree(snap_dir, fork_dir)
    scratch = os.path.join(fork_dir, SCRATCH)
    os.makedirs(scratch)
    env = fork_env(scratch, refuse_office)
    t0 = time.monotonic()
    rc, out, err = _run_runner(method, fork_dir, env, timeout_s)
    return dict(method=method, rc=rc, seconds=round(time.monotonic() - t0, 2), network=_guard_status(out),
                env={k: env[k] for k in ENV_KEYS}, divergence_bytes=divergence_bytes(snap_dir, fork_dir),
                scratch_bytes=_tree_bytes(scratch), stdout_tail=out[-400:], stderr_tail=err[-800:])
