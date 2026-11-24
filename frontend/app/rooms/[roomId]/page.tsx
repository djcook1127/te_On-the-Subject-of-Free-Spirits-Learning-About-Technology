// URLのルーム番号を使って保存済みの情報を取得し、予算・受け取り期限などを表示する画面です。
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { displayDate, getRoom, updateRoomInvite, type Room } from "@/lib/rooms";
import RoomShell from "../RoomShell";
import RoomParticipation from "../RoomParticipation";
import { restoreImportedRoom } from "@/lib/selection";

export default function RoomPage() {
  // ① URLの番号と、画面が現在覚えている情報を用意する。
  const { roomId } = useParams<{ roomId: string }>();
  const [room, setRoom] = useState<Room | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");
  const [invite, setInvite] = useState<{ roomId: string; url: string } | null>(null);
  const [inviteBusy, setInviteBusy] = useState(false);
  const inviteUrl = invite?.roomId === roomId ? invite.url : "";

  // ② 画面を表示したとき、またはURLの番号が変わったときに取得する。
  useEffect(() => {
    // 画面を離れた場合などに、不要な通信を中止するための準備。
    const controller = new AbortController();

    async function loadRoom() {
      try {
        if (process.env.NEXT_PUBLIC_SELECTION_ROOMS === "1" && new URLSearchParams(window.location.search).get("legacy") === "1") {
          const importedPath = await restoreImportedRoom(roomId);
          if (controller.signal.aborted) return;
          if (importedPath) { window.location.replace(importedPath); return; }
        }
        // getRoomは「取得」。取得が終わってから、setRoomで画面の状態を更新する。
        const roomData = await getRoom(roomId, controller.signal);
        setRoom(roomData);
      } catch (error) {
        // 画面を離れて中止した通信は、エラー表示の対象にしない。
        if (controller.signal.aborted) {
          return;
        }
        let message = "ルームを読み込めませんでした。";
        if (error instanceof Error) {
          message = error.message;
        }
        setError(message);
      }
    }

    loadRoom();

    // 次のルームへ移るときや、この画面を離れるときに実行する。
    return () => {
      controller.abort();
    };
  }, [roomId]);

  // ③ URLのコピーボタンが押されたときの処理。
  async function copyUrl() {
    try {
      await navigator.clipboard.writeText(inviteUrl || window.location.href);
      setCopied("URLをコピーしました");
    } catch {
      setCopied(inviteUrl ? "コピーできませんでした。表示されている招待リンクを選択してください。" : "コピーできませんでした。ブラウザーのアドレス欄からコピーしてください。");
    }
  }

  async function changeInvite(method: "POST" | "DELETE") {
    setInviteBusy(true);
    setCopied("");
    try {
      const token = await updateRoomInvite(roomId, method);
      const url = new URL(`/rooms/${encodeURIComponent(roomId)}/select`, window.location.origin);
      if (token) url.hash = new URLSearchParams({ invite: token }).toString();
      setInvite(token ? { roomId, url: url.href } : null);
      setCopied(token ? "7日間有効なリンクを発行しました。" : "招待リンクを無効にしました。");
    } catch (error) {
      setCopied(error instanceof Error ? error.message : "招待リンクを更新できませんでした。");
    } finally {
      setInviteBusy(false);
    }
  }

  // ④ 失敗・読み込み中・成功を順に判定し、それぞれの画面を表示する。
  // 取得後の情報がある場合だけ、ヘッダーにルーム名を出す。
  let headerTitle: string | undefined = undefined;
  if (room !== null) {
    headerTitle = room.title;
  }

  if (error !== "") {
    return (
      <RoomShell title={headerTitle}>
        <section className="room-panel room-status">
          <h1>ルームを表示できません</h1>
          <p className="room-error" role="alert">{error}</p>
          <Link href="/rooms/new" className="room-button">ルーム作成に戻る</Link>
        </section>
      </RoomShell>
    );
  }

  if (room === null) {
    return (
      <RoomShell>
        <p className="room-status" role="status">ルームを読み込んでいます…</p>
      </RoomShell>
    );
  }

  // ここまで来たら、roomに取得した情報が入っている。
  const deadlineText = displayDate(room.deliver_by);
  const priceText = room.price_per_person.toLocaleString("ja-JP");
  const budgetText = room.budget_total.toLocaleString("ja-JP");

  return (
    <RoomShell title={room.title}>
      <div className="room-page-intro">
        <p className="room-eyebrow">ギフトルーム</p>
        <h1>{room.title}</h1>
        <p>幹事：{room.organizer_nickname}さん</p>
      </div>

      <div className="room-stat-grid">
        <section className="room-panel room-stat">
          <h2>受け取り期限</h2>
          <p>{deadlineText}</p>
          <small>この日までに受け取る予定</small>
        </section>
        <section className="room-panel room-stat">
          <h2>一人あたりの負担額</h2>
          <p>¥{priceText}</p>
          <small>総予算 ¥{budgetText} / {room.member_count}人で分担</small>
        </section>
        <section className="room-panel room-stat">
          <h2>参加予定人数</h2>
          <p>{room.member_count}人</p>
          <small>幹事を含む予定人数です</small>
        </section>
      </div>

      <section className="room-panel room-saved">
        <span className="room-saved-mark" aria-hidden="true">✓</span>
        <div>
          <h2>ルームの準備ができました</h2>
          <p>予算と受け取り期限を保存しました。このURLから、いつでも確認できます。</p>
        </div>
      </section>

      {(room.local_preview || room.selection_enabled) && (process.env.NEXT_PUBLIC_SELECTION_ROOMS === "1" ?
        <section className="room-panel room-saved"><div><h2>みんなで候補を持ち寄ろう</h2><p>開設者が最初の候補を提出し、その後に参加者も追加できます。ルーム全体で最大10品を集め、主催者の投票開始後に★評価します。</p><Link href={`/rooms/${encodeURIComponent(roomId)}/select`} className="room-button">提案・比較・決定へ →</Link><p>主催者は共同決定画面の「ルーム情報を編集」から、投票開始前に設定を修正できます。</p></div></section>
        : <RoomParticipation key={roomId} roomId={roomId} />)}

      <div className="room-bottom-grid">
        {(room.storage_source !== "shared" || room.is_organizer) && <section className="room-panel room-url-panel">
          <p className="room-eyebrow">ROOM URL</p>
          <h2>{room.storage_source === "shared" ? "参加者への招待リンク" : "ルームのURLを控える"}</h2>
          {room.storage_source === "shared" ? <>
            <p>発行から7日間使えます。再発行すると以前のリンクは無効になります。</p>
            <button type="button" className="room-button room-button-small" disabled={inviteBusy} onClick={() => void changeInvite("POST")}>発行・再発行</button>{" "}
            <button type="button" className="room-button room-button-small" disabled={inviteBusy} onClick={() => void changeInvite("DELETE")}>無効にする</button>
            {inviteUrl && <div className="room-url-row">
              <input aria-label="招待リンク" value={inviteUrl} readOnly />
              <button type="button" className="room-button room-button-small" disabled={inviteBusy} onClick={copyUrl}>リンクをコピー</button>
            </div>}
          </> : <>
          <p>再び開くときは、このページのURLを使ってください。</p>
          <div className="room-url-row">
            <code>{room.room_path}</code>
            <button type="button" className="room-button room-button-small" onClick={copyUrl}>
              URLをコピー
            </button>
          </div>
          </>}
          <p className="room-help" role="status">{copied}</p>
        </section>}
        <section className="room-dark-panel room-next">
          <p className="room-eyebrow">GIFT SELECTION</p>
          <h2>どんな贈りものに<br />しよう？</h2>
          <p>まずはギフトを探してみましょう。</p>
          <Link href="/" className="room-button">
            ギフトを探す<span aria-hidden="true">→</span>
          </Link>
        </section>
      </div>
    </RoomShell>
  );
}
