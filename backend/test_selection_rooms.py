"""#25の合意：全員提出・全体10品・主催者開始・共通コメントを検証。"""
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
import selection_rooms as selection

PRODUCTS = [{"id": f"TEST-{i:03d}", "category": "食品" if i % 2 else "生活雑貨", "brand": "架空店", "name": f"架空商品{i}", "price": 5000 + i * 50, "rating": 4, "reviewCount": 1} for i in range(1, 13)]


class TestCatalog:
    source = "demo"

    def __init__(self):
        self.products = [dict(p) for p in PRODUCTS]

    def search(self, q, category, indiv_wrap, price_min, price_max, limit):
        found = [g for g in self.products if (not category or g["category"] == category) and (price_min is None or g["price"] >= price_min) and (price_max is None or g["price"] <= price_max)]
        return {"total": len(found), "results": found[:limit]}

    def categories(self, budget):
        return sorted({g["category"] for g in self.products if (budget * 8 + 9) // 10 <= g["price"] <= budget and g["rating"] >= 4})

    def get_many(self, ids):
        return {g["id"]: {"gift": g, "available": True} for g in self.products if g["id"] in ids}


class SelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        setting = patch.dict(os.environ, {"GIFTIA_LOCAL_ROOMS_DB": str(Path(temporary.name) / "selection.sqlite3"), "GIFTIA_CATALOG_SOURCE": "demo"})
        setting.start()
        self.addCleanup(setting.stop)
        clock = patch("room_contract.today_in_japan", return_value=date(2026, 11, 20))
        clock.start()
        self.addCleanup(clock.stop)
        self.catalog = TestCatalog()
        catalog = patch.object(selection, "get_catalog", return_value=self.catalog)
        catalog.start()
        self.addCleanup(catalog.stop)
        self.clients = [TestClient(selection.app) for _ in range(7)]
        for client in self.clients:
            self.addCleanup(client.close)
        self.host = self.clients[0]
        created = self.host.post("/api/rooms", json={"title": "架空送別", "nickname": "主催者ダミー", "budget_total": 6000, "member_count": 7, "deliver_by": "2026-11-24"})
        self.assertEqual(created.status_code, 201)
        self.base = f'/api/rooms/{created.json()["room_id"]}/selection'
        for i, client in enumerate(self.clients[1:]):
            self.assertEqual(client.post(self.base.replace("/selection", "/members"), json={"nickname": f"参加者ダミー{i}"}).status_code, 201)
        self.ids = [m["id"] for m in self.state()["members"]]

    def state(self, client=None):
        response = (client or self.host).get(self.base)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def draft(self, client=None, count=1, version=0, ids=None):
        ids = ids if ids is not None else [p["id"] for p in PRODUCTS[:count]]
        return (client or self.host).put(self.base + "/proposal", json={"version": version, "products": [{"productId": pid, "reason": "生活に合いそう"} for pid in ids]})

    def publish(self, client=None):
        return (client or self.host).post(self.base + "/submit")

    def voting(self, count=1):
        self.assertEqual(self.draft(count=count).status_code, 200)
        self.assertEqual(self.publish().status_code, 200)
        self.assertEqual(self.host.post(self.base + "/start-voting").status_code, 200)

    def test_all_can_submit_but_only_organizer_starts(self):
        sixth = self.clients[6]
        self.assertFalse(self.state(sixth)["me"]["canPropose"])
        self.assertEqual(self.draft(sixth).status_code, 409)
        self.assertEqual(self.publish(sixth).status_code, 409)
        self.assertEqual(self.draft().status_code, 200)
        self.assertFalse(self.state(sixth)["me"]["canPropose"])
        self.assertEqual(self.publish().status_code, 200)
        self.assertTrue(self.state(sixth)["me"]["canPropose"])
        self.assertEqual(self.draft(sixth).status_code, 200)
        self.assertEqual(self.publish(sixth).status_code, 200)
        self.assertEqual(self.state()["phase"], "collecting")
        self.assertEqual(len(self.state()["candidates"]), 1)
        self.assertEqual(sixth.post(self.base + "/start-voting").status_code, 403)
        self.assertEqual(sixth.put(self.base + "/products/TEST-001/vote", json={"stars": 3}).status_code, 409)
        self.assertEqual(self.host.post(self.base + "/start-voting").status_code, 200)
        self.assertEqual(sixth.put(self.base + "/products/TEST-001/vote", json={"stars": 3}).status_code, 200)
        self.assertEqual(self.draft(sixth, version=1).status_code, 409)

    def test_ten_distinct_room_candidates_and_overflow_preserves_public(self):
        self.assertEqual(self.draft(count=10).status_code, 200)
        self.assertEqual(self.publish().status_code, 200)
        self.assertEqual(self.draft(self.clients[1], ids=["TEST-011"]).status_code, 200)
        self.assertEqual(self.publish(self.clients[1]).status_code, 409)
        self.assertEqual(self.state()["progress"]["candidateCount"], 10)
        self.assertEqual(self.draft(self.clients[1], ids=["TEST-001"], version=1).status_code, 200)
        self.assertEqual(self.publish(self.clients[1]).status_code, 200)
        self.assertEqual(self.state()["progress"]["candidateCount"], 10)
        self.assertEqual(self.draft(count=11, version=1).status_code, 422)

    def test_concurrent_submissions_never_exceed_ten(self):
        self.draft(count=9)
        self.publish()
        self.draft(self.clients[1], ids=["TEST-010"])
        self.draft(self.clients[2], ids=["TEST-011"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda client: self.publish(client).status_code, self.clients[1:3]))
        self.assertEqual(sorted(statuses), [200, 409])
        self.assertEqual(self.state()["progress"]["candidateCount"], 10)

    def test_drafts_private_and_previous_public_stays_until_resubmission(self):
        self.draft(count=2)
        self.assertEqual(self.state(self.clients[1])["candidates"], [])
        self.publish()
        self.assertEqual(len(self.state(self.clients[1])["candidates"]), 2)
        self.assertEqual(self.draft(count=3, version=1).status_code, 200)
        self.assertEqual(len(self.state(self.clients[1])["candidates"]), 2)
        self.assertEqual(self.publish().status_code, 200)
        state = self.state(self.clients[1])
        self.assertEqual(len(state["candidates"]), 3)
        self.assertEqual(state["ownProducts"], [])
        self.assertNotIn("主催者ダミー", json.dumps(state["candidates"], ensure_ascii=False))

    def test_room_comments_are_anonymous_and_old_comment_keeps_context(self):
        self.assertEqual(self.clients[6].post(self.base + "/comments", json={"text": "相手はコーヒーをよく飲むそうです"}).status_code, 201)
        self.draft()
        self.publish()
        with selection.connection() as con:
            con.execute("INSERT INTO selection_comments(room_id,member_id,product_id,text) VALUES (%s,%s,%s,%s)", (int(self.base.split('/')[3]), self.ids[0], "TEST-001", "旧商品のコメント"))
        comments = self.state()["comments"]
        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[0]["legacyProduct"], PRODUCTS[0]["name"])
        self.assertEqual(set(comments[1]), {"id", "kind", "text"})
        self.assertNotIn("member_id", json.dumps(comments))
        self.assertEqual(self.host.post(self.base + "/comments", json={"text": "  "}).status_code, 422)
        self.assertEqual(self.host.post(self.base + "/products/TEST-001/comments", json={"text": "旧入口"}).status_code, 404)

    def test_rating_updates_and_all_members_can_vote(self):
        self.voting()
        viewer = self.clients[6]
        url = self.base + "/products/TEST-001/vote"
        self.assertEqual(viewer.put(url, json={"stars": 1}).status_code, 200)
        self.assertEqual(viewer.put(url, json={"stars": 3}).status_code, 200)
        for invalid in [0, 4, True, 1.5]:
            self.assertEqual(viewer.put(url, json={"stars": invalid}).status_code, 422)
        candidate = self.state()["candidates"][0]
        self.assertEqual((candidate["totalStars"], candidate["voters"], candidate["myStars"]), (3, 1, None))
        self.assertNotIn("comments", candidate)
        self.assertEqual(viewer.put(self.base + "/products/unknown/vote", json={"stars": 1}).status_code, 404)

    def test_decision_persists_and_freezes_edits(self):
        self.voting(count=3)
        body = {"mode": "catalog", "productIds": [p["id"] for p in PRODUCTS[:3]], "reasonSources": ["votes"]}
        self.assertEqual(self.clients[1].post(self.base + "/decision", json=body).status_code, 403)
        self.assertEqual(self.host.post(self.base + "/decision", json=body).status_code, 200)
        state = self.state(self.clients[6])
        self.assertEqual(len(state["decision"]["products"]), 3)
        self.assertEqual(state["decision"]["payment"], "demo")
        self.assertEqual(self.host.post(self.base + "/comments", json={"text": "変更"}).status_code, 409)
        self.assertEqual(self.host.post(self.base + "/notes", json={"kind": "好み", "text": "変更"}).status_code, 409)
        self.assertEqual(self.host.put(self.base + "/products/TEST-001/vote", json={"stars": 2}).status_code, 409)
        self.assertEqual(self.host.post(self.base + "/start-voting").status_code, 409)

    def test_draft_conflicts_and_catalog_failure_keep_both_versions(self):
        self.draft()
        self.publish()
        self.assertEqual(self.draft(count=2).status_code, 409)
        with patch.object(self.catalog, "get_many", side_effect=HTTPException(503, "商品情報を取得できません")):
            self.assertEqual(self.draft(count=2, version=1).status_code, 503)
        state = self.state()
        self.assertEqual(len(state["ownProducts"]), 1)
        self.assertEqual(len(state["candidates"]), 1)

    def test_category_is_required_and_random_matches_selection(self):
        self.assertEqual(self.clients[6].get(self.base + "/categories").json()["categories"], ["生活雑貨", "食品"])
        self.assertEqual(self.host.get(self.base + "/random").status_code, 422)
        self.assertEqual(self.host.get(self.base + "/random", params={"category": " "}).status_code, 400)
        gifts = self.clients[6].get(self.base + "/random", params={"category": "食品"}).json()["results"]
        self.assertEqual(len(gifts), 3)
        self.assertTrue(all(g["category"] == "食品" and g["price"] <= 6000 for g in gifts))
        self.assertEqual(len({g["id"] for g in gifts}), 3)
        exclude = ",".join(g["id"] for g in PRODUCTS if g["category"] == "食品")
        self.assertEqual(self.host.get(self.base + "/random", params={"category": "食品", "exclude": exclude}).json()["results"], [])

    def test_shared_random_binds_category_and_exclusions(self):
        catalog = MagicMock(source="shared")
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        with patch.object(selection, "get_catalog", return_value=catalog), patch.object(selection, "read_only_cursor") as context:
            context.return_value.__enter__.return_value = cursor
            response = self.host.get(self.base + "/random", params={"category": "食品", "exclude": "x' OR 1=1"})
        self.assertEqual(response.json()["results"], [])
        sql, params = cursor.execute.call_args.args
        self.assertIn("p.category=%s", sql)
        self.assertIn("ORDER BY RAND() LIMIT 3", sql)
        self.assertNotIn("x' OR", sql)
        self.assertEqual(params, (4800, 6000, "食品", "送別", "x' OR 1=1"))

    def test_empty_room_cannot_start_and_legacy_designation_disabled(self):
        self.assertEqual(self.host.post(self.base + "/start-voting").status_code, 400)
        self.assertEqual(self.host.put(self.base + "/submitters", json={"memberIds": self.ids}).status_code, 410)
        self.assertEqual(self.host.post(self.base + "/decision", json={"mode": "single", "productIds": ["TEST-001"], "reasonSources": ["votes"]}).status_code, 409)
        self.assertEqual(self.publish().status_code, 400)

    def test_outsiders_and_foreign_origins_rejected(self):
        stranger = TestClient(selection.app)
        self.addCleanup(stranger.close)
        self.assertEqual(stranger.get(self.base).status_code, 401)
        self.assertEqual(stranger.post(self.base + "/comments", json={"text": "外部"}).status_code, 401)
        self.assertEqual(self.host.post(self.base + "/comments", json={"text": "外部"}, headers={"Origin": "https://example.com"}).status_code, 403)
        self.assertEqual(self.host.get(self.base).headers["cache-control"], "no-store")

    def test_host_curation_replaces_others_and_survives_own_submission(self):
        contributor = self.clients[1]
        self.assertEqual(self.draft().status_code, 200)
        self.assertEqual(self.publish().status_code, 200)
        self.draft(contributor, count=2)
        self.publish(contributor)
        self.assertEqual(contributor.post(self.base + "/curation", json={"productId": "TEST-003"}).status_code, 403)
        self.assertEqual(self.host.post(self.base + "/curation", json={"replaceProductId": "TEST-001", "productId": "TEST-003"}).status_code, 200)
        self.assertEqual([p["productId"] for p in self.state(contributor)["ownProducts"]], ["TEST-001", "TEST-002"])
        self.assertEqual(self.host.post(self.base + "/curation", json={"productId": "TEST-004"}).status_code, 200)
        self.draft(ids=["TEST-005"], version=1)
        self.publish()
        self.assertEqual({c["gift"]["id"] for c in self.state()["candidates"]}, {"TEST-002", "TEST-003", "TEST-004", "TEST-005"})
        self.assertEqual(self.host.post(self.base + "/curation/remove", json={"productId": "TEST-002"}).status_code, 200)
        self.assertNotIn("TEST-002", {c["gift"]["id"] for c in self.state()["candidates"]})
        self.host.post(self.base + "/start-voting")
        self.assertEqual(self.host.post(self.base + "/curation", json={"productId": "TEST-006"}).status_code, 409)
        self.assertEqual(self.host.post(self.base + "/curation/remove", json={"productId": "TEST-003"}).status_code, 409)

    def test_host_replacement_at_cap_and_invalid_product_keep_candidates(self):
        self.draft(count=10)
        self.publish()
        self.assertEqual(self.host.post(self.base + "/curation", json={"productId": "TEST-011"}).status_code, 409)
        self.assertEqual(self.host.post(self.base + "/curation", json={"replaceProductId": "TEST-001", "productId": "TEST-011"}).status_code, 200)
        self.assertEqual(self.state()["progress"]["candidateCount"], 10)
        self.assertEqual(self.host.post(self.base + "/curation", json={"replaceProductId": "TEST-002", "productId": "unknown"}).status_code, 400)
        self.assertIn("TEST-002", {c["gift"]["id"] for c in self.state()["candidates"]})

    def test_comments_have_types_and_are_closed_and_hidden_during_voting(self):
        response = self.clients[6].post(self.base + "/comments", json={"kind": "避けたいもの", "text": "強い香りは苦手と本人から聞いた"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.state()["comments"][0]["kind"], "避けたいもの")
        self.voting()
        self.assertEqual(self.state()["comments"], [])
        self.assertEqual(self.state()["notes"], [])
        self.assertEqual(self.clients[6].post(self.base + "/comments", json={"kind": "好み", "text": "変更"}).status_code, 409)
        self.assertEqual(self.clients[6].post(self.base + "/notes", json={"kind": "好み", "text": "変更"}).status_code, 409)

    def test_random_price_band_and_review_floor_are_not_relaxed(self):
        self.catalog.products = [
            {**PRODUCTS[0], "id": "EDGE-1", "price": 4800, "rating": 4.0},
            {**PRODUCTS[0], "id": "EDGE-2", "price": 6000, "rating": 4.1},
            {**PRODUCTS[0], "id": "LOW-PRICE", "price": 4799, "rating": 4.9},
            {**PRODUCTS[0], "id": "HIGH-PRICE", "price": 6001, "rating": 4.9},
            {**PRODUCTS[0], "id": "LOW-RATING", "price": 5500, "rating": 3.9},
        ]
        result = self.host.get(self.base + "/random", params={"category": "食品"}).json()["results"]
        self.assertEqual({g["id"] for g in result}, {"EDGE-1", "EDGE-2"})

    def test_decision_reasons_are_multi_select_and_other_requires_text(self):
        self.voting()
        base = {"mode": "single", "productIds": ["TEST-001"]}
        self.assertEqual(self.host.post(self.base + "/decision", json=base).status_code, 422)
        for fields, status in [({"reasonSources": []}, 422), ({"reasonSources": ["votes", "votes"]}, 400), ({"reasonSources": ["other"]}, 400), ({"reasonSources": ["votes"], "otherReason": "自由入力"}, 400)]:
            self.assertEqual(self.host.post(self.base + "/decision", json={**base, **fields}).status_code, status)
        reasons = {"reasonSources": ["votes", "comments", "other"], "otherReason": "持ち帰りやすい大きさだから"}
        self.assertEqual(self.host.post(self.base + "/decision", json={**base, **reasons}).status_code, 200)
        result = self.state(self.clients[6])["decision"]
        self.assertEqual(result["reasonSources"], reasons["reasonSources"])
        self.assertEqual(result["otherReason"], reasons["otherReason"])

    def test_organizer_edits_settings_only_before_voting_and_preserves_data(self):
        self.draft()
        self.publish()
        self.clients[1].post(self.base + "/comments", json={"kind": "好み", "text": "残す情報"})
        body = {"title": "修正したルーム", "budget_total": 5500, "member_count": 4, "deliver_by": "2026-11-25"}
        self.assertEqual(self.clients[1].put(self.base + "/room", json=body).status_code, 403)
        self.assertEqual(self.host.put(self.base + "/room", json={**body, "budget_total": 0}).status_code, 422)
        self.assertEqual(self.host.put(self.base + "/room", json={**body, "deliver_by": "2026-11-23"}).status_code, 422)
        self.assertEqual(self.host.put(self.base + "/room", json=body).status_code, 200)
        result = self.state()
        self.assertEqual(result["room"], {"id": self.base.split('/')[3], "title": body["title"], "budgetTotal": 5500, "memberCount": 4, "deliverBy": "2026-11-25"})
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(len(result["comments"]), 1)
        base_room = self.host.get(self.base.replace('/selection', '')).json()
        self.assertEqual(base_room["price_per_person"], 1375)
        self.assertEqual(self.host.post(self.base + "/start-voting").status_code, 200)
        self.assertEqual(self.host.put(self.base + "/room", json=body).status_code, 409)

    def test_initial_submission_stays_open_after_host_removes_original(self):
        self.draft()
        self.publish()
        self.host.post(self.base + "/curation/remove", json={"productId": "TEST-001"})
        self.assertTrue(self.state(self.clients[1])["initialProposalSubmitted"])
        self.assertEqual(self.draft(self.clients[1], ids=["TEST-002"]).status_code, 200)
        self.assertEqual(self.publish(self.clients[1]).status_code, 200)

    def test_read_does_not_create_submitter_or_acquire_parent_write_lock(self):
        with patch.object(selection.rooms, "own_member", wraps=selection.rooms.own_member) as member:
            self.state(self.clients[1])
        self.assertFalse(member.call_args.kwargs["lock"])
        with selection.connection() as con:
            self.assertIsNone(con.execute("SELECT 1 FROM selection_submitters WHERE room_id=%s AND member_id=%s", (int(self.base.split('/')[3]), self.ids[1])).fetchone())

    def test_combined_submit_returns_state_and_rolls_back_draft_on_overflow(self):
        body = {"version": 0, "products": [{"productId": "TEST-001", "reason": "最初"}]}
        response = self.host.post(self.base + "/submit", json=body)
        self.assertEqual(response.status_code, 200)
        result = response.json()["selection"]
        self.assertEqual(result["me"]["version"], 1)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertTrue(result["initialProposalSubmitted"])
        self.assertEqual(self.host.post(self.base + "/submit", json=body).status_code, 409)
        self.assertEqual(self.draft(count=10, version=1).status_code, 200)
        self.publish()
        response = self.clients[1].post(self.base + "/submit", json={"version": 0, "products": [{"productId": "TEST-011", "reason": "溢れる"}]})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.state(self.clients[1])["ownProducts"], [])
        self.assertEqual(len(self.state()["candidates"]), 10)

    def test_actions_return_authoritative_state_without_followup_get(self):
        first = self.host.post(self.base + "/submit", json={"version": 0, "products": [{"productId": "TEST-001", "reason": "説明"}]}).json()["selection"]
        self.assertTrue(first["initialProposalSubmitted"])
        comment = self.clients[1].post(self.base + "/comments", json={"kind": "好み", "text": "コーヒー"}).json()["selection"]
        self.assertEqual(comment["comments"][0]["text"], "コーヒー")
        start = self.host.post(self.base + "/start-voting").json()["selection"]
        self.assertEqual(start["phase"], "voting")
        self.assertEqual(start["comments"], [])
        vote = self.clients[1].put(self.base + "/products/TEST-001/vote", json={"stars": 3}).json()["selection"]
        self.assertEqual(vote["candidates"][0]["myStars"], 3)
        self.assertEqual(vote["candidates"][0]["totalStars"], 3)
        decision = self.host.post(self.base + "/decision", json={"mode": "single", "productIds": ["TEST-001"], "reasonSources": ["votes"]}).json()["selection"]
        self.assertEqual(decision["phase"], "decided")
        self.assertEqual(decision["decision"]["products"][0]["id"], "TEST-001")

    def test_concurrent_votes_are_not_lost(self):
        self.voting()
        def cast(client):
            return client.put(self.base + "/products/TEST-001/vote", json={"stars": 3}).status_code
        with ThreadPoolExecutor(max_workers=3) as pool:
            statuses = list(pool.map(cast, self.clients[1:4]))
        self.assertEqual(statuses, [200, 200, 200])
        result = self.state()["candidates"][0]
        self.assertEqual((result["totalStars"], result["voters"]), (9, 3))


if __name__ == "__main__":
    unittest.main()
