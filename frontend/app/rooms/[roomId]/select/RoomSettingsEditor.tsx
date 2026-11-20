"use client";

import { useState } from "react";
import { unavailableDate } from "@/lib/rooms";
import { selectionRequest, type Selection } from "@/lib/selection";
import DateCalendar from "../../DateCalendar";

export default function RoomSettingsEditor({ data, busy, onSave }: {
  data: Selection; busy: boolean;
  onSave: (action: () => Promise<Selection>) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(data.room.title);
  const [budget, setBudget] = useState(String(data.room.budgetTotal));
  const [members, setMembers] = useState(String(data.room.memberCount));
  const [deadline, setDeadline] = useState(data.room.deliverBy);
  const [error, setError] = useState("");
  if (!data.me.isOrganizer || data.phase !== "collecting") return null;

  return <section className="room-panel" id="settings">
    <h2>ルーム情報</h2><p>主催者は投票開始前に設定を修正できます。</p>
    {!editing ? <button disabled={busy} onClick={() => {
      setTitle(data.room.title); setBudget(String(data.room.budgetTotal));
      setMembers(String(data.room.memberCount)); setDeadline(data.room.deliverBy);
      setError(""); setEditing(true);
    }}>ルーム情報を編集</button> : <form onSubmit={event => {
      event.preventDefault();
      const dateError = unavailableDate(deadline);
      if (dateError) { setError(`受け取り期限：${dateError}`); return; }
      setError("");
      void onSave(async () => {
        const result = await selectionRequest<{ selection: Selection }>(data.room.id, "/room", "PUT", { title, budget_total: Number(budget), member_count: Number(members), deliver_by: deadline });
        setEditing(false);
        return result.selection;
      });
    }}>
      <label>ルーム名<input required maxLength={100} value={title} disabled={busy} onChange={e => setTitle(e.target.value)} /></label>
      <label>総予算（円）<input type="number" min={1} max={2147483647} step={1} required value={budget} disabled={busy} onChange={e => setBudget(e.target.value)} /></label>
      <label>参加予定人数<input type="number" min={1} max={2147483647} step={1} required value={members} disabled={busy} onChange={e => setMembers(e.target.value)} /></label>
      <DateCalendar value={deadline} onChange={setDeadline} />
      <p>候補・コメントは残ります。予算を下げた場合は候補の価格を確認してください。投票開始後は編集できません。</p>
      {error && <p className="room-error" role="alert">{error}</p>}
      <button className="room-button" disabled={busy}>ルーム情報を保存</button>
      <button type="button" disabled={busy} onClick={() => setEditing(false)}>キャンセル</button>
    </form>}
  </section>;
}
