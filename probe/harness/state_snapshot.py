"""Snapshot an app's SQLite state, and measure whether a GET changes it.

A snapshot hashes every table in the app's database, one hash per table. Rows
are read in full and sorted, so a snapshot changes only when a table's content
changes. Housekeeping tables that move on every request (sessions, for
example) are excluded per app. The exclusion list is written next to the code,
so it can be reviewed.

A GET is state-changing when any non-excluded table differs between a snapshot
taken before it and one taken after it. The measurement always starts from a
freshly reset database. Otherwise a GET that marks a message as read would
look harmless the second time it is measured.

Databases are opened read-only. The apps use journal_mode DELETE, so a reader
does not see a half-written state.
"""

import hashlib
import sqlite3
from pathlib import Path

# Tables that record sessions or other per-request housekeeping. They are not
# business state. Keep this list short: a table that holds business data must
# not be excluded. The Vikunja list is empty until the live database is listed
# and checked (see probe/apps/vikunja/NOTES.md).
EXCLUDED_TABLES = {
    "webmail": frozenset({"sessions"}),
    "checkout": frozenset({"sessions"}),
    "psp": frozenset(),
    "vikunja": frozenset(),
}


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def _table_names(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows]


def snapshot(db_path, exclude=frozenset()):
    """Return {table: {"rows": n, "sha256": hex}} for every table not in exclude."""
    path = Path(db_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"no database at {path}")
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        result = {}
        for name in _table_names(conn):
            if name in exclude:
                continue
            cursor = conn.execute(f"SELECT * FROM {_quote(name)}")
            columns = [d[0] for d in cursor.description]
            rows = sorted(cursor.fetchall(), key=repr)
            digest = hashlib.sha256()
            digest.update(repr(columns).encode("utf-8", "surrogatepass"))
            for row in rows:
                digest.update(repr(row).encode("utf-8", "surrogatepass"))
                digest.update(b"\n")
            result[name] = {"rows": len(rows), "sha256": digest.hexdigest()}
        return result
    finally:
        conn.close()


def changed_tables(before, after):
    """Names of tables that were added, removed or changed between two snapshots."""
    names = sorted(set(before) | set(after))
    return [name for name in names if before.get(name) != after.get(name)]


def measure_get(db_path, exclude, url, reset, replay):
    """Measure one GET from a freshly reset state.

    reset() puts the app back to its seed state. replay(url) sends the GET and
    returns its HTTP status. The result says whether the GET changed any
    non-excluded table, and which tables changed.
    """
    reset()
    before = snapshot(db_path, exclude)
    status = replay(url)
    after = snapshot(db_path, exclude)
    changed = changed_tables(before, after)
    return {"url": url, "status": status, "state_changing": bool(changed), "changed_tables": changed}
