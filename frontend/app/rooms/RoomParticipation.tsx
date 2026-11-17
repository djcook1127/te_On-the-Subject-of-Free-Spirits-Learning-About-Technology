"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { getLocalMember, joinLocalRoom, type LocalMember } from "@/lib/localParticipation";

export default function RoomParticipation({ roomId }: { roomId: string }) {
  const [member, setMember] = useState<LocalMember | null>(null);
  const [nickname, setNickname] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const submitting = useRef(false);

  useEffect(() => {
    let active = true;
    getLocalMember(roomId).then(value => {
      if (active) { setMember(value); setLoading(false); }
    }).catch(err => {
      if (active) { setError(err.message); setLoading(false); }
    });
    return () => { active = false; };
  }, [roomId, reload]);

  async function join(event: React.FormEvent) {
    event.preventDefault();
    if (submitting.current || !nickname.trim()) return;
    submitting.current = true;
    setSaving(true); setError("");
    try { setMember(await joinLocalRoom(roomId, nickname.trim())); }
    catch (err) { setError((err as Error).message); }
    finally { submitting.current = false; setSaving(false); }
  }

  return <section className="room-panel room-participation" aria-label="ルームへの参加">
    <p className="room-eyebrow">ローカル検証 · 架空の商品</p>
    <h2>{member ? `${member.name}さんの候補を考える` : "名前を入力して参加する"}</h2>
    <p>このPC内の検証用ルームです。自分の商品候補や「こんなのが好きそう」という手掛かりを、最大3枠まで保存できます。</p>
    {loading ? <p role="status">参加情報を確認しています…</p> : member ? <>
      <p>このブラウザーでは、{member.name}さんとして参加しています。</p>
      <Link href={`/rooms/${encodeURIComponent(roomId)}/single`} className="room-button">自分の候補・手掛かりを入力する →</Link>
      <p className="room-help">入力は本人だけに表示されます。保存は正式な提出ではありません。</p>
    </> : <form onSubmit={join}>
      <label htmlFor="participant-name">参加する名前</label>
      <input id="participant-name" name="nickname" autoComplete="off" required maxLength={30}
        value={nickname} onChange={event => setNickname(event.target.value)} disabled={saving || !!error && !nickname} />
      <button type="submit" className="room-button" disabled={saving || !nickname.trim()}>{saving ? "参加しています…" : "この名前で参加する"}</button>
      <p className="room-help">同じルームで使われている名前は登録できません。同じブラウザーで再訪すると参加情報が残ります。Cookieを消した場合や別端末からの復元には対応していません。</p>
    </form>}
    {error && <div role="alert"><p className="room-error">{error}</p><button type="button" disabled={saving} onClick={() => { setError(""); setLoading(true); setReload(value => value + 1); }}>参加情報を読み直す</button></div>}
  </section>;
}
