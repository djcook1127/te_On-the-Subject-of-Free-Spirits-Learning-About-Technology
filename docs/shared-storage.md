# ルーム・共同決定の共通DB保存（2026-11-20）

対応：#22-1（[Issue #24](https://github.com/djcook1127/te_On-the-Subject-of-Free-Spirits-Learning-About-Technology/issues/24)）、Draft PR #23。DR-02・04、BR-02・03。ユーザーが共通DB保存と既存テーブルの活用を依頼したため、[共同決定仕様](shared-selection.md)の保存先を拡張する。

## 保存先

| 内容 | 共通MySQLのテーブル |
|---|---|
| ルーム | `consultations`（既存） |
| 参加者 | `consultation_members`（既存） |
| 本人照合・参加期限 | `consultation_member_sessions`（追加。Cookieのハッシュのみ） |
| 提出・比較・決定の段階と決定履歴 | `selection_state`（追加） |
| 最大5人の提出者・提出済み状態・下書きversion | `selection_submitters`（追加） |
| 商品候補・理由・商品情報の控え | `selection_proposals`（追加） |
| 好み・アレルギー等の共有情報 | `selection_notes`（追加） |
| 各人・各候補の★評価 | `selection_votes`（追加） |
| 候補への匿名コメント | `selection_comments`（追加） |
| SQLiteからのコピー済み記録・ID対応 | `selection_imports`（追加） |

商品は従来どおり`products`・`product_scenes`から読取。お気に入りは引き続き各ブラウザーのlocalStorage。共有画面には提案者・コメント投稿者・評価者の名前やIDを返さず、サーバー内部では本人IDを保持する。

既存テーブルのデータを上書きせず、新しいルーム・参加者も同じ既存テーブルへ保存する。追加DDLは[002_shared_selection.sql](../db/migrations/002_shared_selection.sql)の8テーブルのみ。既存テーブルのALTER・DROP・商品更新は含まない。API起動時にDDLは実行しない。

## 一貫性・障害時

- 作成と主催者登録、提出、評価、決定をトランザクションで処理し、失敗時はrollback。
- 同じルームの操作は、最初に親ルーム行を`SELECT ... FOR UPDATE`でロックする。最大5人・1人3品・提出段階を同時操作でも維持する。
- 評価はルーム・本人・商品で一意。更新しても同じ人の票は増えない。
- MySQL接続失敗・追加テーブル未準備は503。SQLiteへ自動的に切り替えない。
- 商品検索とルーム保存は別接続。商品情報は提出・決定時に再確認する。

## このPCで起動する（Windows PowerShell）

リポジトリ直下から実行。設定ファイルの内容は表示・変更しない。

```powershell
cd backend
$env:GIFTIA_ROOM_STORAGE = 'shared'
$env:GIFTIA_CATALOG_SOURCE = 'shared'
python -m uvicorn selection_rooms:app --host 127.0.0.1 --port 8102 --env-file 'C:\Users\admin\OneDrive\Desktop\step3\backend\.env'
```

別ターミナルでリポジトリ直下から実行。

```powershell
cd frontend
$env:NEXT_PUBLIC_API_URL = 'http://127.0.0.1:8102'
$env:NEXT_PUBLIC_SELECTION_ROOMS = '1'
npm.cmd run dev -- --hostname 127.0.0.1 --port 3300
```

入口は<http://127.0.0.1:3300/rooms/new>。デプロイ先では同じ変数とDB設定を環境変数で登録する。複数人がそれぞれAPIを起動しても共通DBの保存内容を共有できるが、相手のPCのlocalhostへはアクセスできない。全員が同じ画面を使うためのAPI・フロント公開、Cookie/CORS/HTTPSの設定は別の作業。現在の起動は自分のPC内に限定する。

## macOS

```sh
GIFTIA_ROOM_STORAGE=shared GIFTIA_CATALOG_SOURCE=shared python3 -m uvicorn selection_rooms:app --app-dir backend --host 127.0.0.1 --port 8102 --env-file '/path/to/existing/.env'
```

```sh
cd frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8102 NEXT_PUBLIC_SELECTION_ROOMS=1 npm run dev -- --hostname 127.0.0.1 --port 3300
```

SQLite検証を継続する場合は`GIFTIA_ROOM_STORAGE=sqlite`を明示する。未指定時も互換性のためsqlite。商品取得元は別変数。両モードのCookie名を分け、同じ数値IDでも本人を混同しない。

## 追加テーブルの適用

既存テーブルの列定義を事前確認し、不一致は停止する。MySQLのDDLは暗黙commitされるため8件をまとめてrollbackできない。すべて`CREATE TABLE IF NOT EXISTS`で再実行可能とし、途中失敗時も既存テーブルを削除して作り直さない。

Windows（backend内）：

```powershell
python manage_shared_storage.py --env-file 'C:\Users\admin\OneDrive\Desktop\step3\backend\.env' apply
```

macOS（backend内）：

```sh
python3 manage_shared_storage.py --env-file '/path/to/existing/.env' apply
```

適用はDB単位で一度。各メンバーがアプリを起動するたびに実行する必要はない。

## SQLiteの既存データを引き継ぐ

旧SQLite APIの書込を止めてから実行。まずSQLite Backup APIで`元ファイルのフォルダー/backups/`へ整合したコピーを作り、それを読取専用で使用する。元SQLiteは削除・更新しない。バックアップと設定ファイルはGitへ入れない。

Windows（backend内）：

```powershell
python manage_shared_storage.py --env-file 'C:\Users\admin\OneDrive\Desktop\step3\backend\.env' import-sqlite --source '..\.local\selection-preview.sqlite3'
```

macOS（backend内）：

```sh
python3 manage_shared_storage.py --env-file '/path/to/existing/.env' import-sqlite --source '../.local/selection-preview.sqlite3'
```

ルーム・参加者にはMySQL側の新IDを割り当て、候補・メモ・評価・コメント・決定内容と本人照合情報の参照先を対応させる。ファイルパスのハッシュと旧ルームIDでコピー済みを記録。同じ元ファイル・同じルームを再実行しても重複を作らず、コピー後のSQLite編集を再同期する処理は行わない。コピー全体は1トランザクションで、失敗時は追加データを取り消す。

同じブラウザーに旧Cookieが残っていれば、参加画面の「以前のルームを引き継ぐ」を選ぶか、旧URLの末尾に`?legacy=1`を付けると、`POST /api/rooms/{旧ID}/migrate-session`で本人を確認し、新しいルームURLへ移動する。Cookie値はJavaScriptへ渡さず、共通DBにはハッシュだけを保存。番号が重なる新しい招待URLを勝手に旧ルームへ転送しない。有効な共通DBの本人Cookieが既にある場合はそちらを優先する。新URLを控えること。

Cookie削除・期限切れ・別端末での本人復元は未実装。SQLiteの旧`/single`用`local_candidate_drafts`は元ファイルに保持し、新しい正式提出へ自動変換しない。

## 検証

通常のテストは共通DBへ接続しない。実MySQLテストは`GIFTIA_RUN_SHARED_TESTS=1`を明示した場合だけ実行し、作成した架空ルームのIDを記録してそのルームだけ後片付けする。既存のルーム・商品は変更しない。結果と適用・引継ぎの実績は[作業記録](work-log/2026-11-20-shared-storage.md)に記載する。
