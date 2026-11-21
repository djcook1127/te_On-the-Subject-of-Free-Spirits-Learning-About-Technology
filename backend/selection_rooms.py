"""Issue #22・24: 名前参加から共同決定まで。SQLite／共通MySQLを明示選択。"""
import json
import os
import random
import sqlite3
from contextlib import contextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

import local_rooms
import shared_rooms
from selection_store import SQLiteStore, MySQLStore
from candidate_demo import get_catalog
from product_catalog import PROJECTION, read_only_cursor, to_gift
from room_contract import RoomSettings

storage_mode = os.environ.get("GIFTIA_ROOM_STORAGE", "sqlite")
if storage_mode not in {"sqlite", "shared"}:
    raise RuntimeError("GIFTIA_ROOM_STORAGEはsqliteまたはsharedを指定してください")
rooms = shared_rooms if storage_mode == "shared" else local_rooms

app = FastAPI(title="Giftia みんなで決める送別ギフト")
app.add_middleware(CORSMiddleware, allow_origins=rooms.ORIGINS, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type"])
app.middleware("http")(rooms.local_origin_only)
app.add_exception_handler(sqlite3.Error, local_rooms.storage_error)
RoomId = rooms.RoomId


@contextmanager
def connection():
    if rooms is shared_rooms:
        with shared_rooms.connection() as con:
            yield con
        return
    with rooms.connection() as con:
        initialize_published = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='selection_published_proposals'").fetchone() is None
        con.executescript('''
          CREATE TABLE IF NOT EXISTS selection_state (
            room_id INTEGER PRIMARY KEY REFERENCES consultations(id),
            phase TEXT NOT NULL DEFAULT 'collecting', decision TEXT,
            organizer_submitted INTEGER NOT NULL DEFAULT 1
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
          CREATE TABLE IF NOT EXISTS selection_published_proposals (
            room_id INTEGER NOT NULL, member_id INTEGER NOT NULL, product_id TEXT NOT NULL,
            reason TEXT NOT NULL, gift TEXT NOT NULL, curated INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(room_id,member_id,product_id),
            FOREIGN KEY(room_id,member_id) REFERENCES selection_submitters(room_id,member_id)
          );
          CREATE TABLE IF NOT EXISTS selection_room_comments (
            id INTEGER PRIMARY KEY, room_id INTEGER NOT NULL REFERENCES consultations(id),
            member_id INTEGER NOT NULL REFERENCES consultation_members(id), text TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'その他'
          );
        ''')
        if "organizer_submitted" not in {r["name"] for r in con.execute("PRAGMA table_info(selection_state)")}:
            con.execute("ALTER TABLE selection_state ADD COLUMN organizer_submitted INTEGER NOT NULL DEFAULT 1")
        if "kind" not in {r["name"] for r in con.execute("PRAGMA table_info(selection_room_comments)")}:
            con.execute("ALTER TABLE selection_room_comments ADD COLUMN kind TEXT NOT NULL DEFAULT 'その他'")
        if "curated" not in {r["name"] for r in con.execute("PRAGMA table_info(selection_published_proposals)")}:
            con.execute("ALTER TABLE selection_published_proposals ADD COLUMN curated INTEGER NOT NULL DEFAULT 0")
        if initialize_published:
            con.execute("""INSERT OR IGNORE INTO selection_published_proposals(room_id,member_id,product_id,reason,gift)
                SELECT p.room_id,p.member_id,p.product_id,p.reason,p.gift FROM selection_proposals p
                JOIN selection_submitters s ON s.room_id=p.room_id AND s.member_id=p.member_id WHERE s.submitted=1""")
            con.commit()
        con.execute("BEGIN IMMEDIATE")
        yield SQLiteStore(con)


def context(con, room_id, request, organizer=False, phase=None, read_only=False, lock_mode=True):
    room, member = rooms.own_member(con, room_id, request, lock=False if read_only else lock_mode)
    if organizer and member["id"] != room["organizer_id"]:
        raise HTTPException(403, "主催者だけが操作できます")
    state = con.execute("SELECT * FROM selection_state WHERE room_id=%s", (room_id,)).fetchone()
    if state is None:
        if not read_only:
            con.ensure_state(room_id)
        state = {"phase": "collecting", "decision": None, "organizer_submitted": 0}
    if phase and state["phase"] != phase:
        raise HTTPException(409, "ルームの段階が変わっています。最新の内容を読み直してください")
    return room, member, state


def checked_products(con, ids):
    catalog = get_catalog()
    if isinstance(con, MySQLStore) and catalog.source == "shared":
        if not ids:
            return {}
        placeholders = ','.join(['%s'] * len(ids))
        rows = con.execute(f"SELECT {PROJECTION},stock FROM products WHERE product_id IN ({placeholders})", tuple(ids))
        return {r["product_id"]: {"gift": to_gift(r), "available": r["stock"] > 0} for r in rows}
    return catalog.get_many(ids)


def require_proposal_ready(room, member, state):
    if member["id"] != room["organizer_id"] and not state["organizer_submitted"]:
        raise HTTPException(409, "開設者が最初の候補を提出してから追加できます。コメントは先に共有できます")


def candidates(con, room_id):
    return group_candidates(con.execute("SELECT product_id,reason,gift FROM selection_published_proposals WHERE room_id=%s ORDER BY product_id,reason", (room_id,)))


def group_candidates(rows):
    # 提案元・提案者数を共有レスポンスへ出さず、重複商品を1件にまとめる。
    grouped = {}
    for row in sorted(rows, key=lambda r: (r["product_id"], r["reason"])):
        item = grouped.setdefault(row["product_id"], {"gift": json.loads(row["gift"]), "reasons": []})
        if row["reason"] and row["reason"] not in item["reasons"]:
            item["reasons"].append(row["reason"])
    return grouped


def require_candidate(con, room_id, product_id):
    if not con.execute("SELECT 1 FROM selection_published_proposals WHERE room_id=%s AND product_id=%s", (room_id, product_id)).fetchone():
        raise HTTPException(404, "このルームの候補ではありません")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Product(Input):
    productId: str = Field(min_length=1, max_length=100)
    reason: str = Field(default="", max_length=100)


class Proposal(Input):
    version: int = Field(strict=True, ge=0)
    products: list[Product] = Field(max_length=10)


class Note(Input):
    kind: Literal["好み", "アレルギー・避けたいもの", "その他"]
    text: str = Field(min_length=1, max_length=300)


class Comment(Input):
    kind: Literal["好み", "避けたいもの", "その他"] = "その他"
    text: str = Field(min_length=1, max_length=300)


class Vote(Input):
    stars: int = Field(strict=True, ge=1, le=3)


class Decision(Input):
    mode: Literal["single", "catalog"]
    productIds: list[str] = Field(min_length=1, max_length=10)
    reasonSources: list[Literal["votes", "comments", "other"]] = Field(min_length=1, max_length=3)
    otherReason: str = Field(default="", max_length=300)


class Curation(Input):
    productId: str = Field(min_length=1, max_length=100)
    replaceProductId: str | None = Field(default=None, min_length=1, max_length=100)
    reason: str = Field(default="", max_length=100)


class RemoveCandidate(Input):
    productId: str = Field(min_length=1, max_length=100)


@app.get("/api/search")
def search(q: str = "", category: str = "", indiv_wrap: bool = False,
           price_min: int | None = Query(None, ge=0), price_max: int | None = Query(None, ge=0),
           limit: int = Query(20, ge=1, le=100)):
    return get_catalog().search(q, category, indiv_wrap, price_min, price_max, limit)


@app.get("/api/rooms/{room_id}/selection")
def get_selection(room_id: RoomId, request: Request):
    with connection() as con:
        return selection_payload(con, room_id, request)


def selection_records(con, room_id, member_id, organizer, phase):
    if isinstance(con, MySQLStore):
        return con.selection_snapshot(room_id, member_id, organizer, phase)
    # SQLiteの単体検証ではJSON集約に依存しない同等の取得を使う。
    own = con.execute("SELECT * FROM selection_submitters WHERE room_id=%s AND member_id=%s", (room_id, member_id)).fetchone()
    def rows(sql, params):
        return [dict(r) for r in con.execute(sql, params)]
    return {
        "own": [dict(own)] if own else [],
        "personal": rows("SELECT product_id,reason,gift FROM selection_proposals WHERE room_id=%s AND member_id=%s", (room_id, member_id)),
        "published": rows("SELECT member_id,product_id,reason,gift FROM selection_published_proposals WHERE room_id=%s", (room_id,)),
        "members": rows("SELECT id,nickname FROM consultation_members WHERE consultation_id=%s", (room_id,)) if organizer else [],
        "totals": rows("SELECT product_id,SUM(stars) AS total,COUNT(*) AS voters FROM selection_votes WHERE room_id=%s GROUP BY product_id", (room_id,)) if phase != "collecting" else [],
        "own_votes": rows("SELECT product_id,stars FROM selection_votes WHERE room_id=%s AND member_id=%s", (room_id, member_id)) if phase != "collecting" else [],
        "old_notes": rows("SELECT id,kind,text FROM selection_notes WHERE room_id=%s", (room_id,)),
        "old_comments": rows("SELECT id,product_id,text FROM selection_comments WHERE room_id=%s", (room_id,)),
        "room_comments": rows("SELECT id,kind,text FROM selection_room_comments WHERE room_id=%s", (room_id,)),
    }


def selection_payload(con, room_id, request, context_data=None):
    room, member, state = context_data or context(con, room_id, request, read_only=True)
    is_organizer = member["id"] == room["organizer_id"]
    records = selection_records(con, room_id, member["id"], is_organizer, state["phase"])
    own = records["own"][0] if records["own"] else None
    personal = sorted(records["personal"], key=lambda r: r["product_id"])
    shared = group_candidates(records["published"])
    totals = {r["product_id"]: r for r in records["totals"]}
    own_votes = {r["product_id"]: r["stars"] for r in records["own_votes"]}
    visible = [{**item, "totalStars": int(totals.get(pid, {}).get("total", 0)), "voters": totals.get(pid, {}).get("voters", 0), "myStars": own_votes.get(pid)} for pid, item in shared.items()]
    visible.sort(key=lambda c: (-c["totalStars"], c["gift"]["id"]))
    members = sorted(records["members"], key=lambda r: r["id"])
    notes = sorted(records["old_notes"], key=lambda r: r["id"])
    comments = [{"id": f'note-{r["id"]}', "kind": "避けたいもの" if r["kind"] == "アレルギー・避けたいもの" else r["kind"], "text": r["text"]} for r in notes]
    comments.extend({"id": f'legacy-{r["id"]}', "kind": "その他", "text": r["text"], "legacyProduct": shared.get(r["product_id"], {}).get("gift", {}).get("name", r["product_id"])} for r in sorted(records["old_comments"], key=lambda r: r["id"]))
    comments.extend({"id": f'room-{r["id"]}', "kind": r["kind"], "text": r["text"]} for r in sorted(records["room_comments"], key=lambda r: r["id"]))
    submitted = len({r["member_id"] for r in records["published"]})
    ready = bool(state["organizer_submitted"])
    return {"room": {"id": str(room_id), "title": room["title"], "budgetTotal": room["budget_total"], "memberCount": room["member_count"], "deliverBy": str(room["deliver_by"])},
            "initialProposalSubmitted": ready,
            "storageSource": getattr(rooms, "STORAGE_SOURCE", "sqlite"),
            "phase": state["phase"], "catalogSource": get_catalog().source,
            "me": {"id": member["id"], "name": member["nickname"], "isOrganizer": is_organizer,
                   "canPropose": state["phase"] == "collecting" and (is_organizer or ready), "submitted": bool(own and own["submitted"]), "version": own["version"] if own else 0},
            "members": [{"id": m["id"], "name": m["nickname"], "canPropose": True} for m in members] if is_organizer else [],
            "progress": {"designated": len(members), "submitted": submitted, "candidateCount": len(shared), "candidateLimit": 10},
            "notes": notes if state["phase"] != "voting" else [],
            "ownProducts": [{"productId": r["product_id"], "reason": r["reason"], "gift": json.loads(r["gift"])} for r in personal],
            "candidates": visible, "comments": comments, "decision": json.loads(state["decision"]) if state["decision"] else None}

@app.put("/api/rooms/{room_id}/selection/room")
def edit_room(room_id: RoomId, body: RoomSettings, request: Request):
    with connection() as con:
        room, member, state = context(con, room_id, request, organizer=True, phase="collecting")
        con.execute("UPDATE consultations SET title=%s,budget_total=%s,member_count=%s,deliver_by=%s WHERE id=%s",
                    (body.title, body.budget_total, body.member_count, body.deliver_by.isoformat(), room_id))
        room = {**dict(room), **body.model_dump(), "deliver_by": body.deliver_by.isoformat()}
        result = selection_payload(con, room_id, request, (room, member, state))
    return {"ok": True, "selection": result}


@app.put("/api/rooms/{room_id}/selection/submitters")
def set_submitters(room_id: RoomId, request: Request):
    raise HTTPException(410, "全員が候補を提出できます。提出者の指定は不要になりました")


@app.put("/api/rooms/{room_id}/selection/proposal")
def save_proposal(room_id: RoomId, body: Proposal, request: Request):
    with connection() as con:
        room, member, state = context(con, room_id, request, phase="collecting")
        require_proposal_ready(room, member, state)
        save_draft(con, room_id, member, body)
    return {"version": body.version + 1}


def save_draft(con, room_id, member, body):
    own = con.execute("SELECT * FROM selection_submitters WHERE room_id=%s AND member_id=%s", (room_id, member["id"])).fetchone()
    if (own["version"] if own else 0) != body.version:
        raise HTTPException(409, "別の画面で変更されています。最新の下書きを読み直してください")
    ids = [p.productId for p in body.products]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "同じ商品は1つにまとめてください")
    found = checked_products(con, ids)
    if any(pid not in found or not found[pid]["available"] for pid in ids):
        raise HTTPException(400, "取り扱いのない商品か在庫切れが含まれています")
    if not own:
        con.add_submitters(room_id, [member["id"]])
    con.execute("DELETE FROM selection_proposals WHERE room_id=%s AND member_id=%s", (room_id, member["id"]))
    con.executemany("INSERT INTO selection_proposals(room_id,member_id,product_id,reason,gift) VALUES (%s,%s,%s,%s,%s)", [(room_id, member["id"], p.productId, p.reason, json.dumps(found[p.productId]["gift"], ensure_ascii=False)) for p in body.products])
    con.execute("UPDATE selection_submitters SET version=version+1,submitted=0 WHERE room_id=%s AND member_id=%s", (room_id, member["id"]))
    return found

@app.post("/api/rooms/{room_id}/selection/submit")
def submit(room_id: RoomId, request: Request, body: Proposal | None = None):
    with connection() as con:
        room, member, state = context(con, room_id, request, phase="collecting")
        require_proposal_ready(room, member, state)
        saved_products = save_draft(con, room_id, member, body) if body is not None else None
        items = con.execute("SELECT product_id,reason FROM selection_proposals WHERE room_id=%s AND member_id=%s", (room_id, member["id"])).fetchall()
        if not items:
            raise HTTPException(400, "商品を1〜10品保存してください")
        ids = {r["product_id"] for r in items}
        others = {r["product_id"] for r in con.execute("SELECT DISTINCT product_id FROM selection_published_proposals WHERE room_id=%s AND (member_id<>%s OR curated=1)", (room_id, member["id"]))}
        if len(ids | others) > 10:
            raise HTTPException(409, "ルームの候補は合計10品までです。候補を減らすか、最新の一覧を確認してください")
        found = saved_products if saved_products is not None else checked_products(con, list(ids))
        if any(pid not in found or not found[pid]["available"] for pid in ids):
            raise HTTPException(400, "商品情報が変わっています。候補を入れ替えてください")
        con.execute("DELETE FROM selection_published_proposals WHERE room_id=%s AND member_id=%s AND curated=0", (room_id, member["id"]))
        con.publish_products([(room_id, member["id"], r["product_id"], r["reason"], json.dumps(found[r["product_id"]]["gift"], ensure_ascii=False)) for r in items])
        if saved_products is None:
            for pid in ids:
                con.execute("UPDATE selection_proposals SET gift=%s WHERE room_id=%s AND member_id=%s AND product_id=%s", (json.dumps(found[pid]["gift"], ensure_ascii=False), room_id, member["id"], pid))
        con.execute("UPDATE selection_submitters SET submitted=1 WHERE room_id=%s AND member_id=%s", (room_id, member["id"]))
        if member["id"] == room["organizer_id"]:
            con.execute("UPDATE selection_state SET organizer_submitted=1 WHERE room_id=%s", (room_id,))
            state = {**dict(state), "organizer_submitted": 1}
        result = selection_payload(con, room_id, request, (room, member, state))
    return {"ok": True, "selection": result}


def remove_public_product(con, room_id, product_id):
    require_candidate(con, room_id, product_id)
    con.execute("""UPDATE selection_submitters SET submitted=0 WHERE room_id=%s AND member_id IN
        (SELECT member_id FROM selection_published_proposals WHERE room_id=%s AND product_id=%s)""", (room_id, room_id, product_id))
    con.execute("DELETE FROM selection_published_proposals WHERE room_id=%s AND product_id=%s", (room_id, product_id))


@app.post("/api/rooms/{room_id}/selection/curation")
def curate(room_id: RoomId, body: Curation, request: Request):
    with connection() as con:
        room, member, state = context(con, room_id, request, organizer=True, phase="collecting")
        shared = candidates(con, room_id)
        if body.replaceProductId and body.replaceProductId not in shared:
            raise HTTPException(404, "差し替え対象の候補がありません")
        target = (set(shared) - ({body.replaceProductId} if body.replaceProductId else set())) | {body.productId}
        if len(target) > 10:
            raise HTTPException(409, "候補は最大10品です。差し替えを選ぶか、候補を減らしてください")
        found = checked_products(con, [body.productId])
        if body.productId not in found or not found[body.productId]["available"]:
            raise HTTPException(400, "商品の取り扱い・在庫を確認できません")
        if body.replaceProductId:
            remove_public_product(con, room_id, body.replaceProductId)
        con.add_submitters(room_id, [member["id"]])
        con.curate_product((room_id, member["id"], body.productId, body.reason, json.dumps(found[body.productId]["gift"], ensure_ascii=False)))
        con.execute("UPDATE selection_state SET organizer_submitted=1 WHERE room_id=%s", (room_id,))
        result = selection_payload(con, room_id, request, (room, member, {**dict(state), "organizer_submitted": 1}))
    return {"ok": True, "selection": result}


@app.post("/api/rooms/{room_id}/selection/curation/remove")
def remove_curated(room_id: RoomId, body: RemoveCandidate, request: Request):
    with connection() as con:
        room, member, state = context(con, room_id, request, organizer=True, phase="collecting")
        remove_public_product(con, room_id, body.productId)
        result = selection_payload(con, room_id, request, (room, member, state))
    return {"ok": True, "selection": result}


@app.post("/api/rooms/{room_id}/selection/start-voting")
def start_voting(room_id: RoomId, request: Request):
    with connection() as con:
        room, member, state = context(con, room_id, request, organizer=True, phase="collecting")
        count = len(candidates(con, room_id))
        if not 1 <= count <= 10:
            raise HTTPException(400, "提出済みの候補が1〜10品あることを確認してください")
        con.execute("UPDATE selection_state SET phase='voting' WHERE room_id=%s", (room_id,))
        result = selection_payload(con, room_id, request, (room, member, {**dict(state), "phase": "voting"}))
    return {"ok": True, "selection": result}


@app.get("/api/rooms/{room_id}/selection/categories")
def get_categories(room_id: RoomId, request: Request):
    with connection() as con:
        room, _, _ = context(con, room_id, request, phase="collecting", read_only=True)
    return {"categories": get_catalog().categories(room["budget_total"])}


@app.get("/api/rooms/{room_id}/selection/random")
def random_products(room_id: RoomId, request: Request, category: str = Query(..., min_length=1, max_length=100), exclude: str = Query("", max_length=2000)):
    with connection() as con:
        room, member, _ = context(con, room_id, request, phase="collecting", read_only=True)

    category = category.strip()
    if not category:
        raise HTTPException(400, "カテゴリーを選んでください")
    excluded = set(exclude.split(",")) - {""}
    catalog = get_catalog()
    if catalog.source == "shared":
        placeholders = ",".join(["%s"] * len(excluded))
        omit = f" AND p.product_id NOT IN ({placeholders})" if excluded else ""
        projection = ",".join("p." + name.strip() for name in PROJECTION.split(","))
        with read_only_cursor() as cursor:
            cursor.execute(f"SELECT {projection} FROM products p WHERE p.stock>0 AND p.price>=%s AND p.price<=%s AND p.rating>=4.0 AND p.category=%s AND EXISTS (SELECT 1 FROM product_scenes s WHERE s.product_id=p.product_id AND s.scene_tag=%s){omit} ORDER BY RAND() LIMIT 3", ((room["budget_total"] * 8 + 9) // 10, room["budget_total"], category, "送別", *excluded))
            result = [to_gift(row) for row in cursor.fetchall()]
    else:
        pool = [p for p in catalog.search("", category, False, (room["budget_total"] * 8 + 9) // 10, room["budget_total"], 100)["results"] if p["id"] not in excluded and p["rating"] >= 4]
        result = random.sample(pool, min(3, len(pool)))
    return {"results": result}


@app.post("/api/rooms/{room_id}/selection/notes", status_code=201)
def add_note(room_id: RoomId, body: Note, request: Request):
    with connection() as con:
        _, member, _ = context(con, room_id, request, phase="collecting")
        con.execute("INSERT INTO selection_notes(room_id,member_id,kind,text) VALUES (%s,%s,%s,%s)", (room_id, member["id"], body.kind, body.text))
    return {"ok": True}


@app.put("/api/rooms/{room_id}/selection/products/{product_id}/vote")
def vote(room_id: RoomId, product_id: str, body: Vote, request: Request):
    with connection() as con:
        room, member, state = context(con, room_id, request, phase="voting", lock_mode="shared")
        require_candidate(con, room_id, product_id)
        con.save_vote((room_id, member["id"], product_id, body.stars))
        result = selection_payload(con, room_id, request, (room, member, state))
    return {"ok": True, "selection": result}


@app.post("/api/rooms/{room_id}/selection/comments", status_code=201)
def comment(room_id: RoomId, body: Comment, request: Request):
    with connection() as con:
        room, member, state = context(con, room_id, request, phase="collecting")
        con.execute("INSERT INTO selection_room_comments(room_id,member_id,kind,text) VALUES (%s,%s,%s,%s)", (room_id, member["id"], body.kind, body.text))
        result = selection_payload(con, room_id, request, (room, member, state))
    return {"ok": True, "selection": result}


@app.post("/api/rooms/{room_id}/selection/decision")
def decide(room_id: RoomId, body: Decision, request: Request):
    if len(body.reasonSources) != len(set(body.reasonSources)):
        raise HTTPException(400, "決定理由は重複なく選んでください")
    if "other" in body.reasonSources and not body.otherReason:
        raise HTTPException(400, "その他の決定理由を入力してください")
    if "other" not in body.reasonSources and body.otherReason:
        raise HTTPException(400, "自由入力の理由を残す場合はその他を選んでください")
    with connection() as con:
        room, member, state = context(con, room_id, request, organizer=True)
        if state["phase"] == "decided":
            raise HTTPException(409, "このルームは決定済みです")
        if state["phase"] != "voting":
            raise HTTPException(409, "主催者が投票開始を押してから決定できます")
        ids = body.productIds
        if len(ids) != len(set(ids)) or (body.mode == "single" and len(ids) != 1):
            raise HTTPException(400, "単品は1品、カタログは重複のない候補を選んでください")
        shared = candidates(con, room_id)
        if not set(ids) <= set(shared):
            raise HTTPException(400, "このルームの候補から選んでください")
        found = checked_products(con, ids)
        if any(pid not in found or not found[pid]["available"] for pid in ids):
            raise HTTPException(400, "在庫切れ・取り扱い終了の商品が含まれています")
        if any(found[pid]["gift"]["price"] > room["budget_total"] for pid in ids):
            raise HTTPException(400, "総予算を超える商品が含まれています")
        decision = {"mode": body.mode, "products": [found[pid]["gift"] for pid in ids], "payment": "demo", "reasonSources": body.reasonSources, "otherReason": body.otherReason}
        con.execute("UPDATE selection_state SET phase='decided',decision=%s WHERE room_id=%s", (json.dumps(decision, ensure_ascii=False), room_id))
        result = selection_payload(con, room_id, request, (room, member, {**dict(state), "phase": "decided", "decision": json.dumps(decision, ensure_ascii=False)}))
    return {"ok": True, "selection": result}


# 名前参加・作成・本人Cookieは既存実装を利用。従来モードは変更しない。
app.include_router(shared_rooms.router if rooms is shared_rooms else local_rooms.app.router)
