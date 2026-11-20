"""SQL差分・ロールバック・移行の境界を実DBなしで確認。"""
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import pymysql
from fastapi import HTTPException

import manage_shared_storage as migration
import shared_rooms
from selection_store import MySQLStore, SQLiteStore


class StoreTests(unittest.TestCase):
    def test_mysql_values_are_bound_and_cursor_is_closed(self):
        raw = MagicMock()
        cursor = raw.cursor.return_value.__enter__.return_value
        cursor.description = [("name",)]
        cursor.fetchall.return_value = [{"name": "result"}]
        result = MySQLStore(raw).execute("SELECT name FROM selection_comments WHERE text=%s", ("x' OR 1=1",))
        self.assertEqual(result.fetchone(), {"name": "result"})
        cursor.execute.assert_called_once_with("SELECT name FROM selection_comments WHERE text=%s", ("x' OR 1=1",))
        raw.cursor.return_value.__exit__.assert_called_once()

    def test_sqlite_uses_same_parameter_contract(self):
        raw = sqlite3.connect(":memory:")
        self.addCleanup(raw.close)
        raw.execute("CREATE TABLE test(value TEXT)")
        store = SQLiteStore(raw)
        store.execute("INSERT INTO test VALUES (%s)", ("%s ? ' data",))
        self.assertEqual(store.execute("SELECT value FROM test").fetchone()[0], "%s ? ' data")

    def test_mysql_upserts_do_not_overwrite_submitted_or_version(self):
        store = MySQLStore(MagicMock())
        with patch.object(store, "execute") as execute, patch.object(store, "executemany") as many:
            store.ensure_state(8)
            self.assertNotIn("phase=", execute.call_args.args[0])
            store.add_submitters(8, [9])
            self.assertNotIn("submitted=", many.call_args.args[0])
            store.save_vote((8, 9, "P1", 3))
            self.assertIn("stars=VALUES(stars)", execute.call_args.args[0])

    def test_connection_commits_success_and_rolls_back_failure_without_details(self):
        raw = MagicMock()
        with patch.object(shared_rooms, "_connect", return_value=raw):
            with shared_rooms.connection():
                pass
        raw.commit.assert_called_once()
        raw.close.assert_called_once()
        raw.reset_mock()
        with patch.object(shared_rooms, "_connect", return_value=raw):
            with self.assertRaises(HTTPException) as error:
                with shared_rooms.connection():
                    raise pymysql.OperationalError(2003, "do-not-expose-host-password")
        raw.rollback.assert_called_once()
        raw.close.assert_called_once()
        self.assertEqual(error.exception.status_code, 503)
        self.assertNotIn("do-not-expose", error.exception.detail)

    def test_parent_room_is_locked_before_mutation(self):
        store = MagicMock()
        store.execute.return_value.fetchone.return_value = {"id": 8}
        self.assertEqual(shared_rooms.room_row(store, 8), {"id": 8})
        sql, params = store.execute.call_args.args
        self.assertIn("FOR UPDATE", sql)
        self.assertEqual(params, (8,))

    def test_cookie_namespace_is_distinct(self):
        import local_rooms
        self.assertNotEqual(shared_rooms.cookie_name(1), local_rooms.cookie_name(1))

    def test_migration_only_creates_new_tables(self):
        statements = migration.ddl_statements()
        self.assertEqual(len(statements), 8)
        self.assertTrue(all(s.startswith("CREATE TABLE IF NOT EXISTS ") for s in statements))
        self.assertFalse(any("CREATE TABLE IF NOT EXISTS consultations (" in s for s in statements))
        self.assertFalse(any("CREATE TABLE IF NOT EXISTS products" in s for s in statements))

    def test_migration_backup_does_not_modify_original(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.sqlite3"
            with closing(sqlite3.connect(source)) as con, con:
                con.execute("CREATE TABLE example(value INTEGER)")
                con.execute("INSERT INTO example VALUES (7)")
            backup = migration.backup_sqlite(source)
            self.assertNotEqual(backup, source)
            with closing(sqlite3.connect(backup)) as con:
                self.assertEqual(con.execute("SELECT value FROM example").fetchone()[0], 7)
            with closing(sqlite3.connect(source)) as con:
                self.assertEqual(con.execute("SELECT value FROM example").fetchone()[0], 7)


if __name__ == "__main__":
    unittest.main()
