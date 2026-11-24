"""共有するルーム入力規則。接続設定は読まない。"""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, field_validator

JST = timezone(timedelta(hours=9))

# ① 画面と共通の祝日ファイルを読み込む。
module_folder = Path(__file__).resolve().parent
calendar_file = module_folder / "shared/japan-holidays.json"
if not calendar_file.is_file():
    calendar_file = module_folder.parent / "shared/japan-holidays.json"
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


class RoomSettings(BaseModel):
    """画面から受け取る入力と、その入力が守る条件。"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=100)
    budget_total: int = Field(strict=True, ge=1, le=2147483647)
    member_count: int = Field(strict=True, ge=1, le=2147483647)
    deliver_by: date

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


class RoomCreate(RoomSettings):
    nickname: str = Field(min_length=1, max_length=30)
