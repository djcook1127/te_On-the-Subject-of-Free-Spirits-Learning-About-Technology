"use client";

import Link from "next/link";
import ResultCard from "../../ResultCard";
import FarewellFavoriteButton from "../../components/FarewellFavoriteButton";
import { useFarewellFavorites } from "@/lib/useFarewellFavorites";
import styles from "../../components/farewellFavorites.module.css";

export default function FarewellFavoritesPage() {
  const { gifts, error } = useFarewellFavorites();
  return <main className="page">
    <header className="header"><h1>Giftia</h1></header>
    <div className={styles.bar}><Link href="/" className={styles.link}>← 普段の検索へ</Link></div>
    <h2 className={styles.title}>送別用のお気に入り</h2>
    <p>気になった商品を、ルームを作る前から集めておけます。ルームの「お気に入りから選ぶ」で、候補に取り込めます。</p>
    <p className={styles.note}>お気に入りは、このブラウザーに保存されます。同じアドレスで開く画面間で利用できます。別端末や別ブラウザーとは同期されません。</p>
    {error && <p role="alert" className={styles.error}>{error}</p>}
    <p role="status">{gifts.length}件を保存中</p>
    {!error && gifts.length === 0 && <p className={styles.empty}>まだお気に入りはありません。普段の検索で、気になる商品を保存してみましょう。</p>}
    <div className="grid">{gifts.map((gift, index) => <article key={gift.id}>
      <ResultCard gift={gift} rank={index + 1} />
      <FarewellFavoriteButton gift={gift} />
    </article>)}</div>
    <p className={styles.note}>価格などは保存時の情報です。注文前に最新情報を確認してください。</p>
  </main>;
}
