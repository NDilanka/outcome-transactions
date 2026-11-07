"""Runs one fork method under an in-process socket guard. Usage: fork_runner.py <method> <fork_dir>.

The first stdout line reports the guard as JSON. The guard only covers Python socket calls;
OS-level network isolation is not applied on Windows.
"""
import json
import os
import re
import runpy
import socket
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "unit1")]

import backend  # noqa: E402


def _blocked(*args, **kwargs):
    raise OSError("network disabled in fork")


def install_guard():
    socket.socket.connect = _blocked
    socket.socket.connect_ex = _blocked
    socket.create_connection = _blocked


def main():
    method, fork_dir = sys.argv[1], os.path.abspath(sys.argv[2])
    if not re.fullmatch(r"[a-z0-9_]+", method):
        raise SystemExit(f"bad method name: {method!r}")
    install_guard()
    office = "refused" if os.environ.get("OTX_REFUSE_OFFICE") == "1" else "allowed"
    if office == "refused":
        backend.refuse_office_com()
    print(json.dumps({"network_guard": "installed",
                      "scope": "in-process socket.connect, connect_ex, create_connection",
                      "os_isolation": "not applied on Windows",
                      "office_com": office}), flush=True)
    path = os.path.join(HERE, "methods", method + ".py")
    sys.argv = [path, fork_dir]
    runpy.run_path(path, run_name="__main__")


if __name__ == "__main__":
    main()
