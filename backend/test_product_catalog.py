"""共通商品読取の境界を、実DBや接続設定に触れず検証する。"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

import candidate_demo as demo
from product_catalog import SharedProductCatalog


ROW = {"product_id": "DUMMY-SHARED-001", "category": "食品", "brand": "架空", "product_name": "架空の共有商品", "price": 3500, "rating": None, "review_count": 2, "stock": 4}
GIFT = {"id": ROW["product_id"], "category": "食品", "brand": "架空", "name": ROW["product_name"], "price": 3500, "rating": 0, "reviewCount": 2}


class SharedCatalogTest(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.return_value = {"n": 1}
        self.cursor.fetchall.return_value = [ROW]
        self.connect = patch("product_catalog._connect", return_value=self.connection)
        self.connect.start()
        self.addCleanup(self.connect.stop)

    def test_search_read_only_and_same_search_conditions(self):
        result = SharedProductCatalog().search("送別 お菓子", "食品", True, 3000, 5000, 2)
        self.assertEqual(result, {"total": 1, "results": [GIFT]})
        calls = self.cursor.execute.call_args_list
        self.assertEqual(calls[0].args, ("START TRANSACTION READ ONLY",))
        self.assertEqual(len(calls), 3)
        sql, params = calls[-1].args
        self.assertIn("stock > 0", sql)
        self.assertIn("ORDER BY sales_count DESC, product_id", sql)
        self.assertNotIn("送別", sql)
        self.assertEqual(params, ("%送別%",) * 3 + ("%お菓子%",) * 3 + ("食品", "%個包装%", 3000, 5000, 2))
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once()
        self.connection.close.assert_called_once()

    def test_product_ids_are_parameters_and_unavailable_is_explicit(self):
        injected_id = "x' OR 1=1 --"
        self.cursor.fetchall.return_value = [{**ROW, "stock": 0}]
        result = SharedProductCatalog().get_many([ROW["product_id"], injected_id])
        self.assertFalse(result[ROW["product_id"]]["available"])
        sql, params = self.cursor.execute.call_args.args
        self.assertNotIn(injected_id, sql)
        self.assertEqual(params, (ROW["product_id"], injected_id))
        self.connection.commit.assert_not_called()

    def test_empty_draft_does_not_need_db_connection(self):
        self.assertEqual(SharedProductCatalog().get_many([]), {})
        self.connection.cursor.assert_not_called()

    def test_categories_come_from_budgeted_in_stock_farewell_products(self):
        self.cursor.fetchall.return_value = [{"category": "食品"}, {"category": "生活雑貨"}]
        self.assertEqual(SharedProductCatalog().categories(6000), ["食品", "生活雑貨"])
        sql, params = self.cursor.execute.call_args.args
        self.assertIn("SELECT DISTINCT p.category", sql)
        self.assertIn("p.stock>0", sql)
        self.assertIn("product_scenes", sql)
        self.assertEqual(params, (4800, 6000, "送別"))
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once()

    def test_query_failure_is_sanitized_and_transaction_closed(self):
        self.cursor.execute.side_effect = RuntimeError("do-not-expose-connection-details")
        with self.assertRaises(HTTPException) as raised:
            SharedProductCatalog().search("", "", False, None, None, 20)
        self.assertEqual(raised.exception.status_code, 503)
        self.assertNotIn("do-not-expose", raised.exception.detail)
        self.connection.rollback.assert_called_once()
        self.connection.close.assert_called_once()


class SharedDraftTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"GIFTIA_CANDIDATE_DEMO_DB": str(Path(self.temp.name) / "draft.sqlite3"), "GIFTIA_CATALOG_SOURCE": "shared"})
        self.env.start()
        self.client = TestClient(demo.app)
        self.url = "/api/rooms/demo-farewell/candidate-draft"
        self.headers = {"X-Demo-Member": "demo-yutti"}

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.temp.cleanup()

    def save(self, slots, version=0):
        return self.client.put(self.url, headers=self.headers, json={"version": version, "slots": slots})

    def test_shared_product_is_saved_and_reloaded_from_current_catalog(self):
        catalog = MagicMock(source="shared")
        catalog.get_many.return_value = {GIFT["id"]: {"gift": GIFT, "available": True}}
        with patch.object(demo, "get_catalog", return_value=catalog):
            result = self.save([{"kind": "product", "productId": GIFT["id"], "reason": "試験用"}])
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["catalogSource"], "shared")
            self.assertEqual(result.json()["slots"][0]["gift"], GIFT)
            catalog.get_many.return_value = {GIFT["id"]: {"gift": {**GIFT, "price": 3700}, "available": True}}
            reread = self.client.get(self.url, headers=self.headers).json()
            self.assertEqual(reread["slots"][0]["gift"]["price"], 3700)
            self.assertEqual(reread["version"], 1)

    def test_missing_or_out_of_stock_does_not_overwrite_draft(self):
        catalog = MagicMock(source="shared")
        with patch.object(demo, "get_catalog", return_value=catalog):
            catalog.get_many.return_value = {}
            self.assertEqual(self.save([{"kind": "hint", "text": "残したいヒント"}]).status_code, 200)
            for products in ({}, {GIFT["id"]: {"gift": GIFT, "available": False}}):
                catalog.get_many.return_value = products
                self.assertEqual(self.save([{"kind": "product", "productId": GIFT["id"], "reason": ""}], 1).status_code, 400)
            self.assertEqual(self.client.get(self.url, headers=self.headers).json()["slots"], [{"kind": "hint", "text": "残したいヒント"}])

    def test_discontinued_saved_product_keeps_snapshot_and_can_be_removed(self):
        catalog = MagicMock(source="shared")
        with patch.object(demo, "get_catalog", return_value=catalog):
            catalog.get_many.return_value = {GIFT["id"]: {"gift": GIFT, "available": True}}
            self.assertEqual(self.save([{"kind": "product", "productId": GIFT["id"], "reason": ""}]).status_code, 200)
            catalog.get_many.return_value = {}
            reread = self.client.get(self.url, headers=self.headers).json()
            self.assertEqual(reread["slots"][0]["gift"], GIFT)
            self.assertFalse(reread["slots"][0]["available"])
            self.assertEqual(self.save([], 1).status_code, 200)

    def test_legacy_demo_product_is_not_deleted_by_mode_switch(self):
        with patch.dict(os.environ, {"GIFTIA_CATALOG_SOURCE": "demo"}):
            self.assertEqual(self.save([{"kind": "product", "productId": "DEMO-001", "reason": "以前の候補"}]).status_code, 200)
        with patch("product_catalog._connect") as connect:
            cursor = connect.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchall.return_value = []
            result = self.client.get(self.url, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["slots"][0]["reason"], "以前の候補")
        self.assertFalse(result.json()["slots"][0]["available"])

    def test_connection_failure_is_not_demo_fallback_and_hides_details(self):
        with patch("product_catalog._connect", side_effect=RuntimeError("do-not-expose-user-host-password")):
            response = self.client.get("/api/search")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("do-not-expose", response.text)
        self.assertNotIn("DEMO-", response.text)
        self.assertIn("共通DB", response.json()["detail"])

    def test_invalid_source_fails_closed(self):
        with patch.dict(os.environ, {"GIFTIA_CATALOG_SOURCE": "typo"}):
            self.assertEqual(self.client.get("/api/search").status_code, 503)


if __name__ == "__main__":
    unittest.main(verbosity=2)
