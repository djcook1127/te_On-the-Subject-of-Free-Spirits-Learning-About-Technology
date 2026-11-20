"""明示的に有効化した場合だけ共通MySQLで検証。作成したテストルームだけ後片付け。"""
import hashlib
import json
import os
import secrets
import sqlite3
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import local_rooms
import manage_shared_storage
import selection_rooms as selection
import shared_rooms
import test_selection_rooms as localtests


@unittest.skipUnless(os.environ.get("GIFTIA_RUN_SHARED_TESTS") == "1", "共通DBへの実行は明示指定時のみ")
class SharedSelectionIntegration(localtests.SelectionTests):
    def setUp(self):
        api = FastAPI()
        api.middleware("http")(local_rooms.local_origin_only)
        for route in selection.app.routes:
            if "/selection" in getattr(route, "path", ""):
                api.router.routes.append(route)
        api.include_router(shared_rooms.router)
        for name, value in [("rooms", shared_rooms), ("app", api)]:
            setting = patch.object(selection, name, value)
            setting.start()
            self.addCleanup(setting.stop)
        self.created_rooms = []
        self.addCleanup(self.clean_created_rooms)
        super().setUp()
        self.created_rooms.append(int(self.base.split("/")[3]))

    def clean_created_rooms(self):
        # このテストで作成したIDだけを対象にする。既存ルームには触らない。
        if self.created_rooms:
            with shared_rooms.connection() as con:
                for room_id in self.created_rooms:
                    con.execute("DELETE FROM consultations WHERE id=%s", (room_id,))

    def test_sqlite_copy_is_idempotent_remaps_ids_and_restores_own_cookie(self):
        source = Path(os.environ["GIFTIA_LOCAL_ROOMS_DB"])
        token = secrets.token_urlsafe(32)
        with closing(sqlite3.connect(source)) as con, con:
            con.executescript('''
                CREATE TABLE consultations(id INTEGER PRIMARY KEY,title TEXT,budget_total INTEGER,member_count INTEGER,deliver_by TEXT,organizer_id INTEGER);
                CREATE TABLE consultation_members(id INTEGER PRIMARY KEY,consultation_id INTEGER,nickname TEXT);
                CREATE TABLE local_member_sessions(token_hash TEXT PRIMARY KEY,room_id INTEGER,member_id INTEGER,expires_at INTEGER);
                CREATE TABLE selection_state(room_id INTEGER PRIMARY KEY,phase TEXT,decision TEXT);
                CREATE TABLE selection_notes(id INTEGER PRIMARY KEY,room_id INTEGER,member_id INTEGER,kind TEXT,text TEXT);
            ''')
            con.execute("INSERT INTO consultations VALUES (1,'移行確認ダミー',6000,3,'2026-11-24',11)")
            con.execute("INSERT INTO consultation_members VALUES (11,1,'移行主催者ダミー')")
            con.execute("INSERT INTO local_member_sessions VALUES (?,1,11,?)", (hashlib.sha256(token.encode()).hexdigest(), int(time.time()) + 3600))
            decision = {"mode": "single", "payment": "demo", "products": [localtests.PRODUCTS[0]]}
            con.execute("INSERT INTO selection_state VALUES (1,'decided',?)", (json.dumps(decision),))
            con.execute("INSERT INTO selection_notes VALUES (1,1,11,'好み','引継ぎ確認')")
        result = manage_shared_storage.copy_sqlite(source)
        new_id = result["copied"][0]["newRoomId"]
        self.created_rooms.append(new_id)
        again = manage_shared_storage.copy_sqlite(source)
        self.assertEqual(again["copied"], [])
        self.assertEqual(again["alreadyImported"][0]["newRoomId"], new_id)
        legacy = TestClient(selection.app)
        self.addCleanup(legacy.close)
        self.assertEqual(legacy.post("/api/rooms/1/migrate-session").status_code, 401)
        legacy.cookies.set(local_rooms.cookie_name(1), token, domain="testserver.local", path="/api/rooms/1")
        response = legacy.post("/api/rooms/1/migrate-session")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["room_path"], f"/rooms/{new_id}/select")
        state = legacy.get(f"/api/rooms/{new_id}/selection").json()
        self.assertTrue(state["me"]["isOrganizer"])
        self.assertEqual(state["storageSource"], "shared")
        self.assertEqual(state["notes"][0]["text"], "引継ぎ確認")
        self.assertEqual(state["decision"], decision)
        self.assertNotIn("token", json.dumps(state))
        with closing(sqlite3.connect(source)) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM consultations").fetchone()[0], 1)

    def test_shared_connection_failure_never_falls_back_to_sqlite(self):
        import pymysql
        with patch.object(shared_rooms, "_connect", side_effect=pymysql.OperationalError(2003, "private-host")):
            response = self.host.get(self.base)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private-host", response.text)


if __name__ == "__main__":
    unittest.main()
