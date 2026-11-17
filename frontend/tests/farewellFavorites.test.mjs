import assert from "node:assert/strict";
import test from "node:test";
import { decodeFavorites, FAVORITES_KEY, updateFavorite } from "../lib/farewellFavoritesStore.ts";

const gift = { id: "DUMMY-1", category: "食品", brand: "架空", name: "架空の珈琲", price: 2400, rating: 4.1, reviewCount: 3 };
function store() {
  const values = new Map();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
}

test("ルームがなくても保存でき、再取得できる", () => {
  const storage = store();
  updateFavorite(storage, gift, true);
  assert.deepEqual(decodeFavorites(storage.getItem(FAVORITES_KEY)), { gifts: [gift], error: "" });
});
test("同じ商品の再保存は重複せず、表示情報を更新する", () => {
  const storage = store();
  updateFavorite(storage, gift, true);
  updateFavorite(storage, { ...gift, price: 2500 }, true);
  assert.equal(decodeFavorites(storage.getItem(FAVORITES_KEY)).gifts.length, 1);
  assert.equal(decodeFavorites(storage.getItem(FAVORITES_KEY)).gifts[0].price, 2500);
});
test("お気に入りはルームの3枠とは別で、4商品以上を集められる", () => {
  const storage = store();
  for (let i = 0; i < 5; i++) updateFavorite(storage, { ...gift, id: `DUMMY-${i}` }, true);
  assert.equal(decodeFavorites(storage.getItem(FAVORITES_KEY)).gifts.length, 5);
});
test("解除で他の商品を消さず、コピー済みの商品オブジェクトも変えない", () => {
  const storage = store();
  updateFavorite(storage, gift, true);
  updateFavorite(storage, { ...gift, id: "DUMMY-2" }, true);
  const copied = decodeFavorites(storage.getItem(FAVORITES_KEY)).gifts[0];
  updateFavorite(storage, gift, false);
  assert.equal(copied.id, gift.id);
  assert.deepEqual(decodeFavorites(storage.getItem(FAVORITES_KEY)).gifts.map(item => item.id), ["DUMMY-2"]);
});
test("既存の保存内容を読み直して追加し、別画面の先行保存を保持する", () => {
  const storage = store();
  updateFavorite(storage, gift, true);
  updateFavorite(storage, { ...gift, id: "DUMMY-2" }, true);
  updateFavorite(storage, { ...gift, id: "DUMMY-3" }, true);
  assert.equal(decodeFavorites(storage.getItem(FAVORITES_KEY)).gifts.length, 3);
});
test("不正な保存データを黙って上書きしない", () => {
  for (const raw of ["broken", "null", '{"version":2,"gifts":[]}', '{"version":1,"gifts":[{}]}', JSON.stringify({ version: 1, gifts: [gift, gift] })]) {
    const storage = store();
    storage.setItem(FAVORITES_KEY, raw);
    assert.ok(decodeFavorites(raw).error);
    assert.throws(() => updateFavorite(storage, gift, true));
    assert.equal(storage.getItem(FAVORITES_KEY), raw);
  }
});
test("容量不足や読み取り拒否を成功扱いしない", () => {
  const full = { getItem: () => null, setItem: () => { throw new Error("QuotaExceededError"); } };
  assert.throws(() => updateFavorite(full, gift, true), /保存できませんでした/);
  const denied = { getItem: () => { throw new Error("SecurityError"); }, setItem: () => assert.fail() };
  assert.throws(() => updateFavorite(denied, gift, true), /読み取れません/);
});
test("壊れた商品を保存しない", () => {
  const storage = store();
  for (const value of [{ ...gift, id: "" }, { ...gift, price: NaN }, { ...gift, price: -1 }]) {
    assert.throws(() => updateFavorite(storage, value, true));
  }
  assert.equal(storage.getItem(FAVORITES_KEY), null);
});
