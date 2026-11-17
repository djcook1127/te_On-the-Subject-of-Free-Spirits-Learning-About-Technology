import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { getLocalMember, joinLocalRoom } from '../lib/localParticipation.ts';
import { loadCandidateDraft, saveCandidateDraft } from '../lib/singleApi.ts';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

test('未参加だけをnullとして扱い、接続失敗を参加済みにしない', async () => {
  globalThis.fetch = async () => new Response('{}', { status: 401 });
  assert.equal(await getLocalMember('1'), null);
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: '保存先を利用できません' }), { status: 503 });
  await assert.rejects(getLocalMember('1'), /保存先を利用できません/);
});

test('名前参加はCookieを利用し、参加者IDやトークンを送信本文へ入れない', async () => {
  globalThis.fetch = async (url, options) => {
    assert.ok(url.endsWith('/api/rooms/1/members'));
    assert.equal(options.credentials, 'include');
    assert.deepEqual(JSON.parse(options.body), { nickname: '参加者B' });
    return new Response(JSON.stringify({ id: '2', name: '参加者B' }));
  };
  assert.deepEqual(await joinLocalRoom('1', '参加者B'), { id: '2', name: '参加者B' });
});

test('ローカル候補入力は架空参加者ヘッダーを使わずCookieで本人を確認する', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(options.credentials, 'include');
    assert.equal(options.headers['X-Demo-Member'], undefined);
    return new Response(JSON.stringify({ slots: [] }));
  };
  await loadCandidateDraft('1', '偽の参加者ID', true);
  await saveCandidateDraft('1', '偽の参加者ID', 0, [], true);
});

test('既存の架空参加者デモは従来のヘッダー契約を維持する', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(options.headers['X-Demo-Member'], 'demo-yutti');
    assert.equal(options.credentials, undefined);
    return new Response(JSON.stringify({ slots: [] }));
  };
  await loadCandidateDraft('demo-farewell', 'demo-yutti');
});

test('保存競合はエラーとして伝え、表示用の商品情報を送信しない', async () => {
  globalThis.fetch = async (url, options) => {
    assert.deepEqual(JSON.parse(options.body), { version: 1, slots: [{ kind: 'product', productId: 'DEMO-001', reason: '理由' }] });
    return new Response(JSON.stringify({ detail: '別の画面で保存されています' }), { status: 409 });
  };
  await assert.rejects(saveCandidateDraft('1', '', 1, [{ kind: 'product', productId: 'DEMO-001', reason: '理由', gift: { price: 1 } }], true), /別の画面で保存/);
});
