"""共通商品をREAD ONLYで取得する。ルームや候補の保存は担当しない。"""

from contextlib import contextmanager

from fastapi import HTTPException


def _connect():
    # テスト・固定商品モードでは接続設定を読まず、必要な場合だけ既存接続を利用する。
    from connection_pool import pool
    return pool.acquire()


@contextmanager
def read_only_cursor():
    connection = None
    try:
        connection = _connect()
        with connection.cursor() as cursor:
            cursor.execute("START TRANSACTION READ ONLY")
            yield cursor
    except Exception:
        # DB例外の本文にはホスト名・ユーザー名等が含まれるため返さない。
        raise HTTPException(503, "共通DBの商品情報を取得できません。接続を確認して再試行してください") from None
    finally:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
            try:
                connection.close()
            except Exception:
                pass


def to_gift(row):
    return {
        "id": row["product_id"], "category": row["category"], "brand": row["brand"],
        "name": row["product_name"], "price": int(row["price"]),
        "rating": float(row["rating"]) if row["rating"] is not None else 0,
        "reviewCount": int(row["review_count"]),
    }


PROJECTION = "product_id, category, brand, product_name, price, rating, review_count"


class SharedProductCatalog:
    source = "shared"

    def categories(self, budget):
        with read_only_cursor() as cursor:
            cursor.execute("""SELECT DISTINCT p.category FROM products p
                WHERE p.stock>0 AND p.price>=%s AND p.price<=%s AND p.rating>=4.0 AND p.category<>''
                  AND EXISTS (SELECT 1 FROM product_scenes s WHERE s.product_id=p.product_id AND s.scene_tag=%s)
                ORDER BY p.category""", ((budget * 8 + 9) // 10, budget, "送別"))
            return [row["category"] for row in cursor.fetchall()]

    def search(self, q, category, indiv_wrap, price_min, price_max, limit):
        # 既存main.pyの検索条件と並び順を維持。推薦用の新しい絞り込みではない。
        where, params = ["stock > 0"], []
        for word in q.split():
            where.append("(product_name LIKE %s OR brand LIKE %s OR description LIKE %s)")
            params.extend([f"%{word}%"] * 3)
        if category:
            where.append("category = %s")
            params.append(category)
        if indiv_wrap:
            where.append("description LIKE %s")
            params.append("%個包装%")
        if price_min is not None:
            where.append("price >= %s")
            params.append(price_min)
        if price_max is not None:
            where.append("price <= %s")
            params.append(price_max)
        condition = " AND ".join(where)
        with read_only_cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) AS n FROM products WHERE {condition}", tuple(params))
            total = int(cursor.fetchone()["n"])
            cursor.execute(f"SELECT {PROJECTION} FROM products WHERE {condition} ORDER BY sales_count DESC, product_id LIMIT %s", (*params, limit))
            results = [to_gift(row) for row in cursor.fetchall()]
        return {"total": total, "results": results}

    def get_many(self, ids):
        if not ids:
            return {}
        placeholders = ",".join(["%s"] * len(ids))
        with read_only_cursor() as cursor:
            cursor.execute(f"SELECT {PROJECTION}, stock FROM products WHERE product_id IN ({placeholders})", tuple(ids))
            return {row["product_id"]: {"gift": to_gift(row), "available": row["stock"] > 0} for row in cursor.fetchall()}
