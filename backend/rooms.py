"""ルーム作成・取得の依頼を受け、入力確認・DB保存・一人あたり負担額の計算を行うプログラムです。"""
import math
from datetime import date
from typing import Annotated

import pymysql
from fastapi import APIRouter, HTTPException, Path as ApiPath
from pydantic import BaseModel

from database import fetch_all, transaction
from room_contract import RoomCreate, validate_deadline

router = APIRouter(prefix="/api/rooms", tags=["相談ルーム"])


class Room(BaseModel):
    """APIから画面へ返すルーム情報の形。"""
    room_id: int
    title: str
    budget_total: int
    member_count: int
    deliver_by: date
    organizer_nickname: str
    price_per_person: int
    room_path: str


def to_room(row: dict) -> Room:
    # ① 保存内容を取り出し、一人あたりの負担額を計算する。
    budget = row["budget_total"]
    people = row["member_count"]
    price_per_person = math.ceil(budget / people)
    room_id = row["room_id"]

    # ② 画面へ返す項目を、一つずつ明示する。
    return Room(
        room_id=room_id,
        title=row["title"],
        budget_total=budget,
        member_count=people,
        deliver_by=row["deliver_by"],
        organizer_nickname=row["organizer_nickname"],
        price_per_person=price_per_person,
        room_path=f"/rooms/{room_id}",
    )


def storage_unavailable() -> HTTPException:
    # 接続先やDBエラー本文をブラウザへ出さない。
    return HTTPException(503, "ルームを保存・取得できません。DB接続とルーム用テーブルの準備を確認してください")


@router.post("", response_model=Room, status_code=201)
def create_room(body: RoomCreate):
    # 入力チェックはRoomCreateが行う。ここへ来た時点で条件を満たしている。
    try:
        # ① 同じ接続で3つのSQLを実行し、全部成功したときだけ保存する。
        with transaction() as cur:
            # ② ルームを追加し、発行された番号を覚える。
            cur.execute(
                """INSERT INTO consultations
                   (title, budget_total, member_count, deliver_by)
                   VALUES (%s, %s, %s, %s)""",
                (body.title, body.budget_total, body.member_count, body.deliver_by),
            )
            room_id = cur.lastrowid

            # ③ 幹事をメンバーとして追加する。
            cur.execute(
                "INSERT INTO consultation_members (consultation_id, nickname) VALUES (%s, %s)",
                (room_id, body.nickname),
            )
            organizer_id = cur.lastrowid

            # ④ ルームに、幹事のメンバー番号を記録する。
            cur.execute(
                "UPDATE consultations SET organizer_id = %s WHERE id = %s",
                (organizer_id, room_id),
            )
    except (pymysql.MySQLError, EnvironmentError):
        raise storage_unavailable() from None

    # ⑤ 保存できた内容を、画面へ返す形に整える。
    saved_room = {
        "room_id": room_id,
        "title": body.title,
        "budget_total": body.budget_total,
        "member_count": body.member_count,
        "deliver_by": body.deliver_by,
        "organizer_nickname": body.nickname,
    }
    return to_room(saved_room)


@router.get("/{room_id}", response_model=Room)
def get_room(room_id: Annotated[int, ApiPath(ge=1, le=2147483647)]):
    # ① URLの番号を使い、ルームと幹事の情報をまとめて取得する。
    try:
        rows = fetch_all(
            """SELECT c.id AS room_id, c.title, c.budget_total, c.member_count, c.deliver_by,
                      m.nickname AS organizer_nickname
               FROM consultations c
               JOIN consultation_members m ON m.id = c.organizer_id AND m.consultation_id = c.id
               WHERE c.id = %s""",
            (room_id,),
        )
    except (pymysql.MySQLError, EnvironmentError):
        raise storage_unavailable() from None
    # ② 該当するルームがなければ、見つからないことを伝える。
    if len(rows) == 0:
        raise HTTPException(404, "ルームが見つかりません。URLを確認してください")

    # ③ 取得した1件を、画面へ返す形に整える。
    saved_room = rows[0]
    return to_room(saved_room)
