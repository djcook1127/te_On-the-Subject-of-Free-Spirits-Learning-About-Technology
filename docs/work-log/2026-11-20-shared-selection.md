# 提案・匿名評価・共同決定（2026-11-20）

## 目的と対応

[Issue #22](https://github.com/djcook1127/te_On-the-Subject-of-Free-Spirits-Learning-About-Technology/issues/22)。BR-02・03、FR-02・08・09・14・15・16、DR-04。[追加仕様](../shared-selection.md)に今回のユーザー合意・実装範囲・未解決事項を記録。顧客効果は未検証。

ブランチ：`feature/issue-22-shared-selection`。開始：`b72a3af`（fetch後のorigin/main）。開始前から未追跡の`frontend/AGENTS.md`は変更対象に含めない。

GitHub連携での起票は403で失敗し、ブラウザーからIssue作成・番号・本文を確認。[起票証拠](evidence/2026-11-20-selection/issue-22-created.png)。途中で過去の記録からローカルGitHub CLIの配置が判明。

## 実装

- `backend/selection_rooms.py`：共通商品の読取、提出者指定、下書き競合検出・正式提出・全員提出後の公開、匿名評価・コメント・共有情報、単品／カタログ決定・保存。ルーム情報は専用SQLite。共通DBのDDL・書込なし。
- `backend/test_selection_rooms.py`：権限・上限・匿名性・状態遷移・失敗時保持・SQLパラメーター・並列評価・決定後の更新拒否。
- `frontend/lib/selection.ts`と`app/rooms/[roomId]/select/`：共有情報を上部に表示し、提案・比較・集計を接続。検索／お気に入り／おまかせ、匿名の★1〜3とコメント、デモ購入確認・決定履歴。
- ルームページ：`NEXT_PUBLIC_SELECTION_ROOMS=1`で新画面への導線。従来モードは維持。

## 確認

| 確認 | 結果 |
|---|---|
| `python -m unittest discover -p 'test_*.py' -v` | 53件すべて成功。共同決定の新規12件を含む。架空商品・一時SQLite、共通DBへ書込なし |
| `npm.cmd run lint` | 成功。表示調整後も再確認 |
| `npm.cmd run build` | TypeScript含め成功。表示調整後の最終結果は追記欄に記録 |
| 共通DBの表・列 | 商品とシーンの表・列名を読取確認。設定内容は表示せず、DDL・書込なし |
| ブラウザー | 作成→提出者指定→共有情報→予算6,000円以内の送別おまかせ3品→シャッフル→3品追加→理由入力→提出→比較→★変更→匿名コメント→カタログ選択→デモ購入確認→決定保存→再読込で履歴復元を確認 |
| 390px幅 | 決定画面を確認。viewport390／document幅375、横にはみ出しなし |

最初のテスト停止はWindowsのasyncio内部socketpairを作る段階での環境制限。トレースで特定し制限外で成功。最初のビルドは既存`.next`キャッシュのrmdirでEPERMとなり、制限外で成功。期待値を変えてテストを通していない。

画面の余白・入力欄の不足を修正して再確認。ブラウザーは主催者1人を提出者にする確認。最大5人・閲覧者の評価・別ルーム拒否・並列操作はAPIテストで確認し、複数ブラウザー同時操作を実施済みとは扱わない。検索・お気に入りからの追加は今回ブラウザーで別途操作していない。

証拠：[比較画面](evidence/2026-11-20-selection/selection-compare.png)、[決定履歴](evidence/2026-11-20-selection/selection-decision.png)、[390px幅](evidence/2026-11-20-selection/selection-mobile.png)。

## 残課題・反映状況

実決済・実配送・受取人の実選択受付・外部公開・保存先の共通DB移行は未実施。カタログはプレビューまで。各人が別APIを起動するとルーム情報は共有されない。アレルギー等の適合保証は行わない。詳細は追加仕様を参照。

コミット・push・PR・マージ状況と最終確認は、実施後に以下へ追記する。レビュー前にマージしない。

### 最終確認

表示調整後の`npm.cmd run lint`、`npm.cmd run build`（TypeScriptを含む）は成功。既存のフロントテスト`node --test tests/localParticipation.test.mjs tests/farewellFavorites.test.mjs`も13件すべて成功。NodeのMODULE_TYPELESS_PACKAGE_JSON警告は既存の設定に由来し、今回の作業では変更していない。

### GitHub反映

実装コミット`b6b4566`を作業ブランチへpush済み。[Draft PR #23](https://github.com/djcook1127/te_On-the-Subject-of-Free-Spirits-Learning-About-Technology/pull/23)を作成。レビュー・Approve・マージは未実施。本記録の反映状況追記は後続の文書コミットに保存する。
