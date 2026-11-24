"""既存MySQLルーム・参加者を使う。実行時にDDLを流さない。"""
import hashlib
import os
import secrets
from contextlib import contextmanager

import pymysql
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import Field

import local_rooms
from room_contract import RoomCreate
from selection_store import MySQLStore

STORAGE_SOURCE = "shared"
RoomId = local_rooms.RoomId
ORIGINS = [*local_rooms.ORIGINS, *(origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip() and origin.strip() != "*")]
router = APIRouter()
INVITE_LIFETIME = 7 * 24 * 60 * 60


class InviteJoin(local_rooms.JoinInput):
    invite_token: str | None = Field(default=None, min_length=43, max_length=43)


async def local_origin_only(request: Request, call_next):
    if request.method in {"POST", "PUT", "DELETE"} and request.headers.get("origin") not in (None, *ORIGINS):
        return JSONResponse(status_code=403, content={"detail": "この画面からは操作できません"})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


def _connect():
    from connection_pool import pool
    return pool.acquire()


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
                        samesite="strict", secure=os.getenv("GIFTIA_SECURE_COOKIES") == "1",
                        path=f"/api/rooms/{room_id}")


def session_member(con, room_id, request):
    token = request.cookies.get(cookie_name(room_id))
    if not token:
        return None
    return con.execute('''SELECT m.id,m.nickname FROM consultation_member_sessions s
        JOIN consultation_members m ON m.id=s.member_id AND m.consultation_id=s.room_id
        WHERE s.token_hash=%s AND s.room_id=%s AND s.expires_at>UNIX_TIMESTAMP()''',
        (hashlib.sha256(token.encode()).hexdigest(), room_id)).fetchone()


def room_row(con, room_id, lock=True):
    # 更新は親行を先にロック。参照だけの画面取得は書込を待たせない。
    room = con.execute('''SELECT c.*,m.nickname AS organizer_nickname FROM consultations c
        JOIN consultation_members m ON m.id=c.organizer_id AND m.consultation_id=c.id
        WHERE c.id=%s''' + (' LOCK IN SHARE MODE' if lock == "shared" else ' FOR UPDATE' if lock else ''), (room_id,)).fetchone()
    if room is None:
        raise HTTPException(404, "ルームが見つかりません")
    return room


def own_member(con, room_id, request, lock=True):
    token = request.cookies.get(cookie_name(room_id))
    if not token:
        raise HTTPException(401, "ルームに名前で参加してから入力してください")
    if not lock:
        row = con.execute('''SELECT c.*,creator.nickname AS organizer_nickname,m.id AS session_member_id,m.nickname AS session_nickname
            FROM consultations c JOIN consultation_members creator ON creator.id=c.organizer_id AND creator.consultation_id=c.id
            JOIN consultation_member_sessions s ON s.room_id=c.id
            JOIN consultation_members m ON m.id=s.member_id AND m.consultation_id=c.id
            WHERE c.id=%s AND s.token_hash=%s AND s.expires_at>UNIX_TIMESTAMP()''',
            (room_id, hashlib.sha256(token.encode()).hexdigest())).fetchone()
        if row:
            return row, {"id": row["session_member_id"], "nickname": row["session_nickname"]}
    room = room_row(con, room_id, lock=lock)
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
def get_room(room_id: RoomId, request: Request):
    with connection() as con:
        room, member = own_member(con, room_id, request, lock=False)
        return {**room_payload(room), "is_organizer": member["id"] == room["organizer_id"]}


def require_organizer(con, room_id, request):
    room, member = own_member(con, room_id, request)
    if member["id"] != room["organizer_id"]:
        raise HTTPException(403, "主催者だけが招待リンクを管理できます")


@router.post("/api/rooms/{room_id}/invite")
def rotate_invite(room_id: RoomId, request: Request):
    with connection() as con:
        require_organizer(con, room_id, request)
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        con.execute(
            """INSERT INTO consultation_invites(room_id,token_hash,expires_at)
            VALUES (%s,%s,UNIX_TIMESTAMP()+%s)
            ON DUPLICATE KEY UPDATE token_hash=%s, expires_at=UNIX_TIMESTAMP()+%s""",
            (room_id, digest, INVITE_LIFETIME, digest, INVITE_LIFETIME),
        )
    return {"token": token, "expires_in": INVITE_LIFETIME}


@router.delete("/api/rooms/{room_id}/invite", status_code=204)
def revoke_invite(room_id: RoomId, request: Request):
    with connection() as con:
        require_organizer(con, room_id, request)
        con.execute("DELETE FROM consultation_invites WHERE room_id=%s", (room_id,))
    return Response(status_code=204)


def require_invite(con, room_id, token):
    if token and con.execute(
        "SELECT 1 FROM consultation_invites WHERE room_id=%s AND token_hash=%s AND expires_at>UNIX_TIMESTAMP()",
        (room_id, hashlib.sha256(token.encode()).hexdigest()),
    ).fetchone():
        return
    raise HTTPException(403, "有効な招待リンクが必要です。主催者に新しいリンクを依頼してください")


@router.get("/api/rooms/{room_id}/me")
def get_me(room_id: RoomId, request: Request):
    with connection() as con:
        _, member = own_member(con, room_id, request)
        return {"id": str(member["id"]), "name": member["nickname"]}


@router.post("/api/rooms/{room_id}/members", status_code=201)
def join_room(room_id: RoomId, body: InviteJoin, request: Request, response: Response):
    if body.invite_token is None and not request.cookies.get(cookie_name(room_id)):
        raise HTTPException(403, "有効な招待リンクが必要です。主催者に新しいリンクを依頼してください")
    with connection() as con:
        room_row(con, room_id)
        member = session_member(con, room_id, request)
        if member:
            if member["nickname"] != body.nickname:
                raise HTTPException(409, "このブラウザーではすでに別の名前で参加しています")
            response.status_code = 200
            return {"id": str(member["id"]), "name": member["nickname"]}
        require_invite(con, room_id, body.invite_token)
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
