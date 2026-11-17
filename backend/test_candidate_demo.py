"""仮APIの参加者分離・入力境界・保存競合と既存検索契約の確認。"""

import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import candidate_demo as demo


class CandidateDemoTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"GIFTIA_CANDIDATE_DEMO_DB": str(Path(self.temp.name) / "drafts.sqlite3"), "GIFTIA_CATALOG_SOURCE": "demo"})
        self.env.start()
        self.client = TestClient(demo.app)
        self.url = "/api/rooms/demo-farewell/candidate-draft"
        self.a = {"X-Demo-Member": "demo-yutti"}
        self.b = {"X-Demo-Member": "demo-takerun"}

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.temp.cleanup()

    def put(self, slots, version=0, headers=None):
        return self.client.put(self.url, headers=headers or self.a, json={"version": version, "slots": slots})

    def test_independent_members_and_persistent_mixed_draft(self):
        a_slots = [{"kind": "product", "productId": "DEMO-001", "reason": "休んでほしい"}, {"kind": "hint", "text": "コーヒーが好きそう"}]
        b_slots = [{"kind": "hint", "text": "休日にゆっくりしてほしい"}]
        self.assertEqual(self.put(a_slots).status_code, 200)
        self.assertEqual(self.put(b_slots, headers=self.b).status_code, 200)
        a = self.client.get(self.url, headers=self.a).json()
        b = self.client.get(self.url, headers=self.b).json()
        self.assertEqual(len(a["slots"]), 2)
        self.assertEqual(b["slots"], b_slots)
        self.assertNotIn("コーヒー", str(b))
        self.assertNotIn("休日", str(a))
        self.assertEqual(a["version"], 1)
        # 別のAPIクライアントからも、同じ保存先の本人の下書きを再取得できる。
        with TestClient(demo.app) as second:
            self.assertEqual(second.get(self.url, headers=self.a).json(), a)

    def test_limits_empty_hint_and_atomic_rejection(self):
        valid = [{"kind": "hint", "text": f"好み{i}"} for i in range(3)]
        self.assertEqual(self.put(valid).status_code, 200)
        self.assertEqual(self.put(valid + [{"kind": "hint", "text": "4つ目"}], version=1).status_code, 422)
        for text in ("", "  ", "あ" * 101):
            self.assertEqual(self.put([{"kind": "hint", "text": text}], version=1).status_code, 422)
        self.assertEqual(self.client.get(self.url, headers=self.a).json()["slots"], valid)

    def test_duplicate_unknown_product_and_spoofed_gift(self):
        product = {"kind": "product", "productId": "DEMO-001", "reason": ""}
        self.assertEqual(self.put([product, product]).status_code, 400)
        self.assertEqual(self.put([{**product, "productId": "unknown"}]).status_code, 400)
        self.assertEqual(self.put([{**product, "gift": {"price": 1}}]).status_code, 422)
        self.assertEqual(self.client.get(self.url, headers=self.a).json()["version"], 0)

    def test_replace_delete_and_same_product_for_different_members(self):
        product = {"kind": "product", "productId": "DEMO-001", "reason": ""}
        self.assertEqual(self.put([product]).status_code, 200)
        self.assertEqual(self.put([product], headers=self.b).status_code, 200)
        self.assertEqual(self.put([{**product, "reason": "  理由を修正  "}], version=1).json()["slots"][0]["reason"], "理由を修正")
        self.assertEqual(self.put([], version=2).json()["slots"], [])
        self.assertEqual(len(self.client.get(self.url, headers=self.b).json()["slots"]), 1)

    def test_missing_other_room_and_missing_member(self):
        self.assertEqual(self.client.get(self.url).status_code, 422)
        self.assertEqual(self.client.get(self.url, headers={"X-Demo-Member": "demo-other-member"}).status_code, 403)
        self.assertEqual(self.client.get("/api/rooms/demo-other/candidate-draft", headers=self.a).status_code, 403)
        self.assertEqual(self.client.get("/api/rooms/unknown/candidate-draft", headers=self.a).status_code, 404)

    def test_concurrent_same_version_has_one_winner(self):
        # 初期化を済ませ、同一版から2つの画面が同時保存した状態を作る。
        self.client.get(self.url, headers=self.a)
        def save(text):
            return self.put([{"kind": "hint", "text": text}]).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(save, ["案A", "案B"]))
        self.assertEqual(sorted(statuses), [200, 409])
        self.assertEqual(self.client.get(self.url, headers=self.a).json()["version"], 1)

    def test_demo_search_retains_gift_contract_and_empty_case(self):
        data = self.client.get("/api/search", params={"q": "コーヒー"}).json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(set(data["results"][0]), {"id", "category", "brand", "name", "price", "rating", "reviewCount"})
        self.assertEqual(self.client.get("/api/search", params={"q": "存在しない商品"}).json(), {"total": 0, "results": []})
        data = self.client.get("/api/search", params={"indiv_wrap": True, "price_min": 3000, "price_max": 4999}).json()
        self.assertEqual([p["id"] for p in data["results"]], ["DEMO-004"])

    def test_cors_allows_local_put_and_rejects_other_origin(self):
        headers = {"Origin": "http://127.0.0.1:3200", "Access-Control-Request-Method": "PUT", "Access-Control-Request-Headers": "Content-Type,X-Demo-Member"}
        self.assertEqual(self.client.options(self.url, headers=headers).status_code, 200)
        self.assertEqual(self.client.options(self.url, headers={**headers, "Origin": "https://example.com"}).status_code, 400)

    def test_existing_search_uses_parameters_and_gift_conversion(self):
        # 既存APIの動作を、環境設定や共通DBに触らず確認する。
        with patch("dotenv.load_dotenv", return_value=False):
            import main as legacy
        row = {"product_id": "DUMMY-001", "category": "食品", "brand": "架空", "product_name": "架空のお菓子", "price": 3500, "rating": None, "review_count": 0}
        with patch.object(legacy, "fetch_all", side_effect=[[{"n": 1}], [row]]) as query:
            result = legacy.search(q="送別 お菓子", category="食品", indiv_wrap=True, price_min=3000, price_max=5000, limit=2)
        self.assertEqual(result["results"][0]["id"], "DUMMY-001")
        self.assertEqual(result["results"][0]["rating"], 0)
        sql, params = query.call_args_list[1].args
        self.assertNotIn("送別", sql)
        self.assertIn("%送別%", params)
        self.assertEqual(params[-1], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
