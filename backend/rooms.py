"""ルーム作成・取得の依頼を受け、入力確認・DB保存・一人あたり負担額の計算を行うプログラムです。"""
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import pymysql
from fastapi import APIRouter, HTTPException, Path as ApiPath
from pydantic import BaseModel, ConfigDict, Field, field_validator

from database import fetch_all, transaction

router = APIRouter(prefix="/api/rooms", tags=["相談ルーム"])
JST = timezone(timedelta(hours=9))

# ① 画面と共通の祝日ファイルを読み込む。
project_folder = Path(__file__).resolve().parent.parent
calendar_file = project_folder / "shared/japan-holidays.json"
calendar_text = calendar_file.read_text(encoding="utf-8")
CALENDAR = json.loads(calendar_text)


def today_in_japan() -> date:
    """パソコンの設定にかかわらず、日本時間の今日を返す。"""
    return datetime.now(JST).date()


def validate_deadline(value: date, today: date | None = None) -> date:
    """使える年・今日以降・土日祝日以外の順に確認する。"""
    if today is None:
        today = today_in_japan()

    if value.year not in CALENDAR["supported_years"]:
        raise ValueError("祝日データのある2026年・2027年の日付を選んでください")

    if value < today:
        raise ValueError("受け取り期限は今日以降を選んでください")

    # Pythonでは月曜日が0、土曜日が5、日曜日が6。
    is_weekend = value.weekday() >= 5
    is_holiday = value.isoformat() in CALENDAR["holidays"]
    if is_weekend or is_holiday:
        raise ValueError("受け取り期限に土日祝日は指定できません。平日を選んでください")

    return value


class RoomCreate(BaseModel):
    """画面から受け取る入力と、その入力が守る条件。"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=100)
    budget_total: int = Field(strict=True, ge=1, le=2147483647)
    member_count: int = Field(strict=True, ge=1, le=2147483647)
    deliver_by: date
    nickname: str = Field(min_length=1, max_length=30)

    @field_validator("deliver_by", mode="before")
    @classmethod
    def only_calendar_date(cls, value):
        # Unix時刻・日時の自動変換を避け、日付だけを受け取る。
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            raise ValueError("受け取り期限はYYYY-MM-DD形式で指定してください")
        if len(value) != 10:
            raise ValueError("受け取り期限はYYYY-MM-DD形式で指定してください")

        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise ValueError("受け取り期限はYYYY-MM-DD形式で指定してください") from None
        if parsed.isoformat() != value:
            raise ValueError("受け取り期限はYYYY-MM-DD形式で指定してください")
        return parsed

    @field_validator("deliver_by")
    @classmethod
    def business_day(cls, value: date) -> date:
        return validate_deadline(value)


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
