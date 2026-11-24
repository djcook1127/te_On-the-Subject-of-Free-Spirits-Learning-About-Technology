"""SQL差分・ロールバック・移行の境界を実DBなしで確認。"""
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import pymysql
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import manage_shared_storage as migration
import shared_rooms
from selection_store import MySQLStore, SQLiteStore


class InviteTests(unittest.TestCase):
    def test_token_is_hashed_and_validation_checks_room_and_expiry(self):
        con = MagicMock()
        token = "a" * 43
        with patch.object(shared_rooms, "connection") as connect, patch.object(shared_rooms, "require_organizer"), patch.object(shared_rooms.secrets, "token_urlsafe", return_value=token):
            connect.return_value.__enter__.return_value = con
            self.assertEqual(shared_rooms.rotate_invite(7, MagicMock())["token"], token)
        _, params = con.execute.call_args.args
        self.assertNotIn(token, params)
        self.assertEqual(params[0], 7)
        self.assertEqual(len(params[1]), 64)
        con.execute.return_value.fetchone.return_value = None
        with self.assertRaises(HTTPException) as expired:
            shared_rooms.require_invite(con, 7, token)
        self.assertEqual(expired.exception.status_code, 403)
        sql, lookup = con.execute.call_args.args
        self.assertIn("expires_at>UNIX_TIMESTAMP()", sql)
        self.assertEqual(lookup, (7, params[1]))
        con.execute.return_value.fetchone.return_value = {"valid": 1}
        shared_rooms.require_invite(con, 7, token)

    def test_missing_invite_does_not_reach_database(self):
        con = MagicMock()
        with self.assertRaises(HTTPException) as missing:
            shared_rooms.require_invite(con, 7, None)
        self.assertEqual(missing.exception.status_code, 403)
        con.execute.assert_not_called()

    def test_http_join_sets_secure_cookie_only_after_invitation(self):
        api = FastAPI()
        api.include_router(shared_rooms.router)
        con = MagicMock()
        con.execute.return_value.lastrowid = 12
        token = "b" * 43
        with (
            TestClient(api, base_url="https://testserver") as browser,
            patch.object(shared_rooms, "connection") as connect,
            patch.object(shared_rooms, "room_row"),
            patch.object(shared_rooms, "session_member", return_value=None),
            patch.dict("os.environ", {"GIFTIA_SECURE_COOKIES": "1"}),
        ):
            connect.return_value.__enter__.return_value = con
            missing = browser.post("/api/rooms/7/members", json={"nickname": "ゲスト"})
            self.assertEqual(missing.status_code, 403)
            self.assertNotIn("set-cookie", missing.headers)
            con.execute.return_value.fetchone.return_value = None
            invalid = browser.post("/api/rooms/7/members", json={"nickname": "ゲスト", "invite_token": token})
            self.assertEqual(invalid.status_code, 403)
            self.assertNotIn("set-cookie", invalid.headers)
            con.execute.return_value.fetchone.return_value = {"valid": 1}
            valid = browser.post("/api/rooms/7/members", json={"nickname": "ゲスト", "invite_token": token})
            self.assertEqual(valid.status_code, 201)
            cookie = valid.headers["set-cookie"]
            for attribute in ("Secure", "HttpOnly", "Path=/api/rooms/7", "SameSite=strict"):
                self.assertIn(attribute, cookie)


class StoreTests(unittest.TestCase):
    def test_snapshot_batches_reads_and_keeps_values_bound(self):
        raw = MagicMock()
        cursor = raw.cursor.return_value.__enter__.return_value
        cursor.description = [("snapshot",)]
        cursor.fetchall.return_value = [{key: json.dumps(value) for key, value in {
            "own": [{"version": 1, "submitted": 1}], "personal": [{"product_id": "DUMMY", "reason": "説明", "gift": {"id": "DUMMY"}}],
            "published": [], "members": [], "own_votes": [], "totals": [], "old_notes": [], "old_comments": [], "room_comments": [],
        }.items()}]
        result = MySQLStore(raw).selection_snapshot(7, 8, False, "voting")
        self.assertEqual(result["personal"][0]["gift"], '{"id": "DUMMY"}')
        cursor.execute.assert_called_once()
        sql, values = cursor.execute.call_args.args
        self.assertIn("JSON_ARRAYAGG", sql)
        self.assertEqual(sql.count('%s'), len(values))
        self.assertIn(False, values)

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

    def test_votes_use_shared_room_lock_while_phase_changes_keep_exclusive_lock(self):
        store = MagicMock()
        store.execute.return_value.fetchone.return_value = {"id": 8}
        shared_rooms.room_row(store, 8, lock="shared")
        self.assertIn("LOCK IN SHARE MODE", store.execute.call_args.args[0])
        self.assertNotIn("FOR UPDATE", store.execute.call_args.args[0])
        shared_rooms.room_row(store, 8, lock=False)
        self.assertNotIn("FOR UPDATE", store.execute.call_args.args[0])

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
