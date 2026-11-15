import type { Gift } from "./api.ts";

export const FAVORITES_KEY = "giftia.farewell-favorites.v1";
export type FavoriteSnapshot = { gifts: Gift[]; error: string };

function isGift(value: unknown): value is Gift {
  if (!value || typeof value !== "object") return false;
  const gift = value as Record<string, unknown>;
  return ["id", "category", "brand", "name"].every(key => typeof gift[key] === "string")
    && (gift.id as string).trim().length > 0
    && ["price", "rating", "reviewCount"].every(key => typeof gift[key] === "number" && Number.isFinite(gift[key]) && (gift[key] as number) >= 0);
}

export function decodeFavorites(raw: string | null): FavoriteSnapshot {
  if (raw === null) return { gifts: [], error: "" };
  try {
    const data = JSON.parse(raw);
    if (data?.version !== 1 || !Array.isArray(data.gifts) || !data.gifts.every(isGift)) throw new Error();
    if (new Set(data.gifts.map((gift: Gift) => gift.id)).size !== data.gifts.length) throw new Error();
    return { gifts: data.gifts, error: "" };
  } catch {
    return { gifts: [], error: "お気に入りの保存データを読み取れません。元のデータは上書きしていません。" };
  }
}

export type FavoriteStorage = Pick<Storage, "getItem" | "setItem">;

// 保存失敗時に成功を返さず、読めない既存データも黙って初期化しない。
export function updateFavorite(storage: FavoriteStorage, gift: Gift, selected: boolean): void {
  if (!isGift(gift)) throw new Error("商品の情報を確認できません。検索し直してください。");
  let raw: string | null;
  try { raw = storage.getItem(FAVORITES_KEY); }
  catch { throw new Error("このブラウザーではお気に入りの保存先を読み取れません。"); }
  const current = decodeFavorites(raw);
  if (current.error) throw new Error(current.error);
  const remaining = current.gifts.filter(item => item.id !== gift.id);
  const gifts = selected ? [...remaining, gift] : remaining;
  try { storage.setItem(FAVORITES_KEY, JSON.stringify({ version: 1, gifts })); }
  catch { throw new Error("お気に入りを保存できませんでした。ブラウザーの保存設定や空き容量を確認してください。"); }
}
