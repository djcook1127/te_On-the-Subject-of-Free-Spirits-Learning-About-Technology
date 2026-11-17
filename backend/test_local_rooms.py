"""名前参加と個人候補入力の分離を一時SQLiteだけで検証する。"""
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import local_rooms as local


class LocalParticipationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        setting = patch.dict(os.environ, {"GIFTIA_LOCAL_ROOMS_DB": str(Path(self.temp.name) / "rooms.sqlite3")})
        setting.start()
        self.addCleanup(setting.stop)
        today = patch("room_contract.today_in_japan", return_value=date(2026, 11, 17))
        today.start()
        self.addCleanup(today.stop)
        self.client = self.other_client()
        self.body = {"title": "架空の送別ルーム", "nickname": "幹事役", "budget_total": 6001,
                     "member_count": 3, "deliver_by": "2026-11-24"}
        response = self.client.post("/api/rooms", json=self.body)
        self.assertEqual(response.status_code, 201)
        self.room_id = response.json()["room_id"]
        self.base = f"/api/rooms/{self.room_id}"

    def other_client(self):
        client = TestClient(local.app)
        self.addCleanup(client.close)
        return client

    def join(self, client, name="参加者B"):
        return client.post(self.base + "/members", json={"nickname": name})

    def put(self, client, slots, version=0, **kwargs):
        return client.put(self.base + "/candidate-draft", json={"version": version, "slots": slots}, **kwargs)

    def test_creator_is_member_cookie_is_private_and_reload_persists(self):
        me = self.client.get(self.base + "/me").json()
        self.assertEqual(me["name"], "幹事役")
        room = self.client.get(self.base).json()
        self.assertEqual(room["price_per_person"], 2001)
        self.assertTrue(room["local_preview"])
        self.assertNotIn("token", room)
        with local.connection() as con:
            session = con.execute("SELECT token_hash FROM local_member_sessions").fetchone()
            token = self.client.cookies.get(local.cookie_name(self.room_id))
            self.assertTrue(session["token_hash"] != token)
        response = self.client.post("/api/rooms", json={**self.body, "title": "別室"})
        header = response.headers["set-cookie"].lower()
        self.assertIn("httponly", header)
        self.assertIn("samesite=strict", header)
        self.assertIn("path=/api/rooms/", header)
        # 再読み込みは同じCookieで本人が復元される。参加者リストは返さない。
        draft = self.client.get(self.base + "/candidate-draft").json()
        self.assertEqual(draft["member"], me)
        self.assertEqual(draft["demoMembers"], [])

    def test_join_is_idempotent_and_duplicate_name_is_not_identity_recovery(self):
        second, third = self.other_client(), self.other_client()
        response = self.join(second, "  参加者B  ")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "参加者B")
        self.assertEqual(self.join(second).status_code, 200)
        self.assertEqual(self.join(second, "別名").status_code, 409)
        self.assertEqual(self.join(third).status_code, 409)
        self.assertEqual(third.get(self.base + "/me").status_code, 401)

    def test_product_and_hint_are_private_and_persisted(self):
        second = self.other_client()
        self.assertEqual(self.join(second).status_code, 201)
        slots = [{"kind": "product", "productId": "DEMO-001", "reason": "休日に使ってほしい"},
                 {"kind": "hint", "text": "コーヒーが好きそう"}]
        saved = self.put(self.client, slots)
        self.assertEqual(saved.status_code, 200)
        own = self.client.get(self.base + "/candidate-draft").json()
        other = second.get(self.base + "/candidate-draft").json()
        self.assertEqual(own["version"], 1)
        self.assertEqual(own["slots"][0]["gift"]["name"], "ゆっくり過ごすマグカップ")
        self.assertEqual(other["slots"], [])
        self.assertNotIn("コーヒー", str(other))
        self.assertTrue(own["localParticipation"])

    def test_no_session_or_spoofed_member_cannot_read_or_write(self):
        stranger = self.other_client()
        fake = {"X-Demo-Member": "1"}
        self.assertEqual(stranger.get(self.base + "/candidate-draft?member=1", headers=fake).status_code, 401)
        self.assertEqual(self.put(stranger, [], headers=fake).status_code, 401)
        second = self.other_client()
        self.join(second)
        self.put(self.client, [{"kind": "hint", "text": "幹事だけの下書き"}])
        own = second.get(self.base + "/candidate-draft?member=1", headers=fake).json()
        self.assertEqual(own["slots"], [])
        self.assertEqual(own["member"]["name"], "参加者B")

    def test_session_cannot_be_used_for_other_room_and_expired_session_is_rejected(self):
        other_room = self.client.post("/api/rooms", json=self.body).json()["room_id"]
        token = self.client.cookies.get(local.cookie_name(self.room_id))
        stranger = self.other_client()
        stranger.cookies.set(local.cookie_name(other_room), token)
        self.assertEqual(stranger.get(f"/api/rooms/{other_room}/me").status_code, 401)
        with local.connection() as con:
            con.execute("UPDATE local_member_sessions SET expires_at=0 WHERE room_id=?", (self.room_id,))
        self.assertEqual(self.client.get(self.base + "/me").status_code, 401)

    def test_invalid_join_and_room_inputs_are_rejected(self):
        stranger = self.other_client()
        for body in ({"nickname": " "}, {"nickname": "あ" * 31}, {"nickname": "A", "id": 1}):
            self.assertEqual(stranger.post(self.base + "/members", json=body).status_code, 422)
        for changes in ({"deliver_by": "2026-11-23"}, {"member_count": 0}, {"budget_total": True}):
            self.assertEqual(self.client.post("/api/rooms", json={**self.body, **changes}).status_code, 422)
        self.assertEqual(self.client.get("/api/rooms/999/me").status_code, 404)
        self.assertEqual(self.client.get("/api/rooms/0/me").status_code, 422)

    def test_three_slots_duplicate_and_spoofed_product_boundaries(self):
        valid = [{"kind": "hint", "text": f"手掛かり{i}"} for i in range(3)]
        self.assertEqual(self.put(self.client, valid).status_code, 200)
        invalid = [valid + [{"kind": "hint", "text": "4枠目"}], [{"kind": "hint", "text": " "}]]
        for slots in invalid:
            self.assertEqual(self.put(self.client, slots, version=1).status_code, 422)
        product = {"kind": "product", "productId": "DEMO-001", "reason": ""}
        self.assertEqual(self.put(self.client, [product, product], version=1).status_code, 400)
        self.assertEqual(self.put(self.client, [{**product, "productId": "unknown"}], version=1).status_code, 400)
        self.assertEqual(self.put(self.client, [{**product, "gift": {"price": 1}}], version=1).status_code, 422)
        self.assertEqual(self.client.get(self.base + "/candidate-draft").json()["slots"], valid)

    def test_same_version_has_one_winner_and_empty_save_removes_own_slots(self):
        def save(text):
            return self.put(self.client, [{"kind": "hint", "text": text}]).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(save, ["案A", "案B"]))
        self.assertEqual(sorted(statuses), [200, 409])
        self.assertEqual(self.put(self.client, [], version=1).json()["slots"], [])

    def test_same_name_concurrent_join_has_one_winner(self):
        clients = [self.other_client(), self.other_client()]
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda client: self.join(client).status_code, clients))
        self.assertEqual(sorted(statuses), [201, 409])

    def test_foreign_origin_cannot_write_and_cookie_cors_is_limited(self):
        headers = {"Origin": "http://127.0.0.1:3300", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "Content-Type"}
        response = self.client.options(self.base + "/members", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-credentials"], "true")
        self.assertEqual(self.join(self.other_client()).status_code, 201)
        response = self.client.put(self.base + "/candidate-draft", json={"version": 0, "slots": []}, headers={"Origin": "https://example.com"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get(self.base).headers["cache-control"], "no-store")

    def test_local_search_does_not_open_shared_connection_or_environment_file(self):
        with patch("product_catalog._connect", side_effect=AssertionError("shared connection forbidden")), patch("dotenv.load_dotenv", side_effect=AssertionError("environment read forbidden")):
            result = self.client.get("/api/search", params={"q": "コーヒー"})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["results"][0]["id"], "DEMO-002")
            self.assertEqual(self.client.get("/api/search?q=該当なし").json()["total"], 0)


if __name__ == "__main__":
    unittest.main()
