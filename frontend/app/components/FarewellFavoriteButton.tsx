"use client";

import { useState } from "react";
import type { Gift } from "@/lib/api";
import { useFarewellFavorites } from "@/lib/useFarewellFavorites";
import styles from "./farewellFavorites.module.css";

export default function FarewellFavoriteButton({ gift }: { gift: Gift }) {
  const { gifts, error, setFavorite } = useFarewellFavorites();
  const selected = gifts.some(item => item.id === gift.id);
  const [notice, setNotice] = useState("");

  return <div className={styles.action}>
    <button type="button" aria-pressed={selected} aria-label={`${gift.name}を送別用のお気に入り${selected ? "から解除" : "に保存"}`}
      onClick={() => {
        setNotice("");
        if (setFavorite(gift, !selected)) setNotice(selected ? "お気に入りを解除しました。" : "送別用のお気に入りに保存しました。");
      }}>
      <span aria-hidden="true">{selected ? "♥" : "♡"}</span> {selected ? "送別用に保存済み" : "送別用のお気に入りに保存"}
    </button>
    {error && <p role="alert" className={styles.error}>{error}</p>}
    <span role="status" className={styles.notice}>{notice}</span>
  </div>;
}
