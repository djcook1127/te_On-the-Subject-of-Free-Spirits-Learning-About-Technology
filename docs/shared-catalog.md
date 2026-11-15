# 共通DBの商品読取とローカル候補保存

2026-11-15。Issue #14-1（#16）。ユーザーの依頼に従い、商品検索を共通DBに接続した。DBの将来改修は今回行わない。PR #13・#15の候補入力とお気に入りを残す。

## 取得先と保存先

| 内容 | 現在の扱い |
|---|---|
| 商品検索・商品IDの確認 | 共通MySQLのproductsをREAD ONLYで取得 |
| お気に入り | ブラウザーのlocalStorage。表示情報は保存時点の控え |
| 候補・手掛かり・保存版番号 | 従来のローカルSQLite |
| ルーム・参加者 | 引き続き検証用の固定データ |

共通DBのDDL・INSERT・UPDATE・DELETEは実行しない。本人確認、共通のルーム保存先、正式提出、コンシェルジュのおすすめ順・追加の絞り込みは今回作らない。

## 起動

既存の接続設定をアプリ内部だけで利用し、設定内容は表示・複製・編集しない。Windows PowerShellでリポジトリ直下から実行する。

```powershell
cd backend
$env:GIFTIA_CATALOG_SOURCE = 'shared'
python -m uvicorn candidate_demo:app --host 127.0.0.1 --port 8101 --env-file 'C:\Users\admin\OneDrive\Desktop\step3\backend\.env'
```

設定ファイルのパスはこのPCの既存配置。別のPCではそのPCの既存設定のパスに置き換える。パスワードや接続文字列をコマンドに書かない。

別ターミナルで画面を起動する。

```powershell
cd frontend
$env:NEXT_PUBLIC_API_URL = 'http://127.0.0.1:8101'
npm.cmd run dev -- --hostname 127.0.0.1 --port 3200
```

macOSは環境変数の指定方法が異なる。設定ファイルは各自の実在する場所を指定し、pythonがなければpython3を使う。

```sh
cd backend
GIFTIA_CATALOG_SOURCE=shared python -m uvicorn candidate_demo:app --host 127.0.0.1 --port 8101 --env-file '/path/to/existing/backend/.env'
```

```sh
cd frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8101 npm run dev -- --hostname 127.0.0.1 --port 3200
```

検索画面：http://127.0.0.1:3200/

元の固定5商品のみで試すにはGIFTIA_CATALOG_SOURCE=demoを指定する。未指定時もdemo。現在このPCで動かすAPIはsharedを指定している。sharedの接続失敗時は503とし、固定商品へ自動で切り替えない。設定値の誤りも503で停止する。

## どのファイルをどう変えたか

| ファイル | 変更内容と理由 |
|---|---|
| backend/product_catalog.py（新規） | 共通商品の検索とIDによる再取得を分離。既存database.pyの接続を利用し、START TRANSACTION READ ONLY→SELECT→rollback→closeで完結する |
| backend/candidate_demo.py | 固定商品／共通商品を切替。保存する商品IDを再取得し、共通DBの商品も従来のSQLiteへ保存できるようにする |
| frontend/lib/singleApi.ts | 取得元catalogSourceと、購入可能か確認するavailableを応答型へ追加 |
| frontend/app/rooms/[roomId]/single/CandidateWorkspace.tsx | 共通DB読取中という表示、購入可能と確認できない旧候補への注意表示を追加 |
| backend/test_product_catalog.py（新規） | 読取専用SQL、在庫切れ、商品取り扱い終了、接続失敗、旧候補の保持等を実DBへ接続せず検証 |
| backend/test_candidate_demo.py | 固定商品の既存テストはdemoモードへ明示固定。shared設定のシェルから起動しても共通DBへ接続しないようにする |

既存main.py、database.py、searchGifts、Gift、ResultCard、検索トップ画面、お気に入りの保存ロジックは今回変更していない。共通MySQLのスキーマ・データも変更していない。

### 検索から保存までの流れ

```text
検索画面／ルーム内検索
  → searchGifts → /api/search
  → SharedProductCatalog → 共通DBの商品をREAD ONLYで取得

お気に入り保存
  → ブラウザー内に商品情報を保存（共通DBへは書かない）

ルームの候補に追加して保存
  → /candidate-draft に商品ID・理由・保存版番号を送る
  → 共通DBで商品を再取得し、存在と在庫を確認
  → ローカルSQLiteへ候補と表示用の商品情報を保存

下書きを再読込
  → SQLiteの本人の候補を取得
  → 共通DBの現在の商品情報を付けて返す
```

検索条件と順序は既存検索に合わせる。在庫あり、キーワード、カテゴリー、説明文の個包装一致、価格帯、販売数順と商品ID順を維持する。ユーザー入力は%sで渡す。これは既存検索の接続であり、コンシェルジュの推薦ロジック追加ではない。

ブラウザーから送られた商品名・価格は保存せず、サーバーで取得した情報を使用する。DB例外に接続先等が含まれる可能性があるため、画面へのエラーは固定の日本語文言とし、元の例外本文を返さない。

## 以前の候補と取り扱い終了

候補やお気に入りは勝手に削除しない。共通DBで見つからない候補も保存時の表示情報を使って残し、available=falseを返して注意を表示する。旧DEMO-商品の控えも表示用に使う。

存在しない商品・在庫切れ・旧架空商品を含む候補の保存は400で拒否し、既存の下書きを上書きしない。手掛かりを残し、該当する商品枠だけを画面で削除・入れ替える必要がある。

お気に入りの情報は保存時点だが、候補の保存・再読込では共通DBから取得し直す。正式購入前の価格・在庫・配送条件の確認、注文連携は未実装。今回は実注文・決済を行わない。

## 将来のDB改修

商品読取を分離したため、後で合意したデータ定義へ接続し直しやすくなる。一方、ルーム・参加者・提出・合意結果の共通保存、本人確認、権限、ブラウザーお気に入りのアカウント移行は未実装。

DB改修時はA・BでAPIとデータ定義を合意し、別の開発DBでマイグレーションを検証する。今回の読取接続完了を、DB改修やA担当との正式統合が完了したとは扱わない。
