"""名前参加から個人候補入力までのローカル検証。環境ファイル・共通DBは利用しない。"""
import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path as ApiPath, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from candidate_demo import DemoProductCatalog, DraftInput, prepare_slots, response as draft_response
from room_contract import RoomCreate

app = FastAPI(title="Giftia ローカル参加・候補入力（架空商品／SQLiteのみ）")
ORIGINS = [f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (3000, 3300)]
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type"])
RoomId = Annotated[int, ApiPath(ge=1, le=2147483647)]
catalog = DemoProductCatalog()


@app.middleware("http")
async def local_origin_only(request: Request, call_next):
    if request.method in {"POST", "PUT"} and request.headers.get("origin") not in (None, *ORIGINS):
        return JSONResponse(status_code=403, content={"detail": "この画面からは操作できません"})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(sqlite3.Error)
async def storage_error(request: Request, error: sqlite3.Error):
    return JSONResponse(status_code=503, content={"detail": "ローカルの保存先を利用できません。時間をおいて再試行してください"})


@contextmanager
def connection():
    filename = Path(os.environ.get("GIFTIA_LOCAL_ROOMS_DB", Path(__file__).resolve().parent.parent / ".local" / "room-preview.sqlite3"))
    filename.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(filename, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        con.executescript('''
          CREATE TABLE IF NOT EXISTS consultations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            budget_total INTEGER NOT NULL CHECK(budget_total>=1),
            member_count INTEGER NOT NULL CHECK(member_count>=1),
            deliver_by TEXT NOT NULL, organizer_id INTEGER
          );
          CREATE TABLE IF NOT EXISTS consultation_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consultation_id INTEGER NOT NULL REFERENCES consultations(id),
            nickname TEXT NOT NULL, UNIQUE(consultation_id, nickname)
          );
          CREATE TABLE IF NOT EXISTS local_member_sessions (
            token_hash TEXT PRIMARY KEY,
            room_id INTEGER NOT NULL REFERENCES consultations(id),
            member_id INTEGER NOT NULL REFERENCES consultation_members(id),
            expires_at INTEGER NOT NULL
          );
          CREATE TABLE IF NOT EXISTS local_candidate_drafts (
            room_id INTEGER NOT NULL REFERENCES consultations(id),
            member_id INTEGER NOT NULL REFERENCES consultation_members(id),
            version INTEGER NOT NULL, slots TEXT NOT NULL,
            PRIMARY KEY(room_id, member_id)
          );
        ''')
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def cookie_name(room_id):
    return f"giftia_local_room_{room_id}"


def session_member(con, room_id, request):
    token = request.cookies.get(cookie_name(room_id))
    if not token:
        return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    return con.execute('''SELECT m.id, m.nickname FROM local_member_sessions s
        JOIN consultation_members m ON m.id=s.member_id AND m.consultation_id=s.room_id
        WHERE s.token_hash=? AND s.room_id=? AND s.expires_at>unixepoch()''', (digest, room_id)).fetchone()


def set_session(con, room_id, member_id, response):
    # URLやレスポンスJSONに識別用トークンを載せない。保存先にはハッシュだけを残す。
    token = secrets.token_urlsafe(32)
    con.execute('''INSERT INTO local_member_sessions(token_hash,room_id,member_id,expires_at)
                   VALUES (?,?,?,unixepoch()+2592000)''',
                (hashlib.sha256(token.encode()).hexdigest(), room_id, member_id))
    response.set_cookie(cookie_name(room_id), token, max_age=2592000, httponly=True,
                        samesite="strict", secure=False, path=f"/api/rooms/{room_id}")


def room_row(con, room_id):
    row = con.execute('''SELECT c.*, m.nickname AS organizer_nickname FROM consultations c
        JOIN consultation_members m ON m.id=c.organizer_id AND m.consultation_id=c.id
        WHERE c.id=?''', (room_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "ルームが見つかりません")
    return row


def room_payload(row):
    return {"room_id": row["id"], "title": row["title"], "budget_total": row["budget_total"],
            "member_count": row["member_count"], "deliver_by": row["deliver_by"],
            "organizer_nickname": row["organizer_nickname"],
            "price_per_person": (row["budget_total"]+row["member_count"]-1)//row["member_count"],
            "room_path": f'/rooms/{row["id"]}', "local_preview": True}


def own_member(con, room_id, request):
    room = room_row(con, room_id)
    member = session_member(con, room_id, request)
    if member is None:
        raise HTTPException(401, "ルームに名前で参加してから入力してください")
    return room, member


class JoinInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    nickname: str = Field(min_length=1, max_length=30)


@app.get("/api/search")
def search(q: str = "", category: str = "", indiv_wrap: bool = False,
           price_min: int | None = Query(None, ge=0), price_max: int | None = Query(None, ge=0),
           limit: int = Query(20, ge=1, le=100)):
    return catalog.search(q, category, indiv_wrap, price_min, price_max, limit)


@app.post("/api/rooms", status_code=201)
def create_room(body: RoomCreate, response: Response):
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        room_id = con.execute('''INSERT INTO consultations(title,budget_total,member_count,deliver_by)
            VALUES (?,?,?,?)''', (body.title, body.budget_total, body.member_count, body.deliver_by.isoformat())).lastrowid
        member_id = con.execute("INSERT INTO consultation_members(consultation_id,nickname) VALUES (?,?)",
                                (room_id, body.nickname)).lastrowid
        con.execute("UPDATE consultations SET organizer_id=? WHERE id=?", (member_id, room_id))
        set_session(con, room_id, member_id, response)
        return room_payload(room_row(con, room_id))


@app.get("/api/rooms/{room_id}")
def get_room(room_id: RoomId):
    with connection() as con:
        return room_payload(room_row(con, room_id))


@app.get("/api/rooms/{room_id}/me")
def get_me(room_id: RoomId, request: Request):
    with connection() as con:
        _, member = own_member(con, room_id, request)
        return {"id": str(member["id"]), "name": member["nickname"]}


@app.post("/api/rooms/{room_id}/members", status_code=201)
def join_room(room_id: RoomId, body: JoinInput, request: Request, response: Response):
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        room_row(con, room_id)
        member = session_member(con, room_id, request)
        if member:
            if member["nickname"] != body.nickname:
                raise HTTPException(409, "このブラウザーではすでに別の名前で参加しています")
            response.status_code = 200
            return {"id": str(member["id"]), "name": member["nickname"]}
        try:
            member_id = con.execute("INSERT INTO consultation_members(consultation_id,nickname) VALUES (?,?)",
                                    (room_id, body.nickname)).lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(409, "このルームではその名前が使われています。別の名前を入力してください") from None
        set_session(con, room_id, member_id, response)
        return {"id": str(member_id), "name": body.nickname}


def personal_payload(room, member, row, products=None):
    result = draft_response({"id": str(room["id"]), "title": room["title"],
                             "budgetTotal": room["budget_total"], "members": []},
                            {"id": str(member["id"]), "name": member["nickname"]},
                            row, catalog, products)
    result["localParticipation"] = True
    return result


@app.get("/api/rooms/{room_id}/candidate-draft")
def get_draft(room_id: RoomId, request: Request):
    with connection() as con:
        room, member = own_member(con, room_id, request)
        row = con.execute("SELECT version,slots FROM local_candidate_drafts WHERE room_id=? AND member_id=?",
                          (room_id, member["id"])).fetchone()
        return personal_payload(room, member, row)


@app.put("/api/rooms/{room_id}/candidate-draft")
def save_draft(room_id: RoomId, body: DraftInput, request: Request):
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        room, member = own_member(con, room_id, request)
        slots, products = prepare_slots(body, catalog)
        row = con.execute("SELECT version FROM local_candidate_drafts WHERE room_id=? AND member_id=?",
                          (room_id, member["id"])).fetchone()
        version = row["version"] if row else 0
        if version != body.version:
            raise HTTPException(409, "別の画面で保存されています。入力内容を控え、保存済み内容を読み直してください")
        version += 1
        text = json.dumps(slots, ensure_ascii=False)
        con.execute('''INSERT INTO local_candidate_drafts(room_id,member_id,version,slots) VALUES (?,?,?,?)
            ON CONFLICT(room_id,member_id) DO UPDATE SET version=excluded.version,slots=excluded.slots''',
                    (room_id, member["id"], version, text))
        return personal_payload(room, member, {"version": version, "slots": text}, products)
