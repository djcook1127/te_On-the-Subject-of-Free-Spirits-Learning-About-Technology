# ローカル版：名前参加から個人候補入力まで

## 目的・承認された範囲

Issue #21。ユーザーが本チャットで「名前での参加から、商品候補・手掛かりの入力まで両方」「このローカル検証仕様で進める」と確認した範囲。

たけるさんのルーム入力規則と、既存の最大3枠の商品・手掛かり入力を接続し、本人別に保存して再表示する。顧客が納得して購入を決められるかの効果検証は未実施。共通MySQLのルームへの接続・書込、別端末からの本人復元、正式提出・全員共有・推薦・投票・決済は対象外。

## 起動

リポジトリ直下で実行（Windows/macOS共通。必要ならpython3）：

```sh
python -m uvicorn local_rooms:app --app-dir backend --host 127.0.0.1 --port 8300
```

別ターミナルでfrontendに移動する。

PowerShell：

```powershell
cd frontend
$env:NEXT_PUBLIC_API_URL = 'http://127.0.0.1:8300'
$env:NEXT_PUBLIC_LOCAL_ROOMS = '1'
npm run dev -- --hostname 127.0.0.1 --port 3300
```

macOS：

```sh
cd frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8300 NEXT_PUBLIC_LOCAL_ROOMS=1 npm run dev -- --hostname 127.0.0.1 --port 3300
```

画面：<http://127.0.0.1:3300/rooms/new>。二つのサーバーは起動したまま使う。既存のMySQL版`main:app`や固定参加者版`candidate_demo:app`と同じポートで起動しない。

本番ビルドをローカル確認する場合も、build時に上記二つの公開設定を指定し、その後`npm run start -- --hostname 127.0.0.1 --port 3300`を使う。これらの設定値に秘密情報を入れない。

## 試せる操作

1. 架空のルーム名・幹事名、総予算、予定人数、平日の受け取り期限でルームを作成する。作成者もその場で参加済みになる。
2. 「自分の候補・手掛かりを入力する」から、商品検索・お気に入りのコピー・手掛かり入力を最大3枠まで行い、保存する。
3. 再読み込みして自分の下書きが残ることを確認する。ルームへ戻っても同じ名前で再訪できる。
4. 別ブラウザーまたはプライベートウィンドウで同じルームURLを開き、別の架空名で参加する。別タブは同じ本人として扱う。
5. それぞれに別の候補・手掛かりを保存し、互いの下書きが表示されないことを確認する。

このURLは同じPC内用で、他のPCへ共有しても使えない。127.0.0.1とlocalhostはCookie・お気に入りの保存領域が異なるため、確認中は同じURLを使う。

## 保存・識別の契約

- 商品は固定の架空5商品。共通DBの接続設定は読まない。MySQLへ接続せず、`db/schema.sql`も適用しない。
- 保存先は`.local/room-preview.sqlite3`。既存のローカルルームは削除せず利用する。テストは環境変数`GIFTIA_LOCAL_ROOMS_DB`で一時ファイルに切り替える。
- 名前は前後空白を除いた1〜30文字。同じルームの同じ名前は409で拒否する。別ルームでは同名を使える。名前を知っているだけでは既存参加者として再訪できない。
- 予定人数は予算計算に使う。参加済み人数とは区別し、参加人数の上限や全員提出の判定には使わない。
- ルーム作成者を含め、参加時にブラウザーへルーム別のHttpOnly・SameSite=Strict Cookieを設定する。識別値はURLやJSONへ返さず、SQLiteにはSHA-256ハッシュだけを保存。有効期間は30日。
- ローカルHTTPでの確認なのでCookieのSecure属性は付けない。本番用の認証方式ではなく、架空情報での検証に限る。127.0.0.1へだけバインドし公開しない。
- Cookieを失った場合の本人復元・名前変更・別人への切替・別端末引継ぎは追加しない。別名での参加または新規ルームで確認する。
- 以前の画面デモで作ったルームには参加Cookieがない。以前の幹事名を入力しても本人復元はできないため、新規ルームの作成から確認することを推奨する。
- Cookieの有効性と対象ルームをサーバーで確認し、参加者IDやデモ用ヘッダーの自己申告は利用しない。他人の下書きや参加者一覧は返さない。
- 1人最大3枠、商品重複不可、手掛かりは空欄不可、理由は任意・100文字以内。下書きversionが古い保存は409で拒否し、編集中の内容を画面に残す。保存は正式提出を意味しない。
- 商品検索・お気に入りは従来の関数・型を維持。お気に入りはルームとは独立したブラウザーlocalStorageで、参加者アカウントごとの保存や同期ではない。

## API

| API | 内容 |
| --- | --- |
| POST /api/rooms | ローカルルームと幹事を同時保存、本人Cookie設定 |
| GET /api/rooms/{roomId} | ルーム概要。local_preview=trueを返す |
| POST /api/rooms/{roomId}/members | 名前で参加。Cookieを持つ同じ本人の同名再送は200、別名変更・名前重複は409 |
| GET /api/rooms/{roomId}/me | Cookieから本人のid/nameを取得。未参加・無効・期限切れは401 |
| GET /api/rooms/{roomId}/candidate-draft | 本人だけの下書きを取得 |
| PUT /api/rooms/{roomId}/candidate-draft | versionとslotsを確認して本人分だけ保存 |
| GET /api/search | 架空商品の既存形式での検索 |

上記は`local_rooms:app`専用で、MySQL版には登録しない。フロントはローカルAPIが返すlocal_preview=trueのルームにだけ参加欄を表示する。フロント起動時のNEXT_PUBLIC_LOCAL_ROOMS=1で、数値ルームの個人入力をCookie方式にする。固定参加者の旧デモは従来のヘッダー方式を維持する。

## 脆弱性修正

Next.jsとeslint-config-nextを16.4.2から16.4.6へ固定更新。`npm audit fix`で互換範囲の開発依存も更新し、検出0件を確認した。これは今回の依存監査結果であり、アプリ全体の安全性を保証するものではない。

元のNext.jsの検出は、use cacheとunstable_cacheの組み合わせによるルートパラメーター間のキャッシュ情報漏えい（GHSA-mfr8-8qww-v76h）。minimatchの処理増幅によるDoSが開発依存へ波及した検出もあった。公式情報：

- <https://github.com/vercel/next.js/security/advisories/GHSA-mfr8-8qww-v76h>
- <https://github.com/advisories/GHSA-g3hv-75wg-m249>

今回のテスト結果・画面操作・スクリーンショットは[検証記録](work-log/2026-11-18-local-participation.md)に記載する。
