"""Issue #22: 名前参加から共同決定まで。商品は読取、ルーム情報は既存SQLiteへ保存。"""
import json
import random
import sqlite3
from contextlib import contextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

import local_rooms as rooms
from candidate_demo import get_catalog
from product_catalog import PROJECTION, read_only_cursor, to_gift

app = FastAPI(title="Giftia みんなで決める送別ギフト")
app.add_middleware(CORSMiddleware, allow_origins=rooms.ORIGINS, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type"])
app.middleware("http")(rooms.local_origin_only)
app.add_exception_handler(sqlite3.Error, rooms.storage_error)
RoomId = rooms.RoomId


@contextmanager
def connection():
    with rooms.connection() as con:
        con.executescript('''
          CREATE TABLE IF NOT EXISTS selection_state (
            room_id INTEGER PRIMARY KEY REFERENCES consultations(id),
            phase TEXT NOT NULL DEFAULT 'collecting', decision TEXT
          );
          CREATE TABLE IF NOT EXISTS selection_submitters (
            room_id INTEGER NOT NULL REFERENCES consultations(id),
            member_id INTEGER NOT NULL REFERENCES consultation_members(id),
            submitted INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(room_id,member_id)
          );
          CREATE TABLE IF NOT EXISTS selection_proposals (
            room_id INTEGER NOT NULL, member_id INTEGER NOT NULL,
            product_id TEXT NOT NULL, reason TEXT NOT NULL, gift TEXT NOT NULL,
            PRIMARY KEY(room_id,member_id,product_id),
            FOREIGN KEY(room_id,member_id) REFERENCES selection_submitters(room_id,member_id)
          );
          CREATE TABLE IF NOT EXISTS selection_notes (
            id INTEGER PRIMARY KEY, room_id INTEGER NOT NULL REFERENCES consultations(id),
            member_id INTEGER NOT NULL REFERENCES consultation_members(id),
            kind TEXT NOT NULL, text TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS selection_votes (
            room_id INTEGER NOT NULL REFERENCES consultations(id), member_id INTEGER NOT NULL,
            product_id TEXT NOT NULL, stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 3),
            PRIMARY KEY(room_id,member_id,product_id)
          );
          CREATE TABLE IF NOT EXISTS selection_comments (
            id INTEGER PRIMARY KEY, room_id INTEGER NOT NULL REFERENCES consultations(id),
            member_id INTEGER NOT NULL, product_id TEXT NOT NULL, text TEXT NOT NULL
          );
        ''')
        con.execute("BEGIN IMMEDIATE")
        yield con


def context(con, room_id, request, organizer=False, phase=None):
    room, member = rooms.own_member(con, room_id, request)
    if organizer and member["id"] != room["organizer_id"]:
        raise HTTPException(403, "主催者だけが操作できます")
    con.execute("INSERT OR IGNORE INTO selection_state(room_id) VALUES (?)", (room_id,))
    state = con.execute("SELECT * FROM selection_state WHERE room_id=?", (room_id,)).fetchone()
    if phase and state["phase"] != phase:
        raise HTTPException(409, "ルームの段階が変わっています。最新の内容を読み直してください")
    return room, member, state


def candidates(con, room_id):
    # 提案元・提案者数を共有レスポンスへ出さず、重複商品を1件にまとめる。
    grouped = {}
    for row in con.execute("SELECT product_id,reason,gift FROM selection_proposals WHERE room_id=? ORDER BY product_id,reason", (room_id,)):
        item = grouped.setdefault(row["product_id"], {"gift": json.loads(row["gift"]), "reasons": []})
        if row["reason"] and row["reason"] not in item["reasons"]:
            item["reasons"].append(row["reason"])
    return grouped


def require_candidate(con, room_id, product_id):
    if not con.execute("SELECT 1 FROM selection_proposals WHERE room_id=? AND product_id=?", (room_id, product_id)).fetchone():
        raise HTTPException(404, "このルームの候補ではありません")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Submitters(Input):
    memberIds: list[Annotated[int, Field(strict=True, ge=1)]] = Field(min_length=1, max_length=5)


class Product(Input):
    productId: str = Field(min_length=1, max_length=100)
    reason: str = Field(default="", max_length=100)


class Proposal(Input):
    version: int = Field(strict=True, ge=0)
    products: list[Product] = Field(max_length=3)


class Note(Input):
    kind: Literal["好み", "アレルギー・避けたいもの", "その他"]
    text: str = Field(min_length=1, max_length=300)


class Comment(Input):
    text: str = Field(min_length=1, max_length=300)


class Vote(Input):
    stars: int = Field(strict=True, ge=1, le=3)


class Decision(Input):
    mode: Literal["single", "catalog"]
    productIds: list[str] = Field(min_length=1, max_length=15)


@app.get("/api/search")
def search(q: str = "", category: str = "", indiv_wrap: bool = False,
           price_min: int | None = Query(None, ge=0), price_max: int | None = Query(None, ge=0),
           limit: int = Query(20, ge=1, le=100)):
    return get_catalog().search(q, category, indiv_wrap, price_min, price_max, limit)


@app.get("/api/rooms/{room_id}/selection")
def get_selection(room_id: RoomId, request: Request):
    with connection() as con:
        room, member, state = context(con, room_id, request)
        roster = con.execute("SELECT * FROM selection_submitters WHERE room_id=?", (room_id,)).fetchall()
        own = next((r for r in roster if r["member_id"] == member["id"]), None)
        personal = con.execute("SELECT product_id,reason,gift FROM selection_proposals WHERE room_id=? AND member_id=? ORDER BY product_id", (room_id, member["id"])).fetchall()
        visible = []
        if state["phase"] != "collecting":
            for pid, item in candidates(con, room_id).items():
                totals = con.execute("SELECT COALESCE(SUM(stars),0) AS total,COUNT(*) AS voters FROM selection_votes WHERE room_id=? AND product_id=?", (room_id, pid)).fetchone()
                vote = con.execute("SELECT stars FROM selection_votes WHERE room_id=? AND member_id=? AND product_id=?", (room_id, member["id"], pid)).fetchone()
                comments = [dict(r) for r in con.execute("SELECT id,text FROM selection_comments WHERE room_id=? AND product_id=? ORDER BY id", (room_id, pid))]
                visible.append({**item, "totalStars": totals["total"], "voters": totals["voters"], "myStars": vote["stars"] if vote else None, "comments": comments})
            visible.sort(key=lambda c: (-c["totalStars"], c["gift"]["id"]))
        is_organizer = member["id"] == room["organizer_id"]
        return {"room": {"id": str(room_id), "title": room["title"], "budgetTotal": room["budget_total"]},
                "phase": state["phase"], "catalogSource": get_catalog().source,
                "me": {"id": member["id"], "name": member["nickname"], "isOrganizer": is_organizer,
                       "canPropose": own is not None, "submitted": bool(own and own["submitted"]), "version": own["version"] if own else 0},
                "members": [{"id": r["id"], "name": r["nickname"], "canPropose": any(s["member_id"] == r["id"] for s in roster)} for r in con.execute("SELECT id,nickname FROM consultation_members WHERE consultation_id=? ORDER BY id", (room_id,))] if is_organizer else [],
                "progress": {"designated": len(roster), "submitted": sum(r["submitted"] for r in roster)},
                "notes": [dict(r) for r in con.execute("SELECT id,kind,text FROM selection_notes WHERE room_id=? ORDER BY id", (room_id,))],
                "ownProducts": [{"productId": r["product_id"], "reason": r["reason"], "gift": json.loads(r["gift"])} for r in personal],
                "candidates": visible, "decision": json.loads(state["decision"]) if state["decision"] else None}


@app.put("/api/rooms/{room_id}/selection/submitters")
def set_submitters(room_id: RoomId, body: Submitters, request: Request):
    ids = body.memberIds
    if any(type(mid) is not int for mid in ids) or len(ids) != len(set(ids)):
        raise HTTPException(400, "提出者を重複なく選んでください")
    with connection() as con:
        context(con, room_id, request, organizer=True, phase="collecting")
        if con.execute("SELECT 1 FROM selection_submitters WHERE room_id=? AND submitted=1", (room_id,)).fetchone():
            raise HTTPException(409, "提出開始後は提出者を変更できません")
        members = {r["id"] for r in con.execute("SELECT id FROM consultation_members WHERE consultation_id=?", (room_id,))}
        if not set(ids) <= members:
            raise HTTPException(400, "このルームの参加者を指定してください")
        previous = {r["member_id"] for r in con.execute("SELECT member_id FROM selection_submitters WHERE room_id=?", (room_id,))}
        removed = previous - set(ids)
        for mid in removed:
            if con.execute("SELECT 1 FROM selection_proposals WHERE room_id=? AND member_id=?", (room_id, mid)).fetchone():
                raise HTTPException(409, "下書きがある提出者は外せません。本人が候補を外して保存してから変更してください")
            con.execute("DELETE FROM selection_submitters WHERE room_id=? AND member_id=?", (room_id, mid))
        con.executemany("INSERT OR IGNORE INTO selection_submitters(room_id,member_id) VALUES (?,?)", [(room_id, mid) for mid in ids])
    return {"ok": True}


@app.put("/api/rooms/{room_id}/selection/proposal")
def save_proposal(room_id: RoomId, body: Proposal, request: Request):
    with connection() as con:
        _, member, _ = context(con, room_id, request, phase="collecting")
        own = con.execute("SELECT * FROM selection_submitters WHERE room_id=? AND member_id=?", (room_id, member["id"])).fetchone()
        if not own:
            raise HTTPException(403, "主催者が指定した提出者だけが候補を提出できます")
        if own["submitted"] or own["version"] != body.version:
            raise HTTPException(409, "提出済み、または別の画面で変更されています")
        ids = [p.productId for p in body.products]
        if len(ids) != len(set(ids)):
            raise HTTPException(400, "同じ商品は1つにまとめてください")
        found = get_catalog().get_many(ids)
        if any(pid not in found or not found[pid]["available"] for pid in ids):
            raise HTTPException(400, "取り扱いのない商品か在庫切れが含まれています")
        con.execute("DELETE FROM selection_proposals WHERE room_id=? AND member_id=?", (room_id, member["id"]))
        con.executemany("INSERT INTO selection_proposals(room_id,member_id,product_id,reason,gift) VALUES (?,?,?,?,?)", [(room_id, member["id"], p.productId, p.reason, json.dumps(found[p.productId]["gift"], ensure_ascii=False)) for p in body.products])
        con.execute("UPDATE selection_submitters SET version=version+1 WHERE room_id=? AND member_id=?", (room_id, member["id"]))
    return {"version": body.version + 1}


@app.post("/api/rooms/{room_id}/selection/submit")
def submit(room_id: RoomId, request: Request):
    with connection() as con:
        _, member, _ = context(con, room_id, request, phase="collecting")
        own = con.execute("SELECT * FROM selection_submitters WHERE room_id=? AND member_id=?", (room_id, member["id"])).fetchone()
        if not own:
            raise HTTPException(403, "候補の提出権限がありません")
        if own["submitted"]:
            return {"ok": True}
        items = con.execute("SELECT product_id FROM selection_proposals WHERE room_id=? AND member_id=?", (room_id, member["id"])).fetchall()
        if not items:
            raise HTTPException(400, "商品を1〜3品保存してください")
        found = get_catalog().get_many([r["product_id"] for r in items])
        if any(r["product_id"] not in found or not found[r["product_id"]]["available"] for r in items):
            raise HTTPException(400, "商品情報が変わっています。候補を入れ替えてください")
        # 下書き後の価格変更も共有前に反映。
        for pid, product in found.items():
            con.execute("UPDATE selection_proposals SET gift=? WHERE room_id=? AND member_id=? AND product_id=?", (json.dumps(product["gift"], ensure_ascii=False), room_id, member["id"], pid))
        con.execute("UPDATE selection_submitters SET submitted=1 WHERE room_id=? AND member_id=?", (room_id, member["id"]))
        if not con.execute("SELECT 1 FROM selection_submitters WHERE room_id=? AND submitted=0", (room_id,)).fetchone():
            con.execute("UPDATE selection_state SET phase='voting' WHERE room_id=?", (room_id,))
    return {"ok": True}


@app.get("/api/rooms/{room_id}/selection/random")
def random_products(room_id: RoomId, request: Request, exclude: str = Query("", max_length=2000)):
    with connection() as con:
        room, member, _ = context(con, room_id, request, phase="collecting")
        own = con.execute("SELECT submitted FROM selection_submitters WHERE room_id=? AND member_id=?", (room_id, member["id"])).fetchone()
        if not own or own["submitted"]:
            raise HTTPException(403, "候補を入力できる提出者だけが利用できます")
    excluded = set(exclude.split(",")) - {""}
    catalog = get_catalog()
    if catalog.source == "shared":
        placeholders = ",".join(["%s"] * len(excluded))
        omit = f" AND p.product_id NOT IN ({placeholders})" if excluded else ""
        projection = ",".join("p." + name.strip() for name in PROJECTION.split(","))
        with read_only_cursor() as cursor:
            cursor.execute(f"SELECT {projection} FROM products p WHERE p.stock>0 AND p.price<=%s AND EXISTS (SELECT 1 FROM product_scenes s WHERE s.product_id=p.product_id AND s.scene_tag=%s){omit} ORDER BY RAND() LIMIT 3", (room["budget_total"], "送別", *excluded))
            result = [to_gift(row) for row in cursor.fetchall()]
    else:
        pool = [p for p in catalog.search("", "", False, None, room["budget_total"], 100)["results"] if p["id"] not in excluded]
        result = random.sample(pool, min(3, len(pool)))
    return {"results": result}


@app.post("/api/rooms/{room_id}/selection/notes", status_code=201)
def add_note(room_id: RoomId, body: Note, request: Request):
    with connection() as con:
        _, member, state = context(con, room_id, request)
        if state["phase"] == "decided":
            raise HTTPException(409, "決定後の情報は変更できません")
        con.execute("INSERT INTO selection_notes(room_id,member_id,kind,text) VALUES (?,?,?,?)", (room_id, member["id"], body.kind, body.text))
    return {"ok": True}


@app.put("/api/rooms/{room_id}/selection/products/{product_id}/vote")
def vote(room_id: RoomId, product_id: str, body: Vote, request: Request):
    with connection() as con:
        _, member, _ = context(con, room_id, request, phase="voting")
        require_candidate(con, room_id, product_id)
        con.execute("INSERT INTO selection_votes(room_id,member_id,product_id,stars) VALUES (?,?,?,?) ON CONFLICT(room_id,member_id,product_id) DO UPDATE SET stars=excluded.stars", (room_id, member["id"], product_id, body.stars))
    return {"ok": True}


@app.post("/api/rooms/{room_id}/selection/products/{product_id}/comments", status_code=201)
def comment(room_id: RoomId, product_id: str, body: Comment, request: Request):
    with connection() as con:
        _, member, _ = context(con, room_id, request, phase="voting")
        require_candidate(con, room_id, product_id)
        con.execute("INSERT INTO selection_comments(room_id,member_id,product_id,text) VALUES (?,?,?,?)", (room_id, member["id"], product_id, body.text))
    return {"ok": True}


@app.post("/api/rooms/{room_id}/selection/decision")
def decide(room_id: RoomId, body: Decision, request: Request):
    with connection() as con:
        room, _, state = context(con, room_id, request, organizer=True)
        if state["phase"] == "decided":
            raise HTTPException(409, "このルームは決定済みです")
        if state["phase"] != "voting":
            raise HTTPException(409, "提出者全員の提出後に決定できます")
        ids = body.productIds
        if len(ids) != len(set(ids)) or (body.mode == "single" and len(ids) != 1):
            raise HTTPException(400, "単品は1品、カタログは重複のない候補を選んでください")
        shared = candidates(con, room_id)
        if not set(ids) <= set(shared):
            raise HTTPException(400, "このルームの候補から選んでください")
        found = get_catalog().get_many(ids)
        if any(pid not in found or not found[pid]["available"] for pid in ids):
            raise HTTPException(400, "在庫切れ・取り扱い終了の商品が含まれています")
        if any(found[pid]["gift"]["price"] > room["budget_total"] for pid in ids):
            raise HTTPException(400, "総予算を超える商品が含まれています")
        decision = {"mode": body.mode, "products": [found[pid]["gift"] for pid in ids], "payment": "demo"}
        con.execute("UPDATE selection_state SET phase='decided',decision=? WHERE room_id=?", (json.dumps(decision, ensure_ascii=False), room_id))
    return {"ok": True}


# 名前参加・作成・本人Cookieは既存実装を利用。従来モードは変更しない。
app.include_router(rooms.app.router)
