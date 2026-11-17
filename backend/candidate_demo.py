"""B担当のローカル検証。商品は固定データまたは共通DBの読取、候補保存はSQLiteのみ。"""

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from product_catalog import SharedProductCatalog

app = FastAPI(title="Giftia 候補入力ローカル検証（商品読取・候補はローカル保存）")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (3000, 3200)],
    allow_methods=["GET", "PUT"],
    allow_headers=["Content-Type", "X-Demo-Member"],
)

ROOMS = {
    "demo-farewell": {
        "id": "demo-farewell", "title": "佐藤さんの送別ギフト", "budgetTotal": 6000,
        "members": [{"id": "demo-yutti", "name": "ゆってぃさん"}, {"id": "demo-takerun", "name": "たけるんさん"}],
    },
    "demo-other": {
        "id": "demo-other", "title": "別のルーム", "budgetTotal": 3000,
        "members": [{"id": "demo-other-member", "name": "別ルームの参加者"}],
    },
}

# 配布DBの実データとは別の、画面・境界テスト用の架空商品。
PRODUCTS = [
    {"id": "DEMO-001", "category": "生活雑貨", "brand": "架空のくらし店", "name": "ゆっくり過ごすマグカップ", "price": 2400, "rating": 4.2, "reviewCount": 12},
    {"id": "DEMO-002", "category": "食品", "brand": "架空の珈琲店", "name": "コーヒーの飲み比べセット", "price": 3600, "rating": 4.4, "reviewCount": 18},
    {"id": "DEMO-003", "category": "生活雑貨", "brand": "架空の織物店", "name": "やわらかいタオルセット", "price": 4200, "rating": 4.1, "reviewCount": 9},
    {"id": "DEMO-004", "category": "食品", "brand": "架空のお菓子店", "name": "個包装の焼き菓子セット", "price": 3200, "rating": 4.0, "reviewCount": 7},
    {"id": "DEMO-005", "category": "コスメ", "brand": "架空のケア用品店", "name": "ハンドケアセット", "price": 6800, "rating": 4.3, "reviewCount": 11},
]
PRODUCT_BY_ID = {p["id"]: p for p in PRODUCTS}


class DemoProductCatalog:
    source = "demo"

    def search(self, q, category, indiv_wrap, price_min, price_max, limit):
        result = [p for p in PRODUCTS if
                  all(word.lower() in f"{p['name']} {p['brand']} {p['category']}".lower() for word in q.split())
                  and (not category or p["category"] == category)
                  and (not indiv_wrap or "個包装" in p["name"])
                  and (price_min is None or p["price"] >= price_min)
                  and (price_max is None or p["price"] <= price_max)]
        return {"total": len(result), "results": result[:limit]}

    def get_many(self, ids):
        return {pid: {"gift": PRODUCT_BY_ID[pid], "available": True} for pid in ids if pid in PRODUCT_BY_ID}


def get_catalog():
    source = os.environ.get("GIFTIA_CATALOG_SOURCE", "demo")
    if source == "shared":
        return SharedProductCatalog()
    if source == "demo":
        return DemoProductCatalog()
    raise HTTPException(503, "商品取得元の設定を確認してください")


class ProductSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["product"]
    productId: str
    reason: str = Field(default="", max_length=100)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value):
        return value.strip() if isinstance(value, str) else value


class HintSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["hint"]
    text: str = Field(min_length=1, max_length=100)

    @field_validator("text", mode="before")
    @classmethod
    def trim_hint(cls, value):
        return value.strip() if isinstance(value, str) else value


Slot = Annotated[ProductSlot | HintSlot, Field(discriminator="kind")]


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=0)
    slots: list[Slot] = Field(max_length=3)


@contextmanager
def connection():
    # テストは一時DBへ切り替え、実行時もこのアプリのローカル保存先だけを使う。
    path = Path(os.environ.get("GIFTIA_CANDIDATE_DEMO_DB", Path(__file__).parent / ".local" / "candidate-demo.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        con.execute("CREATE TABLE IF NOT EXISTS drafts(room_id TEXT,member_id TEXT,version INTEGER NOT NULL,slots TEXT NOT NULL,PRIMARY KEY(room_id,member_id))")
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def participant(room_id, member_id):
    room = ROOMS.get(room_id)
    if not room:
        raise HTTPException(404, "ルームが見つかりません")
    member = next((m for m in room["members"] if m["id"] == member_id), None)
    if not member:
        raise HTTPException(403, "このルームの架空参加者を選び直してください")
    return room, member


def response(room, member, row, catalog=None, products=None):
    slots = json.loads(row["slots"]) if row else []
    catalog = catalog or get_catalog()
    ids = [slot["productId"] for slot in slots if slot["kind"] == "product"]
    products = catalog.get_many(ids) if products is None else products
    visible_slots = []
    for slot in slots:
        if slot["kind"] == "hint":
            visible_slots.append(slot)
            continue
        product = products.get(slot["productId"])
        # モード切替前の架空候補や、取り扱いがなくなった商品を黙って削除しない。
        gift = product["gift"] if product else slot.get("gift") or PRODUCT_BY_ID.get(slot["productId"])
        if gift is None:
            raise HTTPException(409, "保存済みの商品情報を確認できません。保存データの確認が必要です")
        visible_slots.append(dict(slot, gift=gift, available=bool(product and product["available"])))
    return {
        "room": {key: room[key] for key in ("id", "title", "budgetTotal")},
        "member": member, "demoMembers": room["members"],
        "catalogSource": catalog.source,
        "version": row["version"] if row else 0,
        "slots": visible_slots,
    }


@app.get("/api/search")
def search(q: str = "", category: str = "", indiv_wrap: bool = False,
           price_min: int | None = Query(None, ge=0), price_max: int | None = Query(None, ge=0),
           limit: int = Query(20, ge=1, le=100)):
    return get_catalog().search(q, category, indiv_wrap, price_min, price_max, limit)


@app.get("/api/rooms/{room_id}/candidate-draft")
def get_draft(room_id: str, member_id: str = Header(alias="X-Demo-Member")):
    room, member = participant(room_id, member_id)
    with connection() as con:
        row = con.execute("SELECT version,slots FROM drafts WHERE room_id=? AND member_id=?", (room_id, member_id)).fetchone()
        return response(room, member, row)


@app.put("/api/rooms/{room_id}/candidate-draft")
def save_draft(room_id: str, body: DraftInput, member_id: str = Header(alias="X-Demo-Member")):
    room, member = participant(room_id, member_id)
    slots = [slot.model_dump() for slot in body.slots]
    ids = [s["productId"] for s in slots if s["kind"] == "product"]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "同じ商品は1つの枠にまとめてください")
    catalog = get_catalog()
    products = catalog.get_many(ids)
    if any(pid not in products or not products[pid]["available"] for pid in ids):
        raise HTTPException(400, "候補の商品が見つからないか在庫切れです。該当の商品を削除または入れ替えてください")
    # 商品情報はサーバー側で取得し直す。将来取り扱い終了となった場合の表示用にも残す。
    slots = [dict(slot, gift=products[slot["productId"]]["gift"]) if slot["kind"] == "product" else slot for slot in slots]
    with connection() as con:
        # 同一参加者の複数タブから、古い下書きで上書きされることを防ぐ。
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT version FROM drafts WHERE room_id=? AND member_id=?", (room_id, member_id)).fetchone()
        version = row["version"] if row else 0
        if version != body.version:
            raise HTTPException(409, "別の画面で保存されています。入力内容を控え、保存済み内容を読み直してください")
        version += 1
        con.execute("INSERT INTO drafts(room_id,member_id,version,slots) VALUES(?,?,?,?) ON CONFLICT(room_id,member_id) DO UPDATE SET version=excluded.version,slots=excluded.slots",
                    (room_id, member_id, version, json.dumps(slots, ensure_ascii=False)))
        return response(room, member, {"version": version, "slots": json.dumps(slots)}, catalog, products)
