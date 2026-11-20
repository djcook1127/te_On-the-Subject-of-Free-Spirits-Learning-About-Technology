"""既存MySQLルーム・参加者を使う。実行時にDDLを流さない。"""
import hashlib
import secrets
from contextlib import contextmanager

import pymysql
from fastapi import APIRouter, HTTPException, Request, Response

import local_rooms
from room_contract import RoomCreate
from selection_store import MySQLStore

STORAGE_SOURCE = "shared"
RoomId = local_rooms.RoomId
ORIGINS = local_rooms.ORIGINS
local_origin_only = local_rooms.local_origin_only
router = APIRouter()


def _connect():
    from database import get_connection
    return get_connection()


def rollback(raw):
    if raw is not None:
        try:
            raw.rollback()
        except (pymysql.MySQLError, OSError):
            pass


@contextmanager
def connection():
    raw = None
    try:
        raw = _connect()
        raw.begin()
        yield MySQLStore(raw)
        raw.commit()
    except (pymysql.MySQLError, EnvironmentError):
        rollback(raw)
        raise HTTPException(503, "共通DBのルーム情報を利用できません。接続と追加テーブルを確認してください") from None
    except Exception:
        rollback(raw)
        raise
    finally:
        if raw is not None:
            raw.close()


def cookie_name(room_id):
    # SQLiteと同じ数字のルームがあっても本人情報を混同しない。
    return f"giftia_shared_room_{room_id}"


def set_session(con, room_id, member_id, response):
    token = secrets.token_urlsafe(32)
    con.execute("INSERT INTO consultation_member_sessions(token_hash,room_id,member_id,expires_at) VALUES (%s,%s,%s,UNIX_TIMESTAMP()+2592000)", (hashlib.sha256(token.encode()).hexdigest(), room_id, member_id))
    response.set_cookie(cookie_name(room_id), token, max_age=2592000, httponly=True,
                        samesite="strict", secure=False, path=f"/api/rooms/{room_id}")


def session_member(con, room_id, request):
    token = request.cookies.get(cookie_name(room_id))
    if not token:
        return None
    return con.execute('''SELECT m.id,m.nickname FROM consultation_member_sessions s
        JOIN consultation_members m ON m.id=s.member_id AND m.consultation_id=s.room_id
        WHERE s.token_hash=%s AND s.room_id=%s AND s.expires_at>UNIX_TIMESTAMP()''',
        (hashlib.sha256(token.encode()).hexdigest(), room_id)).fetchone()


def room_row(con, room_id):
    # 全更新がこの親行を先にロックする。5人・3品・段階の判定と更新を直列化。
    room = con.execute('''SELECT c.*,m.nickname AS organizer_nickname FROM consultations c
        JOIN consultation_members m ON m.id=c.organizer_id AND m.consultation_id=c.id
        WHERE c.id=%s FOR UPDATE''', (room_id,)).fetchone()
    if room is None:
        raise HTTPException(404, "ルームが見つかりません")
    return room


def own_member(con, room_id, request):
    room = room_row(con, room_id)
    member = session_member(con, room_id, request)
    if member is None:
        raise HTTPException(401, "ルームに名前で参加してから入力してください")
    return room, member


def room_payload(row):
    return {"room_id": row["id"], "title": row["title"], "budget_total": row["budget_total"],
            "member_count": row["member_count"], "deliver_by": row["deliver_by"].isoformat(),
            "organizer_nickname": row["organizer_nickname"],
            "price_per_person": (row["budget_total"] + row["member_count"] - 1) // row["member_count"],
            "room_path": f'/rooms/{row["id"]}', "selection_enabled": True, "storage_source": "shared"}


@router.post("/api/rooms", status_code=201)
def create_room(body: RoomCreate, response: Response):
    with connection() as con:
        room_id = con.execute("INSERT INTO consultations(title,budget_total,member_count,deliver_by) VALUES (%s,%s,%s,%s)", (body.title, body.budget_total, body.member_count, body.deliver_by)).lastrowid
        member_id = con.execute("INSERT INTO consultation_members(consultation_id,nickname) VALUES (%s,%s)", (room_id, body.nickname)).lastrowid
        con.execute("UPDATE consultations SET organizer_id=%s WHERE id=%s", (member_id, room_id))
        con.ensure_state(room_id)
        set_session(con, room_id, member_id, response)
        return room_payload(room_row(con, room_id))


@router.get("/api/rooms/{room_id}")
def get_room(room_id: RoomId):
    with connection() as con:
        return room_payload(room_row(con, room_id))


@router.get("/api/rooms/{room_id}/me")
def get_me(room_id: RoomId, request: Request):
    with connection() as con:
        _, member = own_member(con, room_id, request)
        return {"id": str(member["id"]), "name": member["nickname"]}


@router.post("/api/rooms/{room_id}/members", status_code=201)
def join_room(room_id: RoomId, body: local_rooms.JoinInput, request: Request, response: Response):
    with connection() as con:
        room_row(con, room_id)
        member = session_member(con, room_id, request)
        if member:
            if member["nickname"] != body.nickname:
                raise HTTPException(409, "このブラウザーではすでに別の名前で参加しています")
            response.status_code = 200
            return {"id": str(member["id"]), "name": member["nickname"]}
        try:
            member_id = con.execute("INSERT INTO consultation_members(consultation_id,nickname) VALUES (%s,%s)", (room_id, body.nickname)).lastrowid
        except pymysql.IntegrityError as error:
            if error.args[0] != 1062:
                raise
            raise HTTPException(409, "このルームではその名前が使われています。別の名前を入力してください") from None
        set_session(con, room_id, member_id, response)
        return {"id": str(member_id), "name": body.nickname}


@router.post("/api/rooms/{room_id}/migrate-session")
def migrate_session(room_id: RoomId, request: Request, response: Response):
    """旧Cookieの持ち主だけに、移行済みルームの新Cookieを発行する。"""
    token = request.cookies.get(local_rooms.cookie_name(room_id))
    if not token:
        raise HTTPException(401, "このブラウザーの旧参加情報がありません")
    with connection() as con:
        if session_member(con, room_id, request):
            return {"room_path": None}
        member = con.execute('''SELECT s.room_id,s.member_id FROM consultation_member_sessions s
            JOIN consultation_members m ON m.id=s.member_id AND m.consultation_id=s.room_id
            WHERE s.token_hash=%s AND s.legacy_room_id=%s AND s.expires_at>UNIX_TIMESTAMP()''',
            (hashlib.sha256(token.encode()).hexdigest(), room_id)).fetchone()
        if member is None:
            raise HTTPException(401, "引き継げる旧参加情報がありません")
        room_row(con, member["room_id"])
        set_session(con, member["room_id"], member["member_id"], response)
        return {"room_path": f'/rooms/{member["room_id"]}/select'}
