"""ルームの保存・取得・入力チェック・失敗時の取り消しと既存検索を、班のDBを使わず自動確認するプログラムです。

実行: python -m unittest discover -s backend -p "test_*.py" -v
SQLiteはテスト内だけの代替。アプリの接続先は班のMySQLのまま。
"""
from contextlib import closing
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

# import時も環境ファイルを読まない。
with patch("dotenv.load_dotenv", return_value=False):
    import database
    import main
    import rooms


class TestCursor:
    def __init__(self, cursor, fail_on_member=False):
        self.cursor = cursor
        self.fail_on_member = fail_on_member

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cursor.close()

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    def execute(self, query, params=()):
        if self.fail_on_member and "INSERT INTO consultation_members" in query:
            raise rooms.pymysql.OperationalError(2006, "dummy failure")
        self.cursor.execute(query.replace("%s", "?"), params)
        return self.cursor.rowcount

    def fetchall(self):
        return [dict(row) for row in self.cursor.fetchall()]


class TestConnection:
    def __init__(self, filename, fail_on_member=False):
        self.conn = sqlite3.connect(filename)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.fail_on_member = fail_on_member

    def cursor(self):
        return TestCursor(self.conn.cursor(), self.fail_on_member)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


class RoomTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.filename = str(Path(self.temp.name) / "test.sqlite3")
        self.addCleanup(self.temp.cleanup)
        conn = sqlite3.connect(self.filename)
        conn.executescript("""
            CREATE TABLE consultations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                budget_total INTEGER NOT NULL CHECK(budget_total >= 1),
                member_count INTEGER NOT NULL CHECK(member_count >= 1),
                deliver_by TEXT NOT NULL, organizer_id INTEGER
            );
            CREATE TABLE consultation_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consultation_id INTEGER NOT NULL REFERENCES consultations(id),
                nickname TEXT NOT NULL, UNIQUE(consultation_id, nickname)
            );
        """)
        conn.close()
        self.connection_patch = patch("database.get_connection", side_effect=lambda: TestConnection(self.filename))
        self.connection_patch.start()
        self.addCleanup(self.connection_patch.stop)
        self.today_patch = patch("rooms.today_in_japan", return_value=date(2026, 11, 15))
        self.today_patch.start()
        self.addCleanup(self.today_patch.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.body = {"title": "ダミー送別ルーム", "budget_total": 4501, "member_count": 3, "deliver_by": "2026-11-24", "nickname": "ダミー幹事"}

    def count(self, table):
        # テスト内の固定名だけを使う。ユーザー入力は受け取らない。
        with closing(sqlite3.connect(self.filename)) as conn:
            return conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]

    def test_create_and_reload_from_new_client(self):
        response = self.client.post("/api/rooms", json=self.body)
        self.assertEqual(response.status_code, 201, response.text)
        room = response.json()
        self.assertEqual(room["price_per_person"], 1501)
        self.assertEqual(room["organizer_nickname"], "ダミー幹事")
        self.assertEqual(self.count("consultations"), 1)
        self.assertEqual(self.count("consultation_members"), 1)
        with TestClient(main.app) as second_client:
            loaded = second_client.get(f'/api/rooms/{room["room_id"]}')
        self.assertEqual(loaded.status_code, 200)
        self.assertEqual(loaded.json(), room)

    def test_independent_rooms(self):
        first = self.client.post("/api/rooms", json=self.body).json()
        second = self.client.post("/api/rooms", json={**self.body, "title": "別のダミールーム"}).json()
        self.assertNotEqual(first["room_id"], second["room_id"])
        self.assertEqual(self.client.get(f'/api/rooms/{first["room_id"]}').json()["title"], self.body["title"])

    def test_invalid_deadlines_do_not_write(self):
        for day in ["2026-11-14", "2026-11-21", "2026-11-22", "2026-11-23", "2027-03-22", "2028-01-04", "2027-02-30", "20261124", "2026-11-24T00:00:00", 1795478400]:
            with self.subTest(day=day):
                response = self.client.post("/api/rooms", json={**self.body, "deliver_by": day})
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.count("consultations"), 0)

    def test_national_and_substitute_holiday_rules(self):
        for day in [date(2026, 9, 22), date(2026, 5, 6), date(2027, 3, 22)]:
            with self.subTest(day=day), self.assertRaisesRegex(ValueError, "土日祝日"):
                rooms.validate_deadline(day, date(2026, 1, 1))
        self.assertEqual(rooms.validate_deadline(date(2026, 11, 24), date(2026, 11, 24)), date(2026, 11, 24))

    def test_invalid_fields_do_not_write(self):
        for change in [{"budget_total": 0}, {"member_count": 0}, {"member_count": -1}, {"member_count": 1.5}, {"budget_total": True}, {"budget_total": 2147483648}, {"title": "   "}, {"nickname": " "}, {"nickname": "あ" * 31}, {"title": "あ" * 101}, {"is_paid": True}]:
            with self.subTest(change=change):
                self.assertEqual(self.client.post("/api/rooms", json={**self.body, **change}).status_code, 422)
        self.assertEqual(self.count("consultations"), 0)

    def test_failed_member_insert_rolls_back_room(self):
        with patch("database.get_connection", side_effect=lambda: TestConnection(self.filename, fail_on_member=True)):
            response = self.client.post("/api/rooms", json=self.body)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("dummy failure", response.text)
        self.assertEqual(self.count("consultations"), 0)
        self.assertEqual(self.count("consultation_members"), 0)

    def test_sql_values_are_parameters(self):
        title = "ダミー'); SELECT 'dummy' --"
        response = self.client.post("/api/rooms", json={**self.body, "title": title})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.get(f'/api/rooms/{response.json()["room_id"]}').json()["title"], title)

    def test_missing_and_invalid_room(self):
        self.assertEqual(self.client.get("/api/rooms/999").status_code, 404)
        self.assertEqual(self.client.get("/api/rooms/0").status_code, 422)
        self.assertEqual(self.client.get("/api/rooms/abc").status_code, 422)

    def test_unavailable_storage_does_not_expose_detail(self):
        with patch("database.get_connection", side_effect=EnvironmentError("dummy connection detail")):
            response = self.client.get("/api/rooms/1")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("dummy connection detail", response.text)

    def test_existing_search_contract(self):
        dummy = {"product_id": "DUMMY-001", "category": "食品", "brand": "ダミーブランド", "product_name": "ダミーお菓子", "price": 3000, "rating": None, "review_count": 0}
        with patch("main.fetch_all", side_effect=[[{"n": 1}], [dummy]]) as fetch:
            response = self.client.get("/api/search", params={"q": "ダミー お菓子", "category": "食品", "indiv_wrap": True, "price_min": 1000, "price_max": 4500, "limit": 5})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"total": 1, "results": [{"id": "DUMMY-001", "category": "食品", "brand": "ダミーブランド", "name": "ダミーお菓子", "price": 3000, "rating": 0, "reviewCount": 0}]})
        count_query, count_params = fetch.call_args_list[0].args
        self.assertIn("stock > 0", count_query)
        self.assertNotIn("ダミー", count_query)
        self.assertEqual(count_params, ("%ダミー%",) * 3 + ("%お菓子%",) * 3 + ("食品", "%個包装%", 1000, 4500))
        self.assertEqual(fetch.call_args_list[1].args[1][-1], 5)

    def test_existing_search_empty_and_error(self):
        with patch("main.fetch_all", side_effect=[[{"n": 0}], []]):
            self.assertEqual(self.client.get("/api/search").json(), {"total": 0, "results": []})
        self.assertEqual(self.client.get("/api/search?limit=101").status_code, 422)


if __name__ == "__main__":
    unittest.main()
