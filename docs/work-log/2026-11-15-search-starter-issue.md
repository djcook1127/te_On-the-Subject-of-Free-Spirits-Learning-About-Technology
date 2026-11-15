# [Front] 既存検索の穴埋めを完了し起動に必要なファイルを揃える

2026年11月15日：CLI認証後に[Issue #8](https://github.com/djcook1127/te_On-the-Subject-of-Free-Spirits-Learning-About-Technology/issues/8)として作成済み。以下は起票前の草稿であり、実際のIssueの本文と区別する。

GitHubへの起票は接続済みツールで403（Resource not accessible by integration）となり未実施。GitHub CLIも未導入。ユーザーが指示した既存検索の修復をローカルの codex/fix-search-starter で実施し、コミット・pushはしない。

## 背景・目的

開発に入る前提として既存検索を動作可能にする。画面の初期値とAPI呼び出しの穴埋め、不足するNext.jsの起動ファイルを修復する。

## 対応する文書 ID

AGENTS.md 3・6・8章の既存検索維持。要件定義書V2 7章のStarter構成。新機能のFRは追加しない。

## 完了条件

- 実行コードに穴埋めがない。
- 既存の検索条件・商品型・カードを維持する。
- ビルド・静的検査・API・画面を確認し、実DBの確認結果を明記する。
- 秘密情報を変更・コミットしない。
