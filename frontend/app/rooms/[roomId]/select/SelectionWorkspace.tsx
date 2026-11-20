"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { searchGifts, type Gift } from "@/lib/api";
import { joinLocalRoom } from "@/lib/localParticipation";
import { ParticipationRequired, restoreImportedRoom, selectionRequest, type ProposalProduct, type Selection } from "@/lib/selection";
import { useFarewellFavorites } from "@/lib/useFarewellFavorites";
import RoomShell from "../../RoomShell";
import styles from "./selection.module.css";

export default function SelectionWorkspace({ roomId }: { roomId: string }) {
  const [data, setData] = useState<Selection | null>(null);
  const [joining, setJoining] = useState(false);
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [products, setProducts] = useState<ProposalProduct[]>([]);
  const [version, setVersion] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [submitters, setSubmitters] = useState<number[]>([]);
  const [keyword, setKeyword] = useState("");
  const [results, setResults] = useState<Gift[]>([]);
  const [randoms, setRandoms] = useState<Gift[]>([]);
  const [method, setMethod] = useState<"search" | "favorites" | "random">("search");
  const [tab, setTab] = useState<"propose" | "compare" | "results">("propose");
  const [noteKind, setNoteKind] = useState("好み");
  const [note, setNote] = useState("");
  const [comments, setComments] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<"single" | "catalog">("single");
  const [picked, setPicked] = useState<string[]>([]);
  const [confirming, setConfirming] = useState(false);
  const favorites = useFarewellFavorites();

  async function reload(resetDraft = false) {
    const value = await selectionRequest<Selection>(roomId);
    setData(value); setJoining(false);
    setSubmitters(value.members.filter(m => m.canPropose).map(m => m.id));
    if (resetDraft) { setProducts(value.ownProducts); setVersion(value.me.version); setDirty(false); }
    return value;
  }

  useEffect(() => {
    let active = true;
    (async () => {
      const importedPath = new URLSearchParams(window.location.search).get("legacy") === "1" ? await restoreImportedRoom(roomId) : null;
      if (!active) return null;
      if (importedPath && importedPath !== window.location.pathname) {
        window.location.replace(importedPath); return null;
      }
      return selectionRequest<Selection>(roomId);
    })().then(value => {
      if (!value) return;
      if (!active) return;
      setData(value); setProducts(value.ownProducts); setVersion(value.me.version);
      setSubmitters(value.members.filter(m => m.canPropose).map(m => m.id));
      setTab(value.phase === "decided" ? "results" : value.phase === "voting" ? "compare" : "propose");
    }).catch(err => {
      if (!active) return;
      if (err instanceof ParticipationRequired) setJoining(true);
      else setError(err.message);
    });
    return () => { active = false; };
  }, [roomId]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  async function run(action: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(""); setNotice("");
    try { await action(); }
    catch (err) { setError(err instanceof Error ? err.message : "通信を確認してください"); }
    finally { lock.current = false; setBusy(false); }
  }

  function add(gift: Gift) {
    if (busy || products.length >= 3 || products.some(p => p.productId === gift.id)) return;
    setProducts([...products, { productId: gift.id, gift, reason: "" }]); setDirty(true);
  }

  async function save() {
    const result = await selectionRequest<{ version: number }>(roomId, "/proposal", "PUT", {
      version, products: products.map(p => ({ productId: p.productId, reason: p.reason })),
    });
    setVersion(result.version); setDirty(false);
  }

  async function shuffle() {
    await run(async () => {
      const exclude = products.map(p => p.productId).join(",");
      const response = await selectionRequest<{ results: Gift[] }>(roomId, `/random?exclude=${encodeURIComponent(exclude)}`);
      setRandoms(response.results);
      setNotice(response.results.length ? "おまかせ候補を更新しました。気になる商品を追加してください。" : "送別・予算内で追加できる商品がありません。");
    });
  }

  const editable = data?.phase === "collecting" && data.me.canPropose && !data.me.submitted;
  const shown = method === "favorites" ? favorites.gifts : method === "random" ? randoms : results;

  return <RoomShell title={data?.room.title}><div className={styles.workspace}>
    <div className="room-page-intro"><p className="room-eyebrow">みんなで選ぶ送別ギフト</p><h1>{data?.room.title ?? "ギフトを一緒に決めよう"}</h1>
      <p>候補を持ち寄って、同じ情報を見ながら納得できる贈りものへ。</p></div>
    {error && <p className="room-error" role="alert">{error} <button disabled={busy} onClick={() => run(async () => { await reload(); })}>最新の状況を確認</button> <a href={`/rooms/${encodeURIComponent(roomId)}/select?legacy=1`}>以前のルームを引き継ぐ</a></p>}
    <p role="status" className={styles.notice}>{notice}</p>
    {joining && <form className="room-panel" onSubmit={event => { event.preventDefault(); run(async () => { await joinLocalRoom(roomId, nickname.trim()); await reload(true); }); }}>
      <h2>名前を入力して参加する</h2><p>表示用のニックネームです。投票・コメントに名前は表示されません。</p>
      <label>ニックネーム<input value={nickname} onChange={e => setNickname(e.target.value)} maxLength={30} required /></label>
      <button className="room-button" disabled={busy || !nickname.trim()}>参加する</button><p><a href={`/rooms/${encodeURIComponent(roomId)}/select?legacy=1`}>以前のルームを引き継ぐ</a></p></form>}
    {!data && !joining && !error && <p role="status">ルームを読み込んでいます…</p>}
    {data && <>
      <div className={styles.context}><span>参加中：{data.me.name}さん</span><strong>総予算 ¥{data.room.budgetTotal.toLocaleString()}</strong><span>提出 {data.progress.submitted} / {data.progress.designated}人</span>
        <button disabled={busy} onClick={() => run(async () => { await reload(); setNotice("最新の状況を確認しました。編集中の候補は残しています。"); })}>状況を更新</button></div>
      <section className={`room-panel ${styles.notes}`} aria-label="相手についての共有情報"><div className={styles.sectionTitle}><div><p className="room-eyebrow">みんなの手掛かり</p><h2>相手の好み・気をつけたいこと</h2></div><span>全員が入力できます</span></div>
        {data.notes.length ? <ul>{data.notes.map(n => <li key={n.id}><strong>{n.kind}</strong><span>{n.text}</span></li>)}</ul> : <p>まだ情報がありません。知っていることをひとこと共有しましょう。</p>}
        {data.phase !== "decided" && <form onSubmit={e => { e.preventDefault(); run(async () => { await selectionRequest(roomId, "/notes", "POST", { kind: noteKind, text: note }); setNote(""); await reload(); }); }} className={styles.noteForm}>
          <label>情報の種類<select value={noteKind} onChange={e => setNoteKind(e.target.value)}><option>好み</option><option>アレルギー・避けたいもの</option><option>その他</option></select></label>
          <label>共有する情報<textarea value={note} maxLength={300} rows={2} onChange={e => setNote(e.target.value)} placeholder="例：コーヒーをよく飲むと本人が話していた" required /></label>
          <button className="room-button" disabled={busy || !note.trim()}>匿名で共有</button></form>}
        <p className="room-help">本人談か推測かも添えてください。実名・連絡先・健康情報の詳細は入力しないでください。記載内容は商品の安全性を保証するものではなく、アレルギー等は商品情報での確認が必要です。</p>
      </section>
      <nav className={styles.steps} aria-label="ギフト決定の手順">
        {([['propose', '01 候補を提出'], ['compare', '02 比較・★評価'], ['results', '03 集計・決定']] as const).map(([key, label]) => <button key={key} aria-current={tab === key ? "step" : undefined} disabled={busy || (key !== "propose" && data.phase === "collecting")} onClick={() => { setTab(key); setConfirming(false); }}>{label}</button>)}
      </nav>
      {tab === "propose" && <>
        {data.me.isOrganizer && data.phase === "collecting" && <section className="room-panel"><h2>候補を提出する人を指定する</h2><p>主催者を含めて最大5人を選べます。それ以外の参加者も、共有情報・投票・コメントで参加できます。</p>
          <div className={styles.memberList}>{data.members.map(m => <label key={m.id}><input type="checkbox" checked={submitters.includes(m.id)} disabled={busy || data.progress.submitted > 0 || (!submitters.includes(m.id) && submitters.length >= 5)} onChange={e => setSubmitters(e.target.checked ? [...submitters, m.id] : submitters.filter(id => id !== m.id))} />{m.name}さん</label>)}</div>
          <button className="room-button" disabled={busy || !submitters.length || data.progress.submitted > 0} onClick={() => run(async () => { await selectionRequest(roomId, "/submitters", "PUT", { memberIds: submitters }); await reload(); setNotice("提出者を指定しました。"); })}>この{submitters.length}人を提出者にする</button>
          <p className="room-help">最初の提出後は提出者を変更できません。最大5人×3品で、提出商品は15品以内です。</p></section>}
        {editable ? <div className={styles.proposalLayout}><section className="room-panel"><p className="room-eyebrow">あなたの提案</p><h2>喜んでもらえそうな商品を選ぶ</h2><p>3つの選び方を合わせて最大3品。1品から提出できます。</p>
          <div className={styles.methods}>{([['search', '検索して選ぶ'], ['favorites', 'お気に入り'], ['random', 'おまかせ']] as const).map(([key, label]) => <button key={key} disabled={busy} aria-pressed={method === key} onClick={() => setMethod(key)}>{label}</button>)}</div>
          {method === "search" && <form className={styles.search} onSubmit={e => { e.preventDefault(); run(async () => { setResults(await searchGifts({ keyword, category: "", indivWrap: false, priceBand: "" })); setNotice("検索結果を更新しました。"); }); }}><label>キーワード<input value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="コーヒー、タオル…" /></label><button className="room-button" disabled={busy}>検索</button></form>}
          {method === "favorites" && <><p>このブラウザーに保存した送別用のお気に入りです。</p>{favorites.error && <p role="alert">{favorites.error}</p>}</>}
          {method === "random" && <><p>送別シーン・総予算内の商品からランダムに最大3品を表示します。追加するまでは提出候補になりません。</p><button className="room-button" onClick={shuffle} disabled={busy}>{randoms.length ? "もう一度シャッフル" : "おまかせ候補を見る"}</button><p className="room-help">好み・アレルギー・お届け日の適合は未確認です。条件に合う商品が少ない場合、同じ商品が表示されることがあります。</p></>}
          <div className={styles.productGrid}>{shown.map(gift => <article className={styles.product} key={gift.id}><span className={styles.category}>{gift.category}</span><p>{gift.brand}</p><h3>{gift.name}</h3><strong>¥{gift.price.toLocaleString()}</strong>{gift.price > data.room.budgetTotal && <p className={styles.warning}>総予算を超えています</p>}<button disabled={busy || products.length >= 3 || products.some(p => p.productId === gift.id)} onClick={() => add(gift)}>{products.some(p => p.productId === gift.id) ? "追加済み" : "＋ 候補に追加"}</button></article>)}</div>
          {!shown.length && <p className={styles.empty}>{method === "favorites" ? "お気に入りはまだありません。" : method === "random" ? "おまかせ候補を見ると、ここに表示されます。" : "キーワードを入れて検索。空欄でも検索できます。"}</p>}
        </section><aside className={`room-panel ${styles.stock}`}><h2>あなたの候補 <span>{products.length} / 3</span></h2><p>全員の提出がそろうまでは本人だけに表示されます。</p>
          {products.map(p => <article key={p.productId}><h3>{p.gift.name}</h3><strong>¥{p.gift.price.toLocaleString()}</strong><label>選んだ理由（任意）<textarea value={p.reason} maxLength={100} rows={2} disabled={busy} onChange={e => { setProducts(products.map(item => item.productId === p.productId ? { ...item, reason: e.target.value } : item)); setDirty(true); }} /></label><button disabled={busy} onClick={() => { setProducts(products.filter(item => item.productId !== p.productId)); setDirty(true); }}>候補から外す</button></article>)}
          {!products.length && <p className={styles.empty}>商品を追加するとここに並びます。</p>}
          <button disabled={busy || !dirty} onClick={() => run(async () => { await save(); setNotice("下書きを保存しました。"); })}>下書きを保存</button>
          <button className="room-button" disabled={busy || !products.length} onClick={() => run(async () => { if (dirty) await save(); await selectionRequest(roomId, "/submit", "POST"); const value = await reload(true); setNotice("候補を提出しました。"); if (value.phase === "voting") setTab("compare"); })}>この{products.length}品を提出する</button>
          <p className="room-help">提出後は変更できません。理由に名前などを書かないでください。</p>{dirty && <p role="status">未保存の変更があります</p>}
        </aside></div> : <section className="room-panel"><h2>{data.me.submitted ? "候補を提出しました" : "みんなの提案を待っています"}</h2><p>{data.phase === "collecting" ? `提出者 ${data.progress.designated}人のうち${data.progress.submitted}人が提出済みです。全員そろうと比較・投票を始められます。` : "候補がそろいました。比較・★評価へ進んでください。"}</p><p>ページ上部から、相手の好みなどは全員が共有できます。</p>{data.phase !== "collecting" && <button className="room-button" onClick={() => setTab("compare")}>比較・★評価へ</button>}</section>}
      </>}
      {tab === "compare" && data.phase !== "collecting" && <section><div className={styles.sectionTitle}><div><h2>みんなの候補を比べる</h2><p>各商品に★1〜3で評価できます。未評価は賛成として数えません。</p></div><span>{data.candidates.length}品 / 最大15品</span></div>
        <p className="room-help">投票・コメント・候補の提案者名は表示しません。★の合計は全員の同意を意味しません。評価は決定まで変更できます。</p>
        <div className={styles.comparison}>{data.candidates.map(c => <article className={`room-panel ${styles.candidate}`} key={c.gift.id}><span className={styles.category}>{c.gift.category}</span><p>{c.gift.brand}</p><h3>{c.gift.name}</h3><strong>¥{c.gift.price.toLocaleString()}</strong>{c.reasons.map(reason => <p key={reason} className={styles.reason}>{reason}</p>)}
          <p className={styles.score}>★ {c.totalStars}<small>合計 / {c.voters}人が評価</small></p><div className={styles.stars} role="group" aria-label={`${c.gift.name}の評価`}>{[1, 2, 3].map(stars => <button key={stars} aria-label={`${c.gift.name}に星${stars}`} aria-pressed={c.myStars === stars} disabled={busy || data.phase !== "voting"} onClick={() => run(async () => { await selectionRequest(roomId, `/products/${encodeURIComponent(c.gift.id)}/vote`, "PUT", { stars }); await reload(); })}>{"★".repeat(stars)}</button>)}</div><p className="room-help">あなたの評価：{c.myStars ? `★${c.myStars}` : "未評価"}</p>
          <div className={styles.comments}><h4>匿名コメント</h4>{c.comments.length ? c.comments.map(comment => <p key={comment.id}>{comment.text}</p>) : <p>まだコメントはありません。</p>}</div>
          {data.phase === "voting" && <form onSubmit={e => { e.preventDefault(); run(async () => { await selectionRequest(roomId, `/products/${encodeURIComponent(c.gift.id)}/comments`, "POST", { text: comments[c.gift.id] ?? "" }); setComments({ ...comments, [c.gift.id]: "" }); await reload(); }); }}><label>気になる点・良い点<textarea value={comments[c.gift.id] ?? ""} maxLength={300} rows={2} onChange={e => setComments({ ...comments, [c.gift.id]: e.target.value })} required /></label><button disabled={busy || !comments[c.gift.id]?.trim()}>匿名でコメント</button></form>}
        </article>)}</div><button className="room-button" onClick={() => setTab("results")}>集計を見る →</button></section>}
      {tab === "results" && data.phase !== "collecting" && <section className="room-panel"><p className="room-eyebrow">みんなで決めた贈りものへ</p><h2>{data.decision ? "このルームでの決定商品" : "評価を確認して、贈り方を決める"}</h2>
        {data.decision ? <><p className={styles.decisionBadge}>{data.decision.mode === "single" ? "1品に決定" : "受取人が1品選ぶカタログに決定"}</p><div className={styles.productGrid}>{data.decision.products.map(gift => <article className={styles.product} key={gift.id}><p>{gift.brand}</p><h3>{gift.name}</h3><strong>¥{gift.price.toLocaleString()}</strong></article>)}</div><p>決定内容を保存しました。同じルームのURLから、後で見返せます。</p><p className="room-help">購入確認はデモです。注文・支払い・配送は行っていません。</p>{data.decision.mode === "catalog" && <details className={styles.preview}><summary>受取人用カタログのプレビュー</summary><h3>あなたに贈りたいギフト</h3><p>こちらの中から、お好きな1品をお選びください。</p>{data.decision.products.map(gift => <p key={gift.id}>{gift.name}</p>)}<p>プレビューのみ。実際の選択・配送の受付は行いません。</p></details>}</> : <>
          <ol className={styles.ranking}>{data.candidates.map(c => <li key={c.gift.id}><span>{c.gift.name}</span><strong>★{c.totalStars}</strong><small>{c.voters}人が評価</small></li>)}</ol><p className="room-help">同点の商品は同じ合計点です。自動で勝者を決めず、コメントや共有情報も確認して主催者が確定します。</p>
          {data.me.isOrganizer ? <><div className={styles.methods}><button aria-pressed={mode === "single"} disabled={busy} onClick={() => { setMode("single"); setPicked([]); setConfirming(false); }}>1品を贈る</button><button aria-pressed={mode === "catalog"} disabled={busy} onClick={() => { setMode("catalog"); setPicked([]); setConfirming(false); }}>カタログにして贈る</button></div><p>{mode === "single" ? "贈る商品を1品選んでください。" : "カタログに載せる候補を選んでください。受取人はその中から1品選びます。"}</p>
            <div className={styles.pickList}>{data.candidates.map(c => <label key={c.gift.id}><input type={mode === "single" ? "radio" : "checkbox"} name="decision-product" checked={picked.includes(c.gift.id)} disabled={busy} onChange={e => { setPicked(mode === "single" ? [c.gift.id] : e.target.checked ? [...picked, c.gift.id] : picked.filter(id => id !== c.gift.id)); setConfirming(false); }} /><span>{c.gift.name}</span><strong>¥{c.gift.price.toLocaleString()}</strong></label>)}</div>
            {!confirming ? <button className="room-button" disabled={busy || !picked.length} onClick={() => setConfirming(true)}>デモの購入確認へ</button> : <div className={styles.confirmation}><h3>この内容で決定しますか？</h3><p>{mode === "single" ? "選んだ1品を贈ります。" : `${picked.length}品をカタログに載せ、受取人が1品選ぶ形式です。`}</p>{data.candidates.filter(c => picked.includes(c.gift.id)).map(c => <p key={c.gift.id}>{c.gift.name} · ¥{c.gift.price.toLocaleString()}</p>)}<p>確定後は候補・評価・コメントを変更できません。支払い・注文は発生しません。</p><button className="room-button" disabled={busy} onClick={() => run(async () => { await selectionRequest(roomId, "/decision", "POST", { mode, productIds: picked }); await reload(); setNotice("このルームの決定内容を保存しました。"); })}>この内容で決定・保存する</button><button disabled={busy} onClick={() => setConfirming(false)}>選び直す</button></div>}
          </> : <p>主催者が最終商品・贈り方を確定すると、ここに決定内容が表示されます。</p>}
        </>}
      </section>}
      <div className={styles.footer}><Link href={`/rooms/${encodeURIComponent(roomId)}`}>ルームの基本情報へ</Link><span>{data.catalogSource === "shared" ? "商品：共通DB" : "商品：架空データ"} · {data.storageSource === "shared" ? "ルーム・提案・評価・決定：共通DBに保存" : "ルーム情報はこのAPIのSQLiteに保存"}</span></div>
    </>}
  </div></RoomShell>;
}
