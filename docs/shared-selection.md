# 提案から共同決定まで（2026-11-20 合意仕様）

**共通DB保存への更新**：[共通DB保存の仕様・起動・引継ぎ手順](shared-storage.md)を追加。`GIFTIA_ROOM_STORAGE=shared`で既存のルーム・参加者と追加の候補・評価・コメント・決定を共通MySQLへ保存する。以下のSQLiteの記述・起動方法は従来の検証モードとして残す。現在の共通DB用起動方法は追加手順を参照。

[Issue #22](https://github.com/djcook1127/te_On-the-Subject-of-Free-Spirits-Learning-About-Technology/issues/22)。対応：BR-02・03、FR-02・08・09・14・15・16、DR-04。今回のユーザー合意を記録した追加仕様。この範囲では古い未決・対象外記述より優先する。別管理の原本文書は未更新。顧客効果の検証は未実施。

## 仕様と流れ

1. `/rooms/new`でルームを作成。参加者はニックネームで参加。
2. 主催者が参加済みのメンバーから提出者を最大5人指定。主催者も提出する場合は5人に含める。先着順ではない。
3. 検索・このブラウザーのお気に入り・おまかせを合わせて、1人1〜3品を提出。全体は最大15品。共有時は同じ商品IDを1候補にまとめる。
4. 全提出者が提出するまでは候補を本人だけに表示。全員そろうと比較・投票へ。
5. 全参加者が各商品に★1〜3とコメントを付ける。★は更新可能、同じ人の票は加算しない。未評価は未評価のまま。候補は★合計順に表示。
6. 主催者が集計画面で「1品を贈る／カタログにして贈る」を選択。カタログは候補から受取人が1品選ぶ方式であり、全品購入ではない。各商品の価格が総予算以内か確認する。
7. デモの購入確認後、決定内容を保存。同じルームURLから「このルームでの決定商品」を見返せる。

投票・コメント・共有メモ・共有候補には投稿者名を表示しない。共有APIの候補・コメント・メモに投稿者IDを返さない。主催者は提出者指定のため参加者名一覧を閲覧できる。匿名は参加者への表示上の匿名であり、サーバー内部では権限と重複評価防止のため本人IDを保持。本文中の名前まで自動匿名化する機能ではない。

## 共有情報とおまかせ

- 全員が好み・アレルギーや避けたいもの・その他を匿名入力し、画面上部に共有。商品3品の枠は消費しない。本人談か推測かも文章に添える。実名・連絡先・健康情報の詳細を入力しない案内を表示。
- おまかせは`product_scenes.scene_tag = '送別'`・在庫あり・商品価格が総予算以内の共通商品から`ORDER BY RAND() LIMIT 3`で取得。自分の入力済み商品を除外し、1回の表示内で重複させない。SQLの値はパラメーターで渡す。
- シャッフルは表示候補の再抽出。追加済み下書きや他人の候補、票は置き換えない。母集団が少ないと同じ商品が再表示され得る。0〜2品でも条件外の商品で埋めない。
- 好み・アレルギー・お届け期限への適合は未確認。自動除外・安全保証・手掛かりによるAI推薦は今回行わない。
- 検索・お気に入りの予算超過は画面に明示し、最終決定では拒否。提出時に存在・在庫を再確認し、決定時には最新価格と在庫を再確認する。

## 変更・決定の扱い

- 下書きと正式提出を分ける。versionで古いタブからの上書きを拒否し、失敗時も編集中の入力を残す。
- 下書きがある提出者は外せない。本人が商品を空にして保存してから指定変更する。
- 最初の正式提出後は提出者を変更不可。提出済み候補も変更不可。
- 全員提出前は評価・商品コメント・決定不可。決定後は共有メモ・候補・評価・コメント・決定の再変更不可。
- 同点や未評価から自動で勝者を選ばず、主催者がコメント等を確認して確定。★合計を全員の同意とみなさない。
- 決定時の商品情報を履歴として保存。将来の価格・在庫は保証しない。
- 受取人用カタログは価格・提案者名なしのプレビューまで。実選択受付・購入・決済・配送は行わない。

## 起動：このPCのWindows PowerShell

リポジトリ直下から実行。設定の中身を表示・複製・編集せず、既存ファイルをアプリ内部で利用する。ルーム情報の保存先は従来の検証データと別にする。

```powershell
$repoPath = (Get-Location).Path
$env:GIFTIA_CATALOG_SOURCE = 'shared'
$env:GIFTIA_LOCAL_ROOMS_DB = Join-Path $repoPath '.local\selection-preview.sqlite3'
cd backend
python -m uvicorn selection_rooms:app --host 127.0.0.1 --port 8102 --env-file 'C:\Users\admin\OneDrive\Desktop\step3\backend\.env'
```

別ターミナルでリポジトリ直下から実行。

```powershell
cd frontend
$env:NEXT_PUBLIC_API_URL = 'http://127.0.0.1:8102'
$env:NEXT_PUBLIC_LOCAL_ROOMS = '1'
$env:NEXT_PUBLIC_SELECTION_ROOMS = '1'
npm.cmd run dev -- --hostname 127.0.0.1 --port 3300
```

入口：<http://127.0.0.1:3300/rooms/new>。画面：`/rooms/[roomId]/select`。Cookie・お気に入りの保存領域をそろえるため、localhostと127.0.0.1を混ぜない。

## 起動：macOS

依存関係はREADMEの手順で導入し、既存設定のパスを各自のものに置き換える。

```sh
GIFTIA_LOCAL_ROOMS_DB="$PWD/.local/selection-preview.sqlite3" GIFTIA_CATALOG_SOURCE=shared python3 -m uvicorn selection_rooms:app --app-dir backend --host 127.0.0.1 --port 8102 --env-file '/path/to/existing/.env'
```

```sh
cd frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8102 NEXT_PUBLIC_LOCAL_ROOMS=1 NEXT_PUBLIC_SELECTION_ROOMS=1 npm run dev -- --hostname 127.0.0.1 --port 3300
```

架空商品での検証は`GIFTIA_CATALOG_SOURCE=demo`とし、`--env-file`を省略する。共有DB障害時に架空商品へ自動切替しない。

## APIと保存

既存`local_rooms.py`の作成・参加・本人Cookieを利用。共同決定APIは`selection_rooms.py`に分離し、従来の実行モードは変更しない。SQLiteの追加テーブルは`selection_*`。書込はトランザクションで処理し、ルーム所属・主催者・段階・上限をAPIで判定する。商品DBのDDL・書込は行わない。

| `/api/rooms/{room_id}/selection`以下 | 操作 |
|---|---|
| GET（ルート） | 本人・権限・提出状況・自分の下書き・共有情報・公開後候補・集計・決定 |
| PUT /submitters | 最大5人を指定 |
| PUT /proposal | version付き下書きを最大3品保存 |
| POST /submit | 正式提出。全員提出で比較へ |
| GET /random | 送別・在庫・予算で抽出。excludeで選択済み商品を除外 |
| POST /notes | 共有情報を追加 |
| PUT /products/{product_id}/vote | 自分の★1〜3を保存・更新 |
| POST /products/{product_id}/comments | 匿名コメント |
| POST /decision | 主催者が単品／カタログ決定を保存 |

## 運用の範囲・未解決事項

- 1台のAPIでのローカル実装。各人が別API・SQLiteを起動するとルーム情報は共有されない。複数端末用のホスティング・CORS・Cookie設定・保存先移行は別途必要。
- 本人Cookieの削除・期限切れ・別端末での復元は未実装。公開用認証基盤ではない。
- 他人の変更は「状況を更新」で取得。通知・自動更新・主催者交代・未提出者の締切処理は未実装。
- お気に入りはこのブラウザーの既存保存。別端末同期は未実装。
- 旧`/single`の下書きは従来どおり残し、新しい正式提出へ黙って移行・削除しない。
