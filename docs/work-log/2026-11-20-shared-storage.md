# 共同決定の共通DB保存（2026-11-20）

## 依頼と範囲

#22-1（[Issue #24](https://github.com/djcook1127/te_On-the-Subject-of-Free-Spirits-Learning-About-Technology/issues/24)）。ユーザーが、既存のルーム・参加者テーブルを活用して提案・投票・コメント・決定履歴を共通DBへ保存するよう依頼。DR-02・04、BR-02・03。[共通DB保存仕様](../shared-storage.md)へ整理。

作業ブランチは既存の`feature/issue-22-shared-selection`、開始コミット`8c22c95`。既存Draft PR #23へ追加する。開始前から未追跡の`frontend/AGENTS.md`は変更・コミットしない。

## 変更

- `shared_rooms.py`：既存consultations・consultation_membersを使う作成・参加・本人照合。ルーム行をFOR UPDATEでロックし、主催者・所属を判定。旧Cookieから移行済みルームの本人を引き継ぐAPI。
- `selection_store.py`：MySQLとSQLiteのパラメーター・upsert差分を分離。値はSQLへ連結しない。
- `selection_rooms.py`：`GIFTIA_ROOM_STORAGE=shared`でルームと共同決定をMySQLへ保存。SQLiteは従来モードとして維持。MySQL障害時の自動フォールバックなし。
- `002_shared_selection.sql`：必要な8テーブルだけを追加。既存のルーム・参加者・商品テーブルのALTER・DROP・商品更新なし。
- `manage_shared_storage.py`：追加DDLの事前確認・適用・定義確認。SQLiteの整合バックアップ・読取専用コピー・新ID割当・対応記録・二重移行防止。
- フロント：共通保存先を表示し、作成時のCookieと旧ルーム引継ぎを接続。お気に入りは従来どおりブラウザー保存。

## 実行した確認

| 確認 | 結果 |
|---|---|
| 通常API・ストアテスト | 61件成功。実MySQL用14件は通常実行ではskip |
| フロント既存テスト | 13件成功 |
| lint・本番ビルド | TypeScriptを含め成功 |
| 共通DBの追加DDL | 8テーブル作成・列定義確認が成功 |

追加済み：consultation_member_sessions、selection_state、selection_submitters、selection_proposals、selection_notes、selection_votes、selection_comments、selection_imports。設定ファイルの内容は表示・変更していない。

バックアップの初回テストでWindowsのファイルロックが発生。sqlite3のwithだけでは接続が閉じないため、実装のバックアップ・読取側をcontextlib.closingへ修正し、テストも同じ実接続の解放を確認して成功。期待値を書き換えて回避していない。

実MySQL検証・既存データ引継ぎ・API切替・ブラウザー確認の結果は以下のとおり。

### 適用・既存データ引継ぎ・起動切替

- `manage_shared_storage.py ... apply`で追加8テーブルの作成と列定義確認が成功。
- 旧SQLite APIを停止し、`import-sqlite --source ../.local/selection-preview.sqlite3`を実行。整合バックアップを作成後、元ファイルを変更せず共通DBへコピー。
- 旧ルーム1→共通DBの16、旧ルーム2→17へ割当。候補・提出者・共有情報・評価・コメントの引継ぎ前後の件数一致を確認。参加者・本人照合・決定内容も対応する新ルームへ保存。
- APIを`GIFTIA_ROOM_STORAGE=shared`・`GIFTIA_CATALOG_SOURCE=shared`で8102番へ再起動。SQLiteへの自動フォールバックはしない。
- 同じブラウザーで旧ルームの「以前のルームを引き継ぐ」（`/rooms/2/select?legacy=1`）を選び、新`/rooms/17/select`へ移動。主催者として復元し、共有情報と決定済みカタログの商品、共通DB保存のフッター表示を確認。
- 旧番号と共通DBの番号が衝突する場合に備え、通常の招待URLでは引継ぎを自動実行しない。通常`/rooms/2/select`では参加画面のまま、引継ぎを選んだときだけ17へ移ることを最終ブラウザー確認で検証。
- [画面の証拠](evidence/2026-11-20-selection/shared-storage.png)。新しい確認先は<http://127.0.0.1:3300/rooms/17/select>。

### 実MySQLテスト

`GIFTIA_RUN_SHARED_TESTS=1`を明示して実行し、14件すべて成功（869.628秒）。最大5人・1人3品・全体15品、匿名性、評価更新・並列操作、単品／カタログ決定、失敗時保持、決定後変更拒否、SQLiteのID付替・二重移行防止・旧Cookie照合を確認。架空商品とテスト用ルームを使用し、作成したテストルームだけを後片付け。既存ルームや商品をテストで削除・変更していない。

## 範囲・残課題

実決済・実配送・外部公開・別端末からの本人復元・お気に入りの共通化は今回の対象外。SQLiteの旧`/single`下書きは元ファイルに保持し、新しい正式提出へ自動変換しない。カタログはプレビューまで。顧客効果の調査は未実施。

コミット・push・PR更新・マージ状況は実施後に追記。レビュー前にマージしない。
