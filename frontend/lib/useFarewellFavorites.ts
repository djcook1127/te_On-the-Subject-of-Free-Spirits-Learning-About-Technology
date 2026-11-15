"use client";

import { useMemo, useState, useSyncExternalStore } from "react";
import type { Gift } from "./api";
import { decodeFavorites, FAVORITES_KEY, updateFavorite } from "./farewellFavoritesStore";

const CHANGED = "giftia:farewell-favorites-changed";
const UNAVAILABLE = "storage-unavailable";

function getSnapshot() {
  try { return window.localStorage.getItem(FAVORITES_KEY); }
  catch { return UNAVAILABLE; }
}

function subscribe(callback: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key === FAVORITES_KEY || event.key === null) callback();
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener(CHANGED, callback);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(CHANGED, callback);
  };
}

export function useFarewellFavorites() {
  // サーバー描画時は空にし、保存済みデータはブラウザーで取得する。
  const raw = useSyncExternalStore(subscribe, getSnapshot, () => null);
  const snapshot = useMemo(() => raw === UNAVAILABLE
    ? { gifts: [], error: "このブラウザーではお気に入りの保存先を利用できません。" }
    : decodeFavorites(raw), [raw]);
  const [writeError, setWriteError] = useState("");

  function setFavorite(gift: Gift, selected: boolean): boolean {
    try {
      updateFavorite(window.localStorage, gift, selected);
      setWriteError("");
      window.dispatchEvent(new Event(CHANGED));
      return true;
    } catch (error) {
      setWriteError((error as Error).message);
      return false;
    }
  }

  return { gifts: snapshot.gifts, error: snapshot.error || writeError, setFavorite };
}
