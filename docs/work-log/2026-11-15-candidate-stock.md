# 候補ストックと手掛かり入力

Issue #10-1（#12）。ブランチ feature/issue-12-candidate-stock。開始点 origin/main 8f26937。

ユーザー了承により、B画面とローカル仮APIを追加。商品と手掛かりを最大3枠で混在させ、本人の下書きを保存する。共通MySQL、既存検索、A担当画面、共通設定は変更していない。正式提出・補填・推薦・絞り込みは未実装。

## 起動

リポジトリ直下で以下を別ターミナルで実行する。Windowsはpython、macOSで必要ならpython3を使う。

```sh
cd backend
python -m uvicorn candidate_demo:app --host 127.0.0.1 --port 8101
```

Windows PowerShell:

```powershell
cd frontend
$env:NEXT_PUBLIC_API_URL = 'http://127.0.0.1:8101'
npm.cmd run dev -- --hostname 127.0.0.1 --port 3200
```

macOS:

```sh
cd frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8101 npm run dev -- --hostname 127.0.0.1 --port 3200
```

http://127.0.0.1:3200/rooms/demo-farewell/single?member=demo-yutti と、別ブラウザーで同URLのmember=demo-takerunを開く。

## 確認結果

- `npm run lint` 成功。
- `npm run build` 成功。初回はサンドボックスのEPERMで失敗し、制限外の再実行で成功。
- backendで `python -m unittest test_candidate_demo -v`：9件成功。参加者分離、再取得、最大件数、空欄、重複、存在しない商品、別ルーム、競合保存、CORS、既存検索のパラメーターと返却形式を確認。サンドボックス内では停止したため制限外で実行。
- Edge画面で検索5件、商品追加、重複追加ボタン無効、理由入力、ヒント入力への切替を確認。
- 2つの独立ブラウザーでの保存・復元、保存失敗時の画面保持、狭い画面の確認は継続が必要。APIテスト成功をブラウザー確認済みと扱わない。

## 未完了と接続事項

仮契約は docs/b-candidate-contract.md。架空参加者の切替は認証ではなく、本番公開には使えない。A担当との正式API・参加者識別・DB追加は未合意・未適用。追加依存は不要だが、テスト実行にはhttpxが必要（今回の環境には導入済み）。

Issueの作成は成功。AGENTS.md記載のFukahoriYutaへのアサインはGitHubで解決できず失敗し、未アサイン。重複起票はしていない。PRは継続確認用のDraftとし、承認前にマージしない。
