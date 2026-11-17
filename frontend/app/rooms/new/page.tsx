// ルーム名・予算・人数・受け取り期限・幹事名を入力し、新しいルームを作成する画面です。
"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createRoom, displayDate, unavailableDate, type RoomInput } from "@/lib/rooms";
import DateCalendar from "../DateCalendar";
import RoomShell from "../RoomShell";

export default function NewRoomPage() {
  const router = useRouter();

  // ① 入力した値と、画面に表示する状態を覚える。
  const [title, setTitle] = useState("");
  const [nickname, setNickname] = useState("");
  const [budget, setBudget] = useState("");
  const [members, setMembers] = useState("");
  const [deadline, setDeadline] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  // すばやく連続で押しても送信は1回。画面更新を待たずに確認するためuseRefを使う。
  const submitting = useRef(false);

  // ② 入力中の内容を、プレビューで表示する文字と金額にする。
  const budgetValue = Number(budget);
  const memberValue = Number(members);
  let previewPrice = "—";
  let previewBudget = "未入力";
  let previewMembers = "未入力";
  let previewDeadline = "日付を選んでください";
  let previewTitle = "みんなのギフトルーム";

  if (budgetValue > 0 && memberValue > 0) {
    const perPerson = Math.ceil(budgetValue / memberValue);
    previewPrice = `¥${perPerson.toLocaleString("ja-JP")}`;
  }
  if (budgetValue > 0) {
    previewBudget = `¥${budgetValue.toLocaleString("ja-JP")}`;
  }
  if (members !== "") {
    previewMembers = `${members}人`;
  }
  if (deadline !== "") {
    previewDeadline = displayDate(deadline);
  }
  if (title.trim() !== "") {
    previewTitle = title.trim();
  }

  // ③ カレンダーから受け取った日付を覚え、前のエラー表示を消す。
  function changeDeadline(day: string) {
    setDeadline(day);
    setError("");
  }

  // ④ 作成ボタンが押されたときに、上から順に実行する。
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    // フォーム標準の再読み込みを止め、連続送信も防ぐ。
    event.preventDefault();
    if (submitting.current) {
      return;
    }
    setError("");

    // 受け取り期限と名前を確認する。問題があればここで終了する。
    const deadlineError = unavailableDate(deadline);
    if (deadlineError !== null) {
      setError(deadlineError);
      return;
    }
    const roomTitle = title.trim();
    const organizerNickname = nickname.trim();
    if (roomTitle === "" || organizerNickname === "") {
      setError("ルーム名とニックネームを入力してください。");
      return;
    }

    // 送信する項目を一つずつ用意する。最終的な入力検証はAPIでも行う。
    const roomInput: RoomInput = {
      title: roomTitle,
      nickname: organizerNickname,
      budget_total: budgetValue,
      member_count: memberValue,
      deliver_by: deadline,
    };

    submitting.current = true;
    setSaving(true);
    try {
      // APIで作成が成功してから、作成したルームのURLへ移動する。
      const createdRoom = await createRoom(roomInput);
      router.push(createdRoom.room_path);
    } catch (error) {
      // 入力内容は残し、メッセージを表示して再送信できるようにする。
      let message = "ルームを作成できませんでした。";
      if (error instanceof Error) {
        message = error.message;
      }
      setError(message);
      submitting.current = false;
      setSaving(false);
    }
  }

  // ⑤ ここから下は画面の配置。入力欄の値はuseStateと結び付ける。
  return (
    <RoomShell>
      <div className="room-page-intro">
        <p className="room-eyebrow">みんなで贈る、はじめの一歩</p>
        <h1>ギフトルームをつくる</h1>
        <p>
          予算と受け取り期限をそろえて、
          <br className="room-mobile-break" />
          贈りもの選びを始めましょう。
        </p>
      </div>

      <div className="room-create-layout">
        <form className="room-panel room-create-form" onSubmit={submit} aria-busy={saving}>
          <div className="room-section-heading">
            <span>01</span>
            <h2>ルームの基本情報</h2>
          </div>
          <label className="room-field">
            ルーム名 <span className="room-required">必須</span>
            <input
              name="title"
              value={title}
              onChange={e => setTitle(e.target.value)}
              required
              maxLength={100}
              placeholder="例：同僚さんの送別ギフト"
              autoComplete="off"
            />
          </label>
          <label className="room-field">
            あなたのニックネーム <span className="room-required">必須</span>
            <input
              name="nickname"
              value={nickname}
              onChange={e => setNickname(e.target.value)}
              required
              maxLength={30}
              placeholder="例：たけるん"
              autoComplete="nickname"
            />
            <small>ルームを作った方が幹事になります。実名は入力しないでください。</small>
          </label>

          <div className="room-section-heading">
            <span>02</span>
            <h2>みんなで出し合う予算</h2>
          </div>
          <div className="room-fields-pair">
            <label className="room-field">
              総予算 <span className="room-required">必須</span>
              <span className="room-unit-input">
                <input
                  name="budget_total"
                  type="number"
                  min={1}
                  max={2147483647}
                  step={1}
                  required
                  value={budget}
                  onChange={e => setBudget(e.target.value)}
                  placeholder="例：4500"
                />
                <span>円</span>
              </span>
            </label>
            <label className="room-field">
              参加予定人数 <span className="room-required">必須</span>
              <span className="room-unit-input">
                <input
                  name="member_count"
                  type="number"
                  min={1}
                  max={2147483647}
                  step={1}
                  required
                  value={members}
                  onChange={e => setMembers(e.target.value)}
                  placeholder="例：3"
                />
                <span>人</span>
              </span>
            </label>
          </div>
          <p className="room-help">参加予定人数には、幹事のあなたも含めてください。</p>

          <div className="room-section-heading">
            <span>03</span>
            <h2>いつまでに受け取りますか？</h2>
          </div>
          <DateCalendar value={deadline} onChange={changeDeadline} />

          {error && <p className="room-error" role="alert">{error}</p>}
          <button className="room-button room-submit" type="submit" disabled={saving}>
            {saving ? "ルームを作成しています…" : "この内容でルームを作る"}
            <span aria-hidden="true">→</span>
          </button>
        </form>

        <aside className="room-create-summary" aria-label="設定内容のプレビュー">
          <div className="room-dark-panel">
            <p className="room-eyebrow">YOUR GIFT ROOM</p>
            <h2>{previewTitle}</h2>
            <p>ひとりで迷う時間を、<br />みんなで選ぶ時間に。</p>
            <dl className="room-summary-list">
              <div>
                <dt>一人あたりの負担額</dt>
                <dd className="room-summary-price">{previewPrice}</dd>
              </div>
              <div>
                <dt>総予算 / 参加予定人数</dt>
                <dd>{previewBudget} / {previewMembers}</dd>
              </div>
              <div>
                <dt>受け取り期限</dt>
                <dd>{previewDeadline}</dd>
              </div>
            </dl>
            <p className="room-dark-note">
              一人あたりの金額は、総予算を人数で割って1円単位で切り上げています。
            </p>
          </div>
          <div className="room-summary-tip">
            <span aria-hidden="true">✦</span>
            <div>
              <h3>まずは、条件をそろえるところから。</h3>
              <p>保存した予算と受け取り期限は、あとからルームで確認できます。</p>
            </div>
          </div>
        </aside>
      </div>
    </RoomShell>
  );
}
