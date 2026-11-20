"""共同決定の権限・匿名性・件数制限・保存を一時SQLiteで検証。"""
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from candidate_demo import DemoProductCatalog, PRODUCTS
import selection_rooms as selection


class SelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.patch = patch.dict(os.environ, {"GIFTIA_LOCAL_ROOMS_DB": str(Path(temporary.name) / "selection.sqlite3"), "GIFTIA_CATALOG_SOURCE": "demo"})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        clock = patch("room_contract.today_in_japan", return_value=date(2026, 11, 20))
        clock.start()
        self.addCleanup(clock.stop)
        self.clients = [TestClient(selection.app) for _ in range(7)]
        for client in self.clients:
            self.addCleanup(client.close)
        self.host = self.clients[0]
        room = self.host.post("/api/rooms", json={"title": "架空送別", "nickname": "主催者ダミー", "budget_total": 6000, "member_count": 7, "deliver_by": "2026-11-24"})
        self.assertEqual(room.status_code, 201)
        self.base = f'/api/rooms/{room.json()["room_id"]}/selection'
        for i, client in enumerate(self.clients[1:]):
            response = client.post(self.base.replace("/selection", "/members"), json={"nickname": f"匿名参加ダミー{i}"})
            self.assertEqual(response.status_code, 201)
        self.ids = [m["id"] for m in self.state()["members"]]

    def state(self, client=None):
        response = (client or self.host).get(self.base)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def assign(self, ids=None, client=None):
        return (client or self.host).put(self.base + "/submitters", json={"memberIds": ids or self.ids[:1]})

    def draft(self, client=None, count=1, version=0):
        return (client or self.host).put(self.base + "/proposal", json={"version": version, "products": [{"productId": p["id"], "reason": "本人の生活に合いそう"} for p in PRODUCTS[:count]]})

    def voting(self, count=1):
        self.assertEqual(self.assign().status_code, 200)
        self.assertEqual(self.draft(count=count).status_code, 200)
        self.assertEqual(self.host.post(self.base + "/submit").status_code, 200)
        self.assertEqual(self.state()["phase"], "voting")

    def test_only_organizer_can_designate_at_most_five_room_members(self):
        self.assertEqual(self.assign(client=self.clients[1]).status_code, 403)
        self.assertEqual(self.assign(self.ids[:6]).status_code, 422)
        self.assertEqual(self.assign([self.ids[0], self.ids[0]]).status_code, 400)
        self.assertEqual(self.assign([999999]).status_code, 400)
        self.assertEqual(self.host.put(self.base + "/submitters", json={"memberIds": [True]}).status_code, 422)
        self.assertEqual(self.assign(self.ids[:5]).status_code, 200)
        self.assertEqual(self.draft(client=self.clients[5]).status_code, 403)
        self.assertEqual(self.clients[6].get(self.base + "/random").status_code, 403)

    def test_three_per_person_fifteen_total_and_private_until_all_submit(self):
        self.assertEqual(self.assign(self.ids[:5]).status_code, 200)
        self.assertEqual(self.draft(count=4).status_code, 422)
        for client in self.clients[:4]:
            self.assertEqual(self.draft(client, count=3).status_code, 200)
            self.assertEqual(client.post(self.base + "/submit").status_code, 200)
        self.assertEqual(self.state(self.clients[5])["candidates"], [])
        self.assertEqual(self.state(self.clients[5])["ownProducts"], [])
        self.assertEqual(self.state(self.clients[5])["members"], [])
        self.assertEqual(self.draft(self.clients[4], count=3).status_code, 200)
        self.assertEqual(self.clients[4].post(self.base + "/submit").status_code, 200)
        state = self.state(self.clients[5])
        self.assertEqual(state["phase"], "voting")
        self.assertEqual(len(state["candidates"]), 3)  # 重複商品はまとめる。
        with selection.connection() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) AS n FROM selection_proposals WHERE room_id=%s", (int(self.base.split('/')[3]),)).fetchone()["n"], 15)

    def test_optimistic_draft_lock_and_protected_roster(self):
        self.assign(self.ids[:2])
        self.assertEqual(self.draft().status_code, 200)
        self.assertEqual(self.draft().status_code, 409)
        self.assertEqual(self.assign([self.ids[1]]).status_code, 409)
        self.assertEqual(len(self.state()["ownProducts"]), 1)
        self.assertEqual(self.host.post(self.base + "/submit").status_code, 200)
        self.assertEqual(self.draft(version=1).status_code, 409)
        self.assertEqual(self.assign(self.ids[:3]).status_code, 409)

    def test_all_can_share_notes_but_api_does_not_reveal_authorship(self):
        response = self.clients[6].post(self.base + "/notes", json={"kind": "アレルギー・避けたいもの", "text": "本人に確認が必要"})
        self.assertEqual(response.status_code, 201)
        note = self.state()["notes"][0]
        self.assertEqual(set(note), {"id", "kind", "text"})
        self.assertEqual(self.host.post(self.base + "/notes", json={"kind": "好み", "text": "  "}).status_code, 422)

    def test_anonymous_ratings_are_updated_not_duplicated_and_comments_are_private(self):
        self.voting()
        url = self.base + "/products/DEMO-001"
        viewer = self.clients[6]
        self.assertEqual(viewer.put(url + "/vote", json={"stars": 1}).status_code, 200)
        self.assertEqual(viewer.put(url + "/vote", json={"stars": 3}).status_code, 200)
        for stars in [0, 4, True, 1.5]:
            self.assertEqual(viewer.put(url + "/vote", json={"stars": stars}).status_code, 422)
        self.assertEqual(viewer.post(url + "/comments", json={"text": "持ち帰りやすそう"}).status_code, 201)
        candidate = self.state()["candidates"][0]
        self.assertEqual((candidate["totalStars"], candidate["voters"], candidate["myStars"]), (3, 1, None))
        self.assertEqual(set(candidate["comments"][0]), {"id", "text"})
        self.assertNotIn("匿名参加ダミー", json.dumps(candidate, ensure_ascii=False))
        self.assertNotIn("member_id", json.dumps(candidate))
        self.assertEqual(viewer.put(self.base + "/products/NOT-IN-ROOM/vote", json={"stars": 3}).status_code, 404)

    def test_catalog_decision_survives_revisit_and_locks_mutations(self):
        self.voting(count=3)
        body = {"mode": "catalog", "productIds": [p["id"] for p in PRODUCTS[:3]]}
        self.assertEqual(self.clients[1].post(self.base + "/decision", json=body).status_code, 403)
        self.assertEqual(self.host.post(self.base + "/decision", json=body).status_code, 200)
        state = self.state(self.clients[6])
        self.assertEqual(state["decision"]["mode"], "catalog")
        self.assertEqual(len(state["decision"]["products"]), 3)
        self.assertEqual(state["decision"]["payment"], "demo")
        for url, payload in [("/notes", {"kind": "好み", "text": "変更"}), ("/products/DEMO-001/comments", {"text": "変更"}), ("/decision", body)]:
            self.assertEqual(self.host.post(self.base + url, json=payload).status_code, 409)
        self.assertEqual(self.host.put(self.base + "/products/DEMO-001/vote", json={"stars": 2}).status_code, 409)

    def test_decision_rejects_invalid_single_duplicate_and_over_budget(self):
        self.voting(count=3)
        for body in [{"mode": "single", "productIds": ["DEMO-001", "DEMO-002"]}, {"mode": "catalog", "productIds": ["DEMO-001", "DEMO-001"]}, {"mode": "single", "productIds": ["DEMO-005"]}]:
            self.assertEqual(self.host.post(self.base + "/decision", json=body).status_code, 400)
        catalog = DemoProductCatalog()
        original = catalog.get_many
        def changed(ids):
            found = original(ids)
            for item in found.values():
                item["gift"] = {**item["gift"], "price": 7000}
            return found
        with patch.object(catalog, "get_many", side_effect=changed), patch.object(selection, "get_catalog", return_value=catalog):
            self.assertEqual(self.host.post(self.base + "/decision", json={"mode": "single", "productIds": ["DEMO-001"]}).status_code, 400)
        self.assertEqual(self.state()["phase"], "voting")
        self.assertEqual(self.host.post(self.base + "/decision", json={"mode": "single", "productIds": ["DEMO-001"]}).status_code, 200)

    def test_anonymous_outsiders_wrong_room_and_cross_origin_are_rejected(self):
        stranger = TestClient(selection.app)
        self.addCleanup(stranger.close)
        self.assertEqual(stranger.get(self.base).status_code, 401)
        self.assertEqual(self.host.get("/api/rooms/999999/selection").status_code, 404)
        self.assertEqual(self.host.post(self.base + "/notes", json={"kind": "好み", "text": "test"}, headers={"Origin": "https://example.com"}).status_code, 403)
        self.assertEqual(self.host.get(self.base).headers["cache-control"], "no-store")

    def test_random_is_unique_budgeted_excludes_selected_and_handles_shortage(self):
        self.assign()
        gifts = self.host.get(self.base + "/random").json()["results"]
        self.assertEqual(len(gifts), 3)
        self.assertEqual(len({g["id"] for g in gifts}), 3)
        self.assertTrue(all(g["price"] <= 6000 for g in gifts))
        excluded = ",".join(g["id"] for g in PRODUCTS[:3])
        gifts = self.host.get(self.base + "/random", params={"exclude": excluded}).json()["results"]
        self.assertEqual([g["id"] for g in gifts], ["DEMO-004"])

    def test_shared_random_uses_farewell_tag_and_bound_parameters(self):
        from unittest.mock import MagicMock
        self.assign()
        catalog = MagicMock(source="shared")
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        with patch.object(selection, "get_catalog", return_value=catalog), patch.object(selection, "read_only_cursor") as context:
            context.return_value.__enter__.return_value = cursor
            response = self.host.get(self.base + "/random", params={"exclude": "x' OR 1=1"})
        self.assertEqual(response.json()["results"], [])
        sql, params = cursor.execute.call_args.args
        self.assertIn("product_scenes", sql)
        self.assertIn("ORDER BY RAND() LIMIT 3", sql)
        self.assertNotIn("x' OR", sql)
        self.assertEqual(params, (6000, "送別", "x' OR 1=1"))

    def test_storage_is_not_destroyed_when_catalog_fails(self):
        self.assign()
        self.draft()
        from fastapi import HTTPException
        broken = DemoProductCatalog()
        with patch.object(broken, "get_many", side_effect=HTTPException(503, "共通DBの商品情報を取得できません")), patch.object(selection, "get_catalog", return_value=broken):
            self.assertEqual(self.draft(count=2, version=1).status_code, 503)
        self.assertEqual(len(self.state()["ownProducts"]), 1)

    def test_parallel_votes_keep_one_vote_per_person(self):
        self.voting()
        def cast(stars):
            return self.clients[1].put(self.base + "/products/DEMO-001/vote", json={"stars": stars}).status_code
        with ThreadPoolExecutor(max_workers=3) as pool:
            self.assertEqual(list(pool.map(cast, [1, 2, 3])), [200, 200, 200])
        self.assertEqual(self.state()["candidates"][0]["voters"], 1)


if __name__ == "__main__":
    unittest.main()
