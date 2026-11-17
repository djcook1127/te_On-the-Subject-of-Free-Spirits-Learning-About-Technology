// 受け取り期限を選ぶカレンダーを表示し、過去日・土日祝日を選べなくする部品です。
"use client";

import { useState } from "react";
import { calendarSource, displayDate, japanToday, supportedYears, unavailableDate } from "@/lib/rooms";

type DateCalendarProps = {
  value: string;
  onChange: (day: string) => void;
};

export default function DateCalendar({ value, onChange }: DateCalendarProps) {
  // ① 選択済みの日付があればその月を、なければ今日の月を最初に表示する。
  const today = japanToday();
  let initialDate = today;
  if (value !== "") {
    initialDate = value;
  }
  const [month, setMonth] = useState(initialDate.slice(0, 7));

  // ② 表示する年・月・月初の曜日・その月の日数を計算する。
  const monthParts = month.split("-");
  const year = Number(monthParts[0]);
  const monthNumber = Number(monthParts[1]);
  // JavaScriptの月は0始まりなので、1月なら0を渡す。
  const firstDate = new Date(Date.UTC(year, monthNumber - 1, 1));
  const firstWeekday = firstDate.getUTCDay();
  // 次の月の「0日目」は、表示している月の最終日になる。
  const lastDate = new Date(Date.UTC(year, monthNumber, 0));
  const daysInMonth = lastDate.getUTCDate();

  // ③ 過去の月や、祝日データのない年へ進めないようにする。
  let minMonth = `${supportedYears[0]}-01`;
  const currentMonth = today.slice(0, 7);
  if (currentMonth > minMonth) {
    minMonth = currentMonth;
  }
  const lastSupportedYear = supportedYears[supportedYears.length - 1];
  const maxMonth = `${lastSupportedYear}-12`;

  function moveMonth(step: number) {
    const nextDate = new Date(Date.UTC(year, monthNumber - 1 + step, 1));
    const nextMonth = nextDate.toISOString().slice(0, 7);
    setMonth(nextMonth);
  }

  // ④ 月初の曜日までの空欄を作る。
  const blankCells = [];
  for (let index = 0; index < firstWeekday; index++) {
    blankCells.push(<span key={`blank-${index}`} />);
  }

  // ⑤ 日付ごとに、押せるか・色・読み上げ用の説明を決める。
  const dayButtons = [];
  for (let dayNumber = 1; dayNumber <= daysInMonth; dayNumber++) {
    const dayText = String(dayNumber).padStart(2, "0");
    const day = `${month}-${dayText}`;
    const reason = unavailableDate(day, today);
    const isUnavailable = reason !== null;
    const isSelected = day === value;

    let className = "";
    if (isSelected) {
      className = "room-day-selected";
    } else if (day === today) {
      className = "room-day-today";
    }

    let buttonLabel = displayDate(day);
    let buttonTitle = "受け取り期限に設定";
    if (reason !== null) {
      buttonLabel = `${buttonLabel}、選択不可：${reason}`;
      buttonTitle = reason;
    }

    dayButtons.push(
      <button
        key={day}
        type="button"
        disabled={isUnavailable}
        aria-pressed={isSelected}
        aria-label={buttonLabel}
        title={buttonTitle}
        className={className}
        onClick={() => onChange(day)}
      >
        {dayNumber}
      </button>
    );
  }

  let selectedDateText = "カレンダーから日付を選択";
  if (value !== "") {
    selectedDateText = displayDate(value);
  }

  // ⑥ 準備した日付ボタンを、7列のカレンダーに並べる。
  return (
    <fieldset className="room-calendar-field">
      <legend>受け取り期限 <span className="room-required">必須</span></legend>
      <p id="deadline-help" className="room-help">
        この日までに受け取りたい日を選んでください。土日祝日は選べません。
      </p>
      <div className="room-date-value" aria-live="polite">{selectedDateText}</div>
      <div className="room-calendar" aria-describedby="deadline-help">
        <div className="room-calendar-heading">
          <button
            type="button"
            onClick={() => moveMonth(-1)}
            disabled={month <= minMonth}
            aria-label="前の月"
          >
            ‹
          </button>
          <strong aria-live="polite">{year}年 {monthNumber}月</strong>
          <button
            type="button"
            onClick={() => moveMonth(1)}
            disabled={month >= maxMonth}
            aria-label="次の月"
          >
            ›
          </button>
        </div>
        <div className="room-calendar-grid">
          {["日", "月", "火", "水", "木", "金", "土"].map(weekday => (
            <span className="room-weekday" key={weekday} aria-hidden="true">{weekday}</span>
          ))}
          {blankCells}
          {dayButtons}
        </div>
        <p className="room-calendar-note">薄い文字の日付は選択できません。</p>
      </div>
      <p className="room-help">
        祝日データ：
        <a href={calendarSource} target="_blank" rel="noreferrer">内閣府</a>
        （2026・2027年）
      </p>
    </fieldset>
  );
}
