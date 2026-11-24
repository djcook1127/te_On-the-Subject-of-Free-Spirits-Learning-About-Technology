"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { searchGifts, type Gift } from "@/lib/api";
import { joinLocalRoom } from "@/lib/localParticipation";
import { ParticipationRequired, restoreImportedRoom, selectionRequest, type ProposalProduct, type Selection } from "@/lib/selection";
import { useFarewellFavorites } from "@/lib/useFarewellFavorites";
import RoomShell from "../../RoomShell";
import styles from "./selection.module.css";
import RoomSettingsEditor from "./RoomSettingsEditor";
import DecisionCelebration from "./DecisionCelebration";

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
  const [keyword, setKeyword] = useState("");
  const [results, setResults] = useState<Gift[]>([]);
  const [searching, setSearching] = useState(false);
  const [randomLoading, setRandomLoading] = useState(false);
  const searchController = useRef<AbortController | null>(null);
  const randomRequest = useRef(0);
  const cancelQueries = useCallback(() => {
    searchController.current?.abort(); randomRequest.current++;
  }, []);
  const [randoms, setRandoms] = useState<Gift[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [category, setCategory] = useState("");
  const [categoryError, setCategoryError] = useState("");
  const [categoryLoading, setCategoryLoading] = useState(true);
  const [method, setMethod] = useState<"search" | "favorites" | "random">("search");
  const [tab, setTab] = useState<"propose" | "compare" | "results">("propose");
  const [roomComment, setRoomComment] = useState("");
  const [commentKind, setCommentKind] = useState("好み");
  const [entered, setEntered] = useState(false);
  const [curating, setCurating] = useState(false);
  const [replaceProductId, setReplaceProductId] = useState<string | null>(null);
  const [reasonSources, setReasonSources] = useState<("votes" | "comments" | "other")[]>([]);
  const [otherReason, setOtherReason] = useState("");
  const reasonLabels = { votes: "投票結果を参考にした", comments: "コメントを参考にした", other: "その他" };
  const reasonsValid = reasonSources.length > 0 && (!reasonSources.includes("other") || !!otherReason.trim());
  const [mode, setMode] = useState<"single" | "catalog">("single");
  const [picked, setPicked] = useState<string[]>([]);
  const [confirming, setConfirming] = useState(false);
  const favorites = useFarewellFavorites();

  async function reload(resetDraft = false) {
    const value = await selectionRequest<Selection>(roomId);
    setData(value); setJoining(false);
    if (resetDraft) { setProducts(value.ownProducts); setVersion(value.me.version); setDirty(false); }
    return value;
  }

  async function mutate(path: string, method = "POST", body?: unknown) {
    const result = await selectionRequest<{ selection: Selection }>(roomId, path, method, body);
    setData(result.selection);
    return result.selection;
  }

  async function rate(productId: string, stars: number) {
    if (!data) return;
    const previous = data;
    setData({ ...data, candidates: data.candidates.map(candidate => candidate.gift.id === productId ? {
      ...candidate, totalStars: candidate.totalStars - (candidate.myStars ?? 0) + stars,
      voters: candidate.voters + (candidate.myStars === null ? 1 : 0), myStars: stars,
    } : candidate) });
    setNotice("評価を保存しています…");
    try {
      await mutate(`/products/${encodeURIComponent(productId)}/vote`, "PUT", { stars });
      setNotice("評価を保存しました。");
    } catch (err) {
      setData(previous); // 先に描いた星を、保存失敗時には戻す。
      throw err;
    }
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
      setEntered(value.phase !== "collecting");
      setData(value); setProducts(value.ownProducts); setVersion(value.me.version);
      setTab(value.phase === "decided" ? "results" : value.phase === "voting" ? "compare" : "propose");
    }).catch(err => {
      if (!active) return;
      if (err instanceof ParticipationRequired) setJoining(true);
      else setError(err.message);
    });
    return () => { active = false; cancelQueries(); };
  }, [roomId, cancelQueries]);

  const collecting = data?.phase === "collecting";
  useEffect(() => {
    if (!collecting || !data?.me.canPropose || method !== "random") return;
    let active = true;
    selectionRequest<{ categories: string[] }>(roomId, "/categories").then(value => {
      if (active) { setCategories(value.categories); setCategoryError(""); }
    }).catch(err => { if (active) setCategoryError(err.message); })
      .finally(() => { if (active) setCategoryLoading(false); });
    return () => { active = false; };
  }, [roomId, collecting, data?.me.canPropose, data?.room.budgetTotal, method]);

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
    if (busy) return;
    if (curating && data?.me.isOrganizer) {
      void run(async () => {
        await mutate("/curation", "POST", { productId: gift.id, replaceProductId });
        setCurating(false); setReplaceProductId(null);
        setNotice("投票用の候補を更新しました。");
      });
      return;
    }
    if (products.length >= 10 || products.some(p => p.productId === gift.id)) return;
    setProducts(current => current.length >= 10 || current.some(p => p.productId === gift.id) ? current : [...current, { productId: gift.id, gift, reason: "" }]);
    setDirty(true); setNotice("自分の下書きに追加しました。提出すると全員に共有されます。");
  }

  async function save() {
    const result = await selectionRequest<{ version: number }>(roomId, "/proposal", "PUT", {
      version, products: products.map(p => ({ productId: p.productId, reason: p.reason })),
    });
    setVersion(result.version); setDirty(false);
  }

  async function search() {
    searchController.current?.abort();
    const controller = new AbortController();
    searchController.current = controller;
    setSearching(true); setError("");
    try {
      const gifts = await searchGifts({ keyword, category: "", indivWrap: false, priceBand: "" }, controller.signal);
      if (!controller.signal.aborted) setResults(gifts);
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "検索結果を取得できません");
    } finally {
      if (!controller.signal.aborted) setSearching(false);
    }
  }

  async function shuffle() {
    const request = ++randomRequest.current;
    setRandomLoading(true); setError("");
    try {
      const exclude = products.map(p => p.productId).join(",");
      const response = await selectionRequest<{ results: Gift[] }>(roomId, `/random?category=${encodeURIComponent(category)}&exclude=${encodeURIComponent(exclude)}`);
      if (request === randomRequest.current) {
        setRandoms(response.results);
        setNotice(response.results.length ? "おまかせ候補を更新しました。気になる商品を追加してください。" : "送別・予算内で追加できる商品がありません。");
      }
    } catch (err) {
      if (request === randomRequest.current) setError(err instanceof Error ? err.message : "おまかせを取得できません");
    } finally {
      if (request === randomRequest.current) setRandomLoading(false);
    }
  }

  const editable = data?.phase === "collecting";
  const shown = method === "favorites" ? favorites.gifts : method === "random" ? randoms : results;
  // 投票中は保存レスポンスの得点順に影響されず、同じ商品を同じ位置に表示する。
  const votingCandidates = data ? [...data.candidates].sort((a, b) => a.gift.id.localeCompare(b.gift.id)) : [];

  return <RoomShell title={data?.room.title}><div className={styles.workspace}>
    <div className="room-page-intro"><p className="room-eyebrow">みんなで選ぶ送別ギフト</p><h1>{data?.room.title ?? "ギフトを一緒に決めよう"}</h1></div>
    {error && <p className="room-error" role="alert">{error} <button disabled={busy} onClick={() => run(async () => { await reload(); })}>最新の状況を確認</button> <a href={`/rooms/${encodeURIComponent(roomId)}/select?legacy=1`}>以前のルームを引き継ぐ</a></p>}
    <p role="status" className={styles.notice}>{notice}</p>
    {joining && <form className="room-panel" onSubmit={event => { event.preventDefault(); run(async () => {
      const invite = new URLSearchParams(window.location.hash.slice(1)).get("invite");
      await joinLocalRoom(roomId, nickname.trim(), invite ?? undefined);
      if (invite) window.history.replaceState(null, "", window.location.pathname + window.location.search);
      await reload(true);
    }); }}>
      <h2>名前を入力して参加する</h2><p>表示用のニックネームです。投票・コメントに名前は表示されません。</p>
      <label>ニックネーム<input value={nickname} onChange={e => setNickname(e.target.value)} maxLength={30} required /></label>
      <button className="room-button" disabled={busy || !nickname.trim()}>参加する</button><p><a href={`/rooms/${encodeURIComponent(roomId)}/select?legacy=1`}>以前のルームを引き継ぐ</a></p></form>}
    {!data && !joining && !error && <p role="status">ルームを読み込んでいます…</p>}
    {data && <>
      <div className={styles.context}><span>参加中：{data.me.name}さん</span><strong>総予算 ¥{data.room.budgetTotal.toLocaleString()}</strong><span>候補 {data.progress.candidateCount} / 10品 · {collecting ? "候補提出期間" : data.phase === "voting" ? "投票中" : "決定済み"}</span>
        <button disabled={busy} onClick={() => run(async () => { await reload(); setNotice("最新の状況を確認しました。編集中の候補は残しています。"); })}>状況を更新</button></div>
      <RoomSettingsEditor data={data} busy={busy} onSave={action => run(async () => {
        const latest = await action(); setData(latest); randomRequest.current++; setRandomLoading(false); setRandoms([]); setCategory(""); setCategories([]); setCategoryLoading(true);
        setNotice("ルーム情報を更新しました。予算を変更した場合は候補の価格を確認してください。");
      })} />
      {collecting && !entered ? <section className={`room-panel ${styles.notes}`} aria-label="入室時のコメント">
        <p className="room-eyebrow">入室時に、知っていることをひとこと</p><h2>贈る相手について教えてください</h2><p>情報があれば匿名で共有できます。分からない場合は、そのまま入室できます。</p>
        <form onSubmit={e => { e.preventDefault(); run(async () => { await mutate("/comments", "POST", { kind: commentKind, text: roomComment }); setRoomComment(""); setEntered(true); }); }}>
          <label>コメントの種類<select value={commentKind} onChange={e => setCommentKind(e.target.value)}><option>好み</option><option>避けたいもの</option><option>その他</option></select></label>
          <label>贈る相手について<textarea value={roomComment} maxLength={300} rows={3} onChange={e => setRoomComment(e.target.value)} placeholder={commentKind === "好み" ? "例：コーヒーをよく飲むと本人が話していた" : commentKind === "避けたいもの" ? "例：強い香りは苦手だと聞いた" : "例：荷物が増えるので、小さく持ち帰れる品がよさそう"} required /></label>
          <button className="room-button" disabled={busy || !roomComment.trim()}>コメントして入室</button><button type="button" disabled={busy} onClick={() => setEntered(true)}>コメントせず入室</button>
        </form>
      </section> : <>
      <section className={`room-panel ${styles.notes}`} aria-label="贈る相手についてのコメント">
        <div className={styles.sectionTitle}><h2>相手の好み・避けたいもの</h2><span>入室時に寄せられた匿名コメント</span></div>
        <div className={styles.comments}>{data.comments.length ? data.comments.map(comment => <div key={comment.id}><strong>{comment.kind}</strong>{comment.legacyProduct && <small> 以前の商品コメント：{comment.legacyProduct}</small>}<p>{comment.text}</p></div>) : <p>まだコメントはありません。</p>}</div>
        {collecting && data.me.isOrganizer && <p className="room-help">コメントを確認し、必要なら投票候補を追加・差し替えできます。</p>}
      </section>
      <nav className={styles.steps} aria-label="ギフト決定の手順">
        {([['propose', '01 候補を提出'], ['compare', '02 比較・★評価'], ['results', '03 集計・決定']] as const).map(([key, label]) => <button key={key} aria-current={tab === key ? "step" : undefined} disabled={busy || (key !== "propose" && data.phase === "collecting")} onClick={() => { setTab(key); setConfirming(false); }}>{label}</button>)}
      </nav>
      {tab === "propose" && <>
        {data.phase === "collecting" && <section className="room-panel"><p className="room-eyebrow">候補提出期間</p><h2>みんなで候補を持ち寄る</h2><p>候補は匿名で共有されます。みんなで最大10品まで選べます。</p>{!data.initialProposalSubmitted && <p className={styles.warning}>{data.me.isOrganizer ? "まずは最初の候補を提出しましょう。提出すると、参加者も候補を追加できます。" : "開設者の最初の候補を待っています。入室コメントは先に共有できます。「状況を更新」で開始状況を確認してください。"}</p>}<p>提出済みの候補：{data.progress.candidateCount} / 10品</p>
          {data.me.isOrganizer ? <><button className="room-button" disabled={busy || data.progress.candidateCount === 0} onClick={() => run(async () => { await mutate("/start-voting"); setTab("compare"); setNotice("投票を開始しました。全員が★1〜3で評価できます。"); })}>投票開始</button><p className="room-help">候補がそろったら投票を始めましょう。開始後は候補を変更できません。</p></> : <p>主催者が「投票開始」を押すと、全員で★評価できるようになります。</p>}
          {data.me.isOrganizer && <button disabled={busy || data.progress.candidateCount >= 10} onClick={() => { setCurating(true); setReplaceProductId(null); }}>投票候補を追加する</button>}
          {data.candidates.length > 0 && <div className={styles.productGrid}>{data.candidates.map(c => <article className={styles.product} key={c.gift.id}><span className={styles.category}>{c.gift.category}</span><h3>{c.gift.name}</h3><strong>¥{c.gift.price.toLocaleString()}</strong>{c.reasons.map(reason => <p key={reason}>{reason}</p>)}{data.me.isOrganizer && <><button disabled={busy} onClick={() => { setCurating(true); setReplaceProductId(c.gift.id); }}>差し替える</button><button disabled={busy} onClick={() => run(async () => { await mutate("/curation/remove", "POST", { productId: c.gift.id }); setNotice("投票候補から外しました。元の下書きは残しています。"); })}>候補から外す</button></>}</article>)}</div>}
        </section>}
        {editable && !data.me.canPropose ? <section className="room-panel"><h2>開設者の候補提出を待っています</h2><p>最初の候補が提出されると、ここから商品を追加できます。</p></section> : editable ? <div className={styles.proposalLayout}><section className="room-panel"><p className="room-eyebrow">{curating ? "主催者の候補調整" : "あなたの提案"}</p><h2>{curating ? "投票用のギフトを選ぶ" : "喜んでもらえそうな商品を選ぶ"}</h2><p>検索・お気に入り・おまかせから選べます。</p>
          <div className={styles.methods}>{([['search', '検索して選ぶ'], ['favorites', 'お気に入り'], ['random', 'おまかせ']] as const).map(([key, label]) => <button key={key} disabled={busy} aria-pressed={method === key} onClick={() => setMethod(key)}>{label}</button>)}</div>
          {method === "search" && <><form className={styles.search} onSubmit={e => { e.preventDefault(); void search(); }}><label>キーワード<input value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="コーヒー、タオル…" /></label><button className="room-button" disabled={busy || searching}>{searching ? "検索中…" : "検索"}</button></form>{searching && <p role="status">検索しています…</p>}</>}
          {method === "favorites" && <><p>保存したお気に入りから選べます。</p>{favorites.error && <p role="alert">{favorites.error}</p>}</>}
          {method === "random" && <><p>ご予算に合う高評価のギフトを、選んだカテゴリーからご紹介します。</p><label>おまかせのカテゴリー<select value={category} onChange={e => { randomRequest.current++; setRandomLoading(false); setCategory(e.target.value); setRandoms([]); }} disabled={busy}><option value="">カテゴリーを選んでください</option>{categories.map(value => <option key={value} value={value}>{value}</option>)}</select></label>{categoryError && <p role="alert">{categoryError}</p>}{!categoryError && categories.length === 0 && <p>{categoryLoading ? "カテゴリーを確認しています…" : "ご予算に合う商品が見つかりませんでした。"}</p>}<button className="room-button" onClick={shuffle} disabled={busy || randomLoading || !category}>{randomLoading ? "候補を取得中…" : randoms.length ? "もう一度シャッフル" : "おまかせ候補を見る"}</button></>}
          <div className={styles.productGrid}>{shown.map(gift => <article className={styles.product} key={gift.id}><span className={styles.category}>{gift.category}</span><p>{gift.brand}</p><h3>{gift.name}</h3><strong>¥{gift.price.toLocaleString()}</strong><small>商品レビュー ★{gift.rating.toFixed(1)}</small>{gift.price > data.room.budgetTotal && <p className={styles.warning}>総予算を超えています</p>}<button disabled={busy || (!curating && (products.length >= 10 || products.some(p => p.productId === gift.id)))} onClick={() => add(gift)}>{curating ? (replaceProductId ? "この商品に差し替える" : "投票候補に追加") : products.some(p => p.productId === gift.id) ? "追加済み" : "＋ 候補に追加"}</button></article>)}</div>
          {!shown.length && <div className={styles.empty}>{method === "favorites" ? <><p>お気に入りはまだありません。</p><strong>会員登録がお済みでない方へ</strong><p>新規登録をご検討ください。</p></> : method === "random" ? "カテゴリーを選んで、おまかせ候補を見てみましょう。" : "キーワードを入れて検索。空欄でも検索できます。"}</div>}
        </section>{curating ? <aside className={`room-panel ${styles.stock}`}><h2>{replaceProductId ? "候補を差し替える" : "投票候補を追加する"}</h2>{replaceProductId && <p>差し替え対象：{data.candidates.find(c => c.gift.id === replaceProductId)?.gift.name}</p>}<p>商品を選んで、投票候補を整えましょう。</p><button disabled={busy} onClick={() => { setCurating(false); setReplaceProductId(null); }}>通常の提案に戻る</button></aside> : <aside className={`room-panel ${styles.stock}`}><h2>あなたの候補 <span>{products.length}品</span></h2><p>下書きは本人だけに表示されます。提出した候補は匿名で全員に共有されます。</p>
          {products.map(p => <article key={p.productId}><h3>{p.gift.name}</h3><strong>¥{p.gift.price.toLocaleString()}</strong><label>選んだ理由（任意）<textarea value={p.reason} maxLength={100} rows={2} disabled={busy} onChange={e => { setProducts(products.map(item => item.productId === p.productId ? { ...item, reason: e.target.value } : item)); setDirty(true); }} /></label><button disabled={busy} onClick={() => { setProducts(products.filter(item => item.productId !== p.productId)); setDirty(true); }}>候補から外す</button></article>)}
          {!products.length && <p className={styles.empty}>商品を追加するとここに並びます。</p>}
          <button disabled={busy || !dirty} onClick={() => run(async () => { await save(); setNotice("下書きを保存しました。"); })}>下書きを保存</button>
          <button className="room-button" disabled={busy || !products.length} onClick={() => run(async () => {
            const result = await selectionRequest<{ selection: Selection }>(roomId, "/submit", "POST", dirty ? { version, products: products.map(p => ({ productId: p.productId, reason: p.reason })) } : undefined);
            const value = result.selection; setData(value); setProducts(value.ownProducts); setVersion(value.me.version); setDirty(false);
            setNotice("匿名で候補を提出しました。主催者の投票開始まで追加・入替できます。"); if (value.phase === "voting") setTab("compare");
          })}>この{products.length}品を提出する</button>
          <p className="room-help">投票開始までは、提出した候補を追加・入替できます。</p>{dirty && <p role="status">未保存の変更があります</p>}
        </aside>}</div> : <section className="room-panel"><h2>候補が確定しました</h2><p>投票開始後は候補を変更できません。比較・★評価へ進んでください。</p><button className="room-button" onClick={() => setTab("compare")}>比較・★評価へ</button></section>}
      </>}
      {tab === "compare" && data.phase !== "collecting" && <section><div className={styles.sectionTitle}><div><h2>みんなの候補を比べる</h2><p>各商品に★1〜3で評価できます。</p></div><span>{data.candidates.length}品 / 最大10品</span></div>
        <p className="room-help">評価は匿名です。決定まで変更できます。</p>
        <div className={styles.comparison}>{votingCandidates.map(c => <article className={`room-panel ${styles.candidate}`} key={c.gift.id}><span className={styles.category}>{c.gift.category}</span><p>{c.gift.brand}</p><h3>{c.gift.name}</h3><strong>¥{c.gift.price.toLocaleString()}</strong>{c.reasons.map(reason => <p key={reason} className={styles.reason}>{reason}</p>)}
          <p className={styles.score}>★ {c.totalStars}<small>合計 / {c.voters}人が評価</small></p><div className={styles.stars} role="group" aria-label={`${c.gift.name}の評価`}>{[1, 2, 3].map(stars => <button key={stars} aria-label={`${c.gift.name}に星${stars}`} aria-pressed={c.myStars === stars} disabled={busy || data.phase !== "voting"} onClick={() => run(async () => { await rate(c.gift.id, stars); })}>{"★".repeat(stars)}</button>)}</div><p className="room-help">あなたの評価：{c.myStars ? `★${c.myStars}` : "未評価"}</p>

        </article>)}</div><button className="room-button" onClick={() => setTab("results")}>集計を見る →</button></section>}
      {tab === "results" && data.phase !== "collecting" && <section className="room-panel"><p className="room-eyebrow">みんなで決めた贈りものへ</p><h2>{data.decision ? "このルームでの決定商品" : "評価を確認して、贈り方を決める"}</h2>
        {data.decision ? <><DecisionCelebration key={roomId} /><p className={styles.decisionBadge}>{data.decision.mode === "single" ? "1品に決定" : "受取人が1品選ぶカタログに決定"}</p><div className={styles.productGrid}>{data.decision.products.map(gift => <article className={styles.product} key={gift.id}><p>{gift.brand}</p><h3>{gift.name}</h3><strong>¥{gift.price.toLocaleString()}</strong></article>)}</div><section className={styles.savedReasons}><h3>主催者の決定理由</h3>{data.decision.reasonSources?.length ? <><ul>{data.decision.reasonSources.map(code => <li key={code}>{reasonLabels[code]}</li>)}</ul>{data.decision.otherReason && <p>{data.decision.otherReason}</p>}</> : <p>この決定の理由は記録されていません。</p>}</section><p>決定内容を保存しました。同じルームのURLから、後で見返せます。</p><p className="room-help">購入確認はデモです。注文・支払い・配送は行っていません。</p>{data.decision.mode === "catalog" && <details className={styles.preview}><summary>受取人用カタログのプレビュー</summary><h3>あなたに贈りたいギフト</h3><p>こちらの中から、お好きな1品をお選びください。</p>{data.decision.products.map(gift => <p key={gift.id}>{gift.name}</p>)}<p>プレビューのみ。実際の選択・配送の受付は行いません。</p></details>}</> : <>
          {!data.me.isOrganizer && <ol className={styles.ranking}>{data.candidates.map(c => <li key={c.gift.id}><span>{c.gift.name}</span><strong>★{c.totalStars}</strong><small>{c.voters}人が評価</small></li>)}</ol>}
          {data.me.isOrganizer ? <><div className={styles.methods}><button aria-pressed={mode === "single"} disabled={busy} onClick={() => { setMode("single"); setPicked([]); setConfirming(false); }}>1品を贈る</button><button aria-pressed={mode === "catalog"} disabled={busy} onClick={() => { setMode("catalog"); setPicked([]); setConfirming(false); }}>カタログにして贈る</button></div><p>{mode === "single" ? "贈る商品を1品選んでください。" : "カタログに載せる候補を選んでください。受取人はその中から1品選びます。"}</p>
            <div className={styles.pickList}>{data.candidates.map(c => <label key={c.gift.id}><input type={mode === "single" ? "radio" : "checkbox"} name="decision-product" checked={picked.includes(c.gift.id)} disabled={busy} onChange={e => { setPicked(mode === "single" ? [c.gift.id] : e.target.checked ? [...picked, c.gift.id] : picked.filter(id => id !== c.gift.id)); setConfirming(false); }} /><span className={styles.resultName}>{c.gift.name}</span><span className={styles.resultScore}><strong>★{c.totalStars}</strong><small>{c.voters}人が評価</small></span><strong className={styles.resultPrice}>¥{c.gift.price.toLocaleString()}</strong></label>)}</div>
            <fieldset className={styles.decisionReasons}><legend>決定理由（複数選択・必須）</legend>{(["votes", "comments", "other"] as const).map(code => <label key={code}><input type="checkbox" checked={reasonSources.includes(code)} disabled={busy} onChange={e => { setReasonSources(e.target.checked ? [...reasonSources, code] : reasonSources.filter(value => value !== code)); if (code === "other" && !e.target.checked) setOtherReason(""); setConfirming(false); }} />{reasonLabels[code]}</label>)}{reasonSources.includes("other") && <label>その他の理由（必須）<textarea value={otherReason} maxLength={300} rows={3} required onChange={e => { setOtherReason(e.target.value); setConfirming(false); }} /></label>}<p className="room-help">選んだ理由を参加者に共有します。</p></fieldset>
            {!confirming ? <button className="room-button" disabled={busy || !picked.length || !reasonsValid} onClick={() => setConfirming(true)}>購入内容を確認（デモ）</button> : <div className={styles.confirmation}><h3>この内容で決定しますか？</h3><p>決定理由：{reasonSources.map(code => reasonLabels[code]).join("・")}</p>{otherReason && <p>{otherReason}</p>}<p>{mode === "single" ? "選んだ1品を贈ります。" : `${picked.length}品をカタログに載せ、受取人が1品選ぶ形式です。`}</p>{data.candidates.filter(c => picked.includes(c.gift.id)).map(c => <p key={c.gift.id}>{c.gift.name} · ¥{c.gift.price.toLocaleString()}</p>)}<p>確定後は候補・評価・コメントを変更できません。支払い・注文は発生しません。</p><button className="room-button" disabled={busy} onClick={() => run(async () => { await mutate("/decision", "POST", { mode, productIds: picked, reasonSources, otherReason }); setNotice("このルームの決定内容を保存しました。"); })}>この内容で決定・保存する</button><button disabled={busy} onClick={() => setConfirming(false)}>選び直す</button></div>}
          </> : <p>主催者が最終商品・贈り方を確定すると、ここに決定内容が表示されます。</p>}
        </>}
      </section>}
      <div className={styles.footer}><Link href={`/rooms/${encodeURIComponent(roomId)}`}>ルームの基本情報へ</Link></div>
      </>}
    </>}
  </div></RoomShell>;
}
