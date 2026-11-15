# GitHub Issue作成の403を調査

確認日：2026年11月15日。ブランチ：fix/issue-8-search-starter（初期名codex/fix-search-starter）。

## 目的

既存検索の修復に対応するIssueを作成できない原因を調べ、作業記録を共有可能な場所へ残す。

## 確認した事実

- 前回のIssue作成は403、Resource not accessible by integrationで失敗した。Issueは作成されていない。
- 接続済みGitHub連携で確認できたインストール先は対象リポジトリの所有者と異なる。所有者djcook1127側のインストールは確認できなかった。
- 対象リポジトリのメタデータでは利用者のpush権限はtrue、adminはfalse。利用者自身の権限とGitHub Appに付与された権限は区別する。
- 対象リポジトリは公開であり、読み取りに成功しただけではIssue書き込み権限があるとは判定できない。

## 判断と必要な対応

インストール先と対象リポジトリの所有者の不一致が有力な原因。ただし、実際に所有者側の管理画面を確認・変更したわけではないため確定原因とはしない。

リポジトリ所有者がGitHub Appの設定で、対象リポジトリへのアクセスとIssuesの書き込み権限を確認する。インストールがなければ所有者側で追加し、必要なら連携を再接続する。対象リポジトリに必要な範囲だけを許可する。利用者が管理者でなければ所有者への依頼が必要。

設定後、既存Issueの重複を確認し、[起票用本文](2026-11-15-search-starter-issue.md)を使って正式に作成・読み戻し確認する。

## 今回残した記録

Git対象外だった既存検索の確認記録とIssue草稿をdocs/work-logに複製し、証拠画像3枚を同フォルダー配下へ保存した。以後の記録項目は[一覧](README.md)に記載。

調査時点では、連携権限の変更・再インストール・Issueの再作成・コミット・push・PRは未実施。コードは変更していない。

## CLI接続の準備

ユーザーからIssueを書き込める接続とMarkdownルールに従う指示を受け、AGENTS.md 7章のGitHub CLI経由を準備した。

- 公式GitHub CLI v2.104.0のWindows版を.local/tools/ghへ配置。システムのPATHや既存のGit認証は変更していない。
- ダウンロードしたZIPのSHA256が公式チェックサムと一致することを確認した。CLI本体はGit対象外。
- CLIには既存のログインがなかったため、ブラウザー認証を開始し、利用者にログインとアクセス許可の確認を依頼した。
- ブラウザーでの許可操作は利用者本人が実施。GitHubの完了画面とCLIの認証成功を確認した。

認証用コードや資格情報は作業記録に残さない。このCLI接続は既存のGitHub連携アプリとは別の認証経路であり、アプリ側の403が解消したとは扱わない。

## 接続とIssue作成の結果

- 認証アカウント：panapanawriter-dev。資格情報はWindowsのキーチェーン（CLI表示ではkeyring）に保存。
- 対象リポジトリのviewerPermissionはWRITE。
- gh issue listで全状態の既存Issueを確認し、修復内容の重複がないことを確認した。
- gh issue create --body-fileで[Issue #8](https://github.com/djcook1127/te_On-the-Subject-of-Free-Spirits-Learning-About-Technology/issues/8)を作成。
- タイトルに[Front]、本文に「背景・目的」「対応する文書 ID」「完了条件（Done の定義）」を記載。実装・確認済みの項目と未完了のPRレビューを分けた。
- gh issue viewで番号・本文・作成者・OPEN状態を読み戻して確認。Issueをクローズしていない。

CLIはリポジトリ直下から `.\.local\tools\gh\bin\gh.exe` として利用する。macOS等でCLIを通常導入済みの場合はghを使う。この配置はこのPCのローカル用であり、Gitには含めない。

GitHubアプリの権限設定は変更していない。今後のIssue・PR操作は、AGENTS.mdに従い認証済みのCLIを使用する。接続確認完了時点ではコード・作業記録のコミット・push・PRは未実施だった。その後の状態は[検索修復の作業記録](2026-11-15-search-starter.md)とIssue #8の関連PRを参照。
