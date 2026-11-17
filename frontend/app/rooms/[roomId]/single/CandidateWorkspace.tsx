"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ResultCard from "../../../ResultCard";
import { searchGifts, type Gift } from "@/lib/api";
import { loadCandidateDraft, saveCandidateDraft, type CandidateDraft, type CandidateSlot } from "@/lib/singleApi";
import { useFarewellFavorites } from "@/lib/useFarewellFavorites";
import styles from "./candidate.module.css";

export default function CandidateWorkspace({ roomId, initialMemberId, localParticipation = false }: { roomId: string; initialMemberId: string; localParticipation?: boolean }) {
  const [memberId, setMemberId] = useState(initialMemberId);
  const [draft, setDraft] = useState<CandidateDraft | null>(null);
  const [slots, setSlots] = useState<CandidateSlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [reload, setReload] = useState(0);
  const [method, setMethod] = useState<"product" | "hint" | "favorites">("product");
  const favorites = useFarewellFavorites();
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState("");
  const [results, setResults] = useState<Gift[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [hint, setHint] = useState("");
  const [loadError, setLoadError] = useState("");
  const [searchError, setSearchError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [notice, setNotice] = useState("");
  const busy = loading || saving || searching;
  const invalidHint = slots.some(slot => slot.kind === "hint" && !slot.text.trim());

  useEffect(() => {
    let active = true;
    loadCandidateDraft(roomId, memberId, localParticipation).then(value => {
      if (!active) return;
      setDraft(value); setSlots(value.slots); setDirty(false); setLoading(false);
    }).catch(error => {
      if (!active) return;
      setLoadError(`入力を読み込めません：${error.message}`); setLoading(false);
    });
    // 参加者切替前に開始した通信で、別の人の画面を上書きしない。
    return () => { active = false; };
  }, [roomId, memberId, reload, localParticipation]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function changeSlots(next: CandidateSlot[]) {
    setSlots(next); setDirty(true); setNotice("");
  }

  function selectMember(id: string) {
    if (dirty && !window.confirm("まだ保存されていません。編集内容を破棄して参加者を切り替えますか？")) return;
    setDraft(null); setSlots([]); setDirty(false); setLoading(true); setLoadError("");
    setSaveError(""); setNotice(""); setHint(""); setMemberId(id);
    const url = new URL(window.location.href);
    url.searchParams.set("member", id);
    window.history.replaceState(null, "", url);
  }

  function reread() {
    if (dirty && !window.confirm("編集内容を破棄して、保存済みの内容を読み直しますか？")) return;
    setLoading(true); setLoadError(""); setSaveError(""); setNotice("");
    setReload(value => value + 1);
  }

  async function onSearch(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    setSearching(true); setSearchError("");
    try { setResults(await searchGifts({ keyword, category, indivWrap: false, priceBand: "" })); }
    catch (error) { setResults(null); setSearchError(`APIにつながりません：${(error as Error).message}`); }
    finally { setSearching(false); }
  }

  function addGift(gift: Gift) {
    if (busy || slots.length >= 3 || slots.some(slot => slot.kind === "product" && slot.productId === gift.id)) return;
    changeSlots([...slots, { kind: "product", productId: gift.id, reason: "", gift }]);
    setNotice(`「${gift.name}」を候補に追加しました。最後に保存してください。`);
  }

  function addHint(event: React.FormEvent) {
    event.preventDefault();
    if (busy || !hint.trim() || slots.length >= 3) return;
    changeSlots([...slots, { kind: "hint", text: hint.trim() }]); setHint("");
    setNotice("手掛かりを追加しました。最後に保存してください。");
  }

  async function save() {
    if (!draft || busy || invalidHint || !dirty) return;
    setSaving(true); setSaveError(""); setNotice("");
    try {
      const value = await saveCandidateDraft(roomId, memberId, draft.version, slots, localParticipation);
      setDraft(value); setSlots(value.slots); setDirty(false);
      setNotice("あなたの入力を保存しました。正式な提出はまだ行っていません。");
    } catch (error) {
      // 保存失敗・競合のときに、編集中の枠や手掛かりを消さない。
      setSaveError(`APIにつながりません：${(error as Error).message}`);
    } finally { setSaving(false); }
  }

  return <div className={styles.workspace}>
    <div className={styles.demo}>{localParticipation ? "ローカル検証用：名前で参加した本人の入力です。商品は架空で、このPC内だけに保存します。" : draft?.catalogSource === "shared"
      ? "共通DBの商品を読み取っています。ルーム・参加者は検証用、候補はこのPCに保存します。"
      : draft?.catalogSource === "demo"
        ? "ローカル検証用：架空の商品・参加者を使っています。今回は入力の保存までを確認します。"
        : "ローカル検証用：商品情報の取得元を確認しています。"}</div>
    <header className={styles.header}>
      <div className={styles.brand}>Giftia <span>みんなで選ぶ、贈りもの。</span></div>
      <Link href="/" onClick={event => { if (dirty && !window.confirm("保存していない編集内容があります。検索画面へ移動しますか？")) event.preventDefault(); }}>既存の検索画面へ</Link>
    </header>
    <main className={styles.main}>
      <div className={styles.roomBar}>
        <span>{draft?.room.title ?? "送別ギフトの候補入力"}</span>
        {localParticipation ? <p>参加者：{draft?.member.name ?? "確認中…"} <Link href={`/rooms/${encodeURIComponent(roomId)}`} onClick={event => { if (dirty && !window.confirm("保存していない編集内容があります。ルームへ戻りますか？")) event.preventDefault(); }}>ルームに戻る</Link></p> : <label>確認する架空参加者
          <select aria-label="確認する架空参加者" disabled={busy || !draft} value={memberId} onChange={event => selectMember(event.target.value)}>
            {(draft?.demoMembers ?? [{ id: memberId, name: memberId }]).map(member => <option key={member.id} value={member.id}>{member.name}</option>)}
          </select>
        </label>}
      </div>
      <section className={styles.intro}>
        <p className={styles.eyebrow}>1つに決める · 候補を持ち寄る</p>
        <h1>どんなギフトが喜ばれそう？</h1>
        <p>自分で商品を選んでも、「こんなのが好きそう」とヒントを残しても。<br />あなたのアイデアを、最大3つまでストックできます。</p>
      </section>
      {loading && <p role="status" className={styles.status}>あなたの入力を読み込んでいます…</p>}
      {loadError && <div role="alert" className={styles.error}>{loadError}<button onClick={reread} disabled={busy}>再試行</button>{localParticipation && <Link href={`/rooms/${encodeURIComponent(roomId)}`}>ルームで参加情報を確認する</Link>}</div>}
      {draft && !loading && !loadError && <>
        <div className={styles.budget}>みんなの予算 <strong>{draft.room.budgetTotal.toLocaleString()}円</strong><span>候補を考えるときの目安です。</span></div>
        <div className={styles.columns}>
          <section aria-label="候補を追加する" className={styles.chooser}>
            <div role="group" aria-label="候補の入力方法" className={styles.tabs}>
              <button aria-pressed={method === "product"} onClick={() => setMethod("product")} disabled={busy}>商品から選ぶ</button>
              <button aria-pressed={method === "favorites"} onClick={() => setMethod("favorites")} disabled={busy}>お気に入りから選ぶ</button>
              <button aria-pressed={method === "hint"} onClick={() => setMethod("hint")} disabled={busy}>好みをヒントにする</button>
            </div>
            {method === "product" ? <>
              <form onSubmit={onSearch} className={styles.search}>
                <label>キーワード<input value={keyword} onChange={event => setKeyword(event.target.value)} placeholder="例：コーヒー、タオル" disabled={busy} /></label>
                <label>カテゴリー<select value={category} onChange={event => setCategory(event.target.value)} disabled={busy}>
                  <option value="">すべて</option><option value="食品">食品</option><option value="生活雑貨">生活雑貨</option><option value="コスメ">コスメ</option>
                </select></label>
                <button type="submit" disabled={busy}>{searching ? "検索中…" : "検索"}</button>
              </form>
              {searchError && <p role="alert" className={styles.error}>{searchError}</p>}
              {searching && <p role="status">商品を検索しています…</p>}
              {!searching && results === null && !searchError && <div className={styles.empty}>相手のことを思い浮かべながら探してみましょう。<br />キーワードを空にして検索すると、全商品を表示します。</div>}
              {results && !searching && <>
                <p className={styles.muted}>{results.length ? `検索結果 ${results.length}件` : "条件に合う商品がありません。言葉やカテゴリーを変えてみてください。"}</p>
                <div className={styles.results}>{results.map((gift, index) => {
                  const selected = slots.some(slot => slot.kind === "product" && slot.productId === gift.id);
                  return <article key={gift.id} className={`${styles.result} ${selected ? styles.selected : ""}`}>
                    <ResultCard gift={gift} rank={index + 1} />
                    <button disabled={busy || selected || slots.length >= 3} onClick={() => addGift(gift)} aria-label={`${gift.name}を候補に追加`}>{selected ? "追加済み" : "＋ 候補に追加"}</button>
                  </article>;
                })}</div>
              </>}
            </> : method === "favorites" ? <>
              <h2 className={styles.favoritesTitle}>送別用のお気に入りから</h2>
              <p className={styles.muted}>気になっていた商品を、今回のルームの候補に選べます。選んだ後もお気に入りには残ります。</p>
              <p className={styles.muted}>このブラウザーのお気に入りです。架空参加者の切替とは連動しません。価格などは保存時の情報です。</p>
              {favorites.error && <p role="alert" className={styles.error}>{favorites.error}</p>}
              {!favorites.error && favorites.gifts.length === 0 && <div className={styles.empty}>まだお気に入りはありません。<br />普段の検索で「送別用のお気に入りに保存」を押してください。</div>}
              <div className={styles.results}>{favorites.gifts.map((gift, index) => {
                const selected = slots.some(slot => slot.kind === "product" && slot.productId === gift.id);
                return <article key={gift.id} className={`${styles.result} ${selected ? styles.selected : ""}`}>
                  <ResultCard gift={gift} rank={index + 1} />
                  <button disabled={busy || selected || slots.length >= 3} onClick={() => addGift(gift)} aria-label={`${gift.name}をお気に入りからルームの候補に追加`}>{selected ? "ルームに追加済み" : "＋ ルームの候補に追加"}</button>
                </article>;
              })}</div>
              <p className={styles.muted}>追加後は、右の「入力内容を保存する」でルームの下書きを保存してください。</p>
            </> : <form className={styles.hintForm} onSubmit={addHint}>
              <span className={styles.hintIcon} aria-hidden="true">✧</span>
              <h2>商品が決まらなくても、大丈夫。</h2>
              <p>相手の好みや、贈りたい気持ちをヒントにして残せます。<br />例：「コーヒーが好きそう」「休日にゆっくりしてほしい」</p>
              <label>こんなのが好きそう<textarea maxLength={100} rows={4} value={hint} onChange={event => setHint(event.target.value)} disabled={busy || slots.length >= 3} placeholder="相手を思い浮かべて、ひとこと。" /></label>
              <div className={styles.hintFooter}><span>{hint.length}/100文字</span><button type="submit" disabled={busy || !hint.trim() || slots.length >= 3}>＋ ヒントを候補に追加</button></div>
              <p className={styles.muted}>今回はヒントの保存までです。商品への補填は後日行います。</p>
            </form>}
          </section>
          <aside className={styles.stock} aria-label="あなたの候補ストック">
            <div className={styles.stockHeading}><h2>あなたの候補ストック</h2><strong>{slots.length}<small> / 3</small></strong></div>
            <p>ほかの人には、まだ見えません。</p>
            {slots.length === 0 && <div className={styles.stockEmpty}>商品やヒントを追加すると、<br />ここに並びます。</div>}
            <ol className={styles.slots}>{slots.map((slot, index) => <li key={slot.kind === "product" ? slot.productId : `hint-${index}`}>
              <div className={styles.slotTop}><span>{String(index + 1).padStart(2, "0")} · {slot.kind === "product" ? "商品" : "ヒント"}</span><button aria-label={`候補${index + 1}を削除`} disabled={busy} onClick={() => changeSlots(slots.filter((_, i) => i !== index))}>削除</button></div>
              {slot.kind === "product" ? <>
                <h3>{slot.gift.name}</h3><p className={styles.slotPrice}>{slot.gift.price.toLocaleString()}円</p>
                {slot.available === false && <p role="alert">現在の商品一覧では購入可能と確認できません。保存済み候補は残しています。削除または入れ替えてください。</p>}
                <label>選んだ理由（任意）<textarea aria-label={`候補${index + 1}の理由`} maxLength={100} rows={2} value={slot.reason} disabled={busy} onChange={event => changeSlots(slots.map((s, i) => i === index ? { ...slot, reason: event.target.value } : s))} placeholder="こんなところがよさそう" /></label>
              </> : <label>こんなのが好きそう<textarea aria-label={`候補${index + 1}のヒント`} maxLength={100} rows={3} value={slot.text} disabled={busy} onChange={event => changeSlots(slots.map((s, i) => i === index ? { ...slot, text: event.target.value } : s))} /></label>}
            </li>)}</ol>
            {slots.length >= 3 && <p className={styles.full}>3枠そろいました。入れ替えるときは、候補を削除して追加してください。</p>}
            {invalidHint && <p role="alert">空欄のヒントを入力するか、枠を削除してください。</p>}
            <button className={styles.save} onClick={save} disabled={busy || !dirty || invalidHint}>{saving ? "保存しています…" : "入力内容を保存する"}</button>
            <p className={styles.saveState}>{dirty ? "未保存の変更があります" : "保存済みの内容を表示しています"}</p>
            <button className={styles.reread} disabled={busy} onClick={reread}>保存済みの内容を読み直す</button>
          </aside>
        </div>
      </>}
      {saveError && <p className={styles.error} role="alert">{saveError}。編集内容はこの画面に残っています。</p>}
      <p role="status" className={styles.notice}>{notice}</p>
    </main>
  </div>;
}
