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

from state_snapshot import EXCLUDED_TABLES, changed_tables, measure_get, semantic_digest, snapshot, volatile_column  # noqa: E402


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


def make_seeded(path, created, password, session_row, task_order=(1, 2, 3)):
    """A small app database. The tasks table has no primary key, so insert order is its scan order.

    Two builds that differ only in times, password hashes, salts and session rows must give the same
    semantic digest. task_order changes the insert order without changing the rows.
    """
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        PRAGMA journal_mode = DELETE;
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, created TEXT, updated TEXT);
        CREATE TABLE tasks (id INTEGER NOT NULL, title TEXT, done INTEGER NOT NULL, done_at TEXT, created TEXT, updated TEXT);
        CREATE TABLE sessions (id TEXT PRIMARY KEY, token TEXT, created_at TEXT);
        """
    )
    conn.execute("INSERT INTO users VALUES (1, 'alex', ?, ?, ?)", (password, created, created))
    titles = {1: "Renew passport", 2: "Pay council tax", 3: "Call dentist"}
    for task_id in task_order:
        conn.execute("INSERT INTO tasks VALUES (?, ?, 0, NULL, ?, ?)", (task_id, titles[task_id], created, created))
    conn.execute("INSERT INTO sessions VALUES (?, ?, ?)", (session_row, session_row, created))
    conn.commit()
    conn.close()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SemanticDigestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.first = str(root / "first.db")
        self.second = str(root / "second.db")
        make_seeded(self.first, created="2026-11-08 09:12:01", password="$2a$10$first-salt", session_row="sess-first")
        make_seeded(self.second, created="2026-11-08 10:40:55", password="$2a$10$second-salt", session_row="sess-second", task_order=(3, 1, 2))
        self.excluded = frozenset({"sessions"})

    def tearDown(self):
        self._tmp.cleanup()

    def test_builds_that_differ_only_in_times_salts_and_sessions_give_the_same_digest(self):
        self.assertNotEqual(file_sha(self.first), file_sha(self.second), "the files must differ, or the test proves nothing")
        self.assertEqual(semantic_digest(self.first, self.excluded)["sha256"], semantic_digest(self.second, self.excluded)["sha256"])

    def test_insert_order_does_not_change_a_tables_digest(self):
        self.assertEqual(
            semantic_digest(self.first, self.excluded)["tables"]["tasks"]["sha256"],
            semantic_digest(self.second, self.excluded)["tables"]["tasks"]["sha256"],
        )

    def test_a_business_change_changes_the_digest_and_names_the_table(self):
        before = semantic_digest(self.first, self.excluded)
        run_sql(self.first, "UPDATE tasks SET title = 'Renew passport (urgent)' WHERE id = 1")
        after = semantic_digest(self.first, self.excluded)
        self.assertNotEqual(before["sha256"], after["sha256"])
        self.assertNotEqual(before["tables"]["tasks"]["sha256"], after["tables"]["tasks"]["sha256"])
        self.assertEqual(before["tables"]["users"], after["tables"]["users"])

    def test_a_done_flag_change_counts(self):
        before = semantic_digest(self.first, self.excluded)
        run_sql(self.first, "UPDATE tasks SET done = 1 WHERE id = 2")
        self.assertNotEqual(before["sha256"], semantic_digest(self.first, self.excluded)["sha256"])

    def test_a_timestamp_only_change_is_ignored(self):
        before = semantic_digest(self.first, self.excluded)
        run_sql(self.first, "UPDATE tasks SET updated = '2031-01-01 00:00:00', done_at = '2031-01-01'")
        self.assertEqual(before["sha256"], semantic_digest(self.first, self.excluded)["sha256"])

    def test_a_password_change_is_ignored(self):
        before = semantic_digest(self.first, self.excluded)
        run_sql(self.first, "UPDATE users SET password = '$2a$10$other-salt'")
        self.assertEqual(before["sha256"], semantic_digest(self.first, self.excluded)["sha256"])

    def test_session_rows_are_left_out_entirely(self):
        before = semantic_digest(self.first, self.excluded)
        run_sql(self.first, "INSERT INTO sessions VALUES ('extra', 'extra', '2031-01-01')")
        after = semantic_digest(self.first, self.excluded)
        self.assertEqual(before["sha256"], after["sha256"])
        self.assertNotIn("sessions", after["tables"])

    def test_the_result_lists_tables_rows_and_what_was_left_out(self):
        result = semantic_digest(self.first, self.excluded)
        self.assertEqual(sorted(result["tables"]), ["tasks", "users"])
        self.assertEqual(result["tables"]["tasks"]["rows"], 3)
        self.assertEqual(result["excluded_tables"], ["sessions"])
        self.assertEqual(result["left_out_columns"], ["created", "done_at", "password", "updated"])

    def test_the_database_file_is_not_changed(self):
        before = file_sha(self.first)
        semantic_digest(self.first, self.excluded)
        self.assertEqual(file_sha(self.first), before)

    def test_a_missing_database_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            semantic_digest(str(Path(self._tmp.name) / "missing.db"), self.excluded)


class VolatileColumnTests(unittest.TestCase):
    def test_times_secrets_and_salts_are_volatile(self):
        for name in ("created", "Updated", "created_at", "done_at", "deletion_scheduled_at", "password", "password_reset_token", "api_token", "hash", "salt", "secret_key"):
            self.assertTrue(volatile_column(name), name)

    def test_business_columns_are_kept(self):
        for name in ("id", "title", "done", "position", "due_date", "project_id", "description", "updated_by_id"):
            self.assertFalse(volatile_column(name), name)


class ExclusionListTests(unittest.TestCase):
    def test_business_tables_are_never_excluded(self):
        self.assertEqual(EXCLUDED_TABLES["webmail"], frozenset({"sessions"}))
        self.assertEqual(EXCLUDED_TABLES["checkout"], frozenset({"sessions"}))
        for app, names in EXCLUDED_TABLES.items():
            for banned in ("message_meta", "orders", "carts", "quotes", "products", "drafts", "effects"):
                self.assertNotIn(banned, names, f"{app} must not exclude {banned}")


if __name__ == "__main__":
    unittest.main()
