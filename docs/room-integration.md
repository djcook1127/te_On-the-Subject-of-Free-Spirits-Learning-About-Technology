# ルーム基盤と候補入力のコード統合

## 目的と取り込み元

たけるさんのルーム作成・取得を、既存検索・お気に入り・個人候補入力を残して同じリポジトリに統合する。対象は開発用の限定試作。

- 土台：`ab363b4`（PR #13までのmain）。
- お気に入り・商品読取：`f913459`まで（PR #15・#17）。この系統のコミットは保持する。
- ルーム：`origin/takerutech0`の必要なソースのみを選択して取り込む。元の履歴、環境ファイル、PDF・プレビュー画像・一時生成スクリプトは取り込まない。
- 要求・要件：同ブランチの`docs/requirements-definition.md`と`docs/system-requirements.md`。受け取り期限・総予算のBR-05等を含む新しい版。原本Wordは今回未確認であり、チーム合意の全項目を再確認したものではない。
- 対応：BR-02・03・05、FR-01・02の一部、DR-02。既存Issue #10・#14・#16と関連する。

## 統合した内容

`main:app`に`rooms.router`を登録し、CORSでPOSTを許可。DB接続の既存読取処理を残し、ルームと幹事を一括保存する`transaction()`を追加した。SQL定義は`db/schema.sql`、共通祝日は`shared/japan-holidays.json`。

画面は`/rooms/new`（作成）と`/rooms/[roomId]`（取得・表示）。トップ検索に作成リンクを追加し、お気に入りの表示・保存・一覧・個人候補へのコピーを残した。Next.jsのTurbopack rootをリポジトリ直下にして共通祝日JSONを参照する。

## 起動と保存先

リポジトリ直下で以下を実行する。PowerShell/macOS共通（macOSで必要ならpython3）。依存関係と利用者自身の接続設定はREADMEを参照する。

```sh
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

別ターミナル：

```sh
cd frontend
npm run dev -- --hostname 127.0.0.1
```

ルームの作成は班の開発MySQLへ書き込む。利用前に管理担当者が既存の`consultations`・`consultation_members`とSQL定義を照合すること。`IF NOT EXISTS`は既存テーブルの列を更新しない。今回、共通DBへのSQL適用・実ルーム作成は実施していない。

候補入力の検証は別APIを使う。`backend`で以下を起動し、別ターミナルからフロントをポート3200で起動する。

```sh
python -m uvicorn candidate_demo:app --host 127.0.0.1 --port 8100
```

PowerShell（frontend内）：

```powershell
$env:NEXT_PUBLIC_API_URL = 'http://127.0.0.1:8100'
npm run dev -- --hostname 127.0.0.1 --port 3200
```

macOS（frontend内）：

```sh
NEXT_PUBLIC_API_URL=http://127.0.0.1:8100 npm run dev -- --hostname 127.0.0.1 --port 3200
```

候補入力は`/rooms/demo-farewell/single`。固定商品が既定で、共通商品の読取モードは`docs/shared-catalog.md`を参照。個人下書きはローカルSQLite、お気に入りはブラウザーlocalStorage。同じブラウザーでも3000と3200は保存領域が別になる。

## 未接続・未決事項

MySQLの実ルームIDと固定の架空ルームIDは統一していない。実ルーム画面から候補下書きへ接続する導線は追加していない。同じポートで`main:app`と`candidate_demo:app`を同時起動しない。

参加者ID・本人確認・招待後の参加・再訪・閲覧権限・候補保存先を#10で合意してから接続する。ヘッダーの架空参加者指定を本番の認証として流用しない。正式提出・全員公開・推薦・投票・決済は今回追加しない。

ルームの連番URLはアクセス制御ではない。現コードは参加者の権限判定を持たないため、架空情報での開発検証に限る。配送可能日を保証する機能も未実装。

## 安全性と検証

環境ファイルは読み書きせず、サンプルも既存mainの空欄版を維持。元ブランチの秘密情報の削除やパスワード変更は、このコード統合では完了しない。

今回の確認結果は[統合作業記録](work-log/2026-11-17-room-integration.md)に記載する。元ブランチの調査・テスト・MySQL保存実績は、今回実施した結果と区別する。
