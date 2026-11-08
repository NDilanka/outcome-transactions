"""Tests for state snapshots and GET effect measurement. Uses synthetic SQLite files only.

Run: python -m unittest discover -s probe/tests -p "test_*.py" -v
"""

import hashlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

from state_snapshot import EXCLUDED_TABLES, changed_tables, measure_get, snapshot  # noqa: E402


def make_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        PRAGMA journal_mode = DELETE;
        CREATE TABLE sessions (id TEXT PRIMARY KEY, last_seen INTEGER);
        CREATE TABLE message_meta (id TEXT PRIMARY KEY, seen INTEGER NOT NULL);
        CREATE TABLE contacts (id INTEGER PRIMARY KEY, name TEXT);
        INSERT INTO sessions VALUES ('s1', 100);
        INSERT INTO message_meta VALUES ('m1', 0), ('m2', 1);
        INSERT INTO contacts VALUES (1, 'Bob Ng');
        """
    )
    conn.commit()
    conn.close()


def run_sql(path, sql, params=()):
    conn = sqlite3.connect(path)
    conn.execute(sql, params)
    conn.commit()
    conn.close()


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self._tmp.name) / "app.db")
        make_db(self.db)

    def tearDown(self):
        self._tmp.cleanup()

    def test_snapshot_lists_every_table_with_row_counts(self):
        snap = snapshot(self.db)
        self.assertEqual(sorted(snap), ["contacts", "message_meta", "sessions"])
        self.assertEqual(snap["message_meta"]["rows"], 2)

    def test_identical_state_gives_identical_snapshots(self):
        self.assertEqual(snapshot(self.db), snapshot(self.db))
        self.assertEqual(changed_tables(snapshot(self.db), snapshot(self.db)), [])

    def test_excluded_tables_are_left_out(self):
        snap = snapshot(self.db, exclude=frozenset({"sessions"}))
        self.assertNotIn("sessions", snap)

    def test_snapshot_does_not_change_the_file(self):
        before = hashlib.sha256(Path(self.db).read_bytes()).hexdigest()
        snapshot(self.db)
        self.assertEqual(hashlib.sha256(Path(self.db).read_bytes()).hexdigest(), before)

    def test_missing_database_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            snapshot(str(Path(self.db).with_name("missing.db")))

    def test_changed_row_is_reported_by_table(self):
        before = snapshot(self.db)
        run_sql(self.db, "UPDATE message_meta SET seen = 1 WHERE id = 'm1'")
        self.assertEqual(changed_tables(before, snapshot(self.db)), ["message_meta"])

    def test_added_row_counts_as_a_change(self):
        before = snapshot(self.db)
        run_sql(self.db, "INSERT INTO contacts VALUES (2, 'Dana Lee')")
        self.assertEqual(changed_tables(before, snapshot(self.db)), ["contacts"])


class MeasureGetTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self._tmp.name) / "app.db")
        make_db(self.db)
        self.excluded = frozenset({"sessions"})

    def tearDown(self):
        self._tmp.cleanup()

    def _reset(self):
        # Seed state: m1 unread, session row present.
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE message_meta SET seen = 0 WHERE id = 'm1'")
        conn.execute("UPDATE sessions SET last_seen = 100")
        conn.commit()
        conn.close()

    def test_get_that_only_touches_sessions_is_not_state_changing(self):
        def replay(url):
            run_sql(self.db, "UPDATE sessions SET last_seen = 200")
            return 200

        result = measure_get(self.db, self.excluded, "/inbox", self._reset, replay)
        self.assertFalse(result["state_changing"])
        self.assertEqual(result["changed_tables"], [])
        self.assertEqual(result["status"], 200)

    def test_get_that_marks_a_message_read_is_state_changing(self):
        def replay(url):
            run_sql(self.db, "UPDATE message_meta SET seen = 1 WHERE id = 'm1'")
            return 200

        result = measure_get(self.db, self.excluded, "/message/m1", self._reset, replay)
        self.assertTrue(result["state_changing"])
        self.assertEqual(result["changed_tables"], ["message_meta"])

    def test_reset_is_needed_or_a_second_measurement_hides_the_change(self):
        def mark_read(url):
            run_sql(self.db, "UPDATE message_meta SET seen = 1 WHERE id = 'm1'")
            return 200

        first = measure_get(self.db, self.excluded, "/message/m1", self._reset, mark_read)
        second = measure_get(self.db, self.excluded, "/message/m1", lambda: None, mark_read)
        self.assertTrue(first["state_changing"])
        self.assertFalse(second["state_changing"], "without a reset the second GET looks harmless")

    def test_reset_runs_before_the_first_snapshot(self):
        order = []

        def reset():
            order.append("reset")
            self._reset()

        def replay(url):
            order.append("replay")
            return 204

        measure_get(self.db, self.excluded, "/x", reset, replay)
        self.assertEqual(order, ["reset", "replay"])


class ExclusionListTests(unittest.TestCase):
    def test_business_tables_are_never_excluded(self):
        self.assertEqual(EXCLUDED_TABLES["webmail"], frozenset({"sessions"}))
        self.assertEqual(EXCLUDED_TABLES["checkout"], frozenset({"sessions"}))
        for app, names in EXCLUDED_TABLES.items():
            for banned in ("message_meta", "orders", "carts", "quotes", "products", "drafts", "effects"):
                self.assertNotIn(banned, names, f"{app} must not exclude {banned}")


if __name__ == "__main__":
    unittest.main()
