# Giftia 商品検索の起動

Next.js の画面から FastAPI を呼び、班の開発用 MySQL の商品を検索します。ルーム作成・取得、お気に入り、個人候補入力のコードを統合しました。実ルームと個人候補入力はまだ未接続です。保存先・起動方法・未決事項は[統合の説明](docs/room-integration.md)、チームの作業ルールは [AGENTS.md](AGENTS.md) を参照してください。

作業内容・動作確認・未完了事項は [開発の作業記録](docs/work-log/README.md) に残します。ローカル保存とGitHubへの反映状況を区別して記録します。

## 必要なもの

- Node.js 20.9以上、npm
- Python 3.10以上
- 班の開発DBへの接続設定とネットワーク接続

画面の依存バージョン・APIクライアント・CSSは、手元の配布プロジェクト `giftia-frontend` から復元しました。`Gift` 型・`searchGifts`・`ResultCard` の処理と `/api/search` の契約は維持しています。

## APIを起動する

リポジトリ直下から、Windows PowerShell／macOSのどちらも以下を実行します（macOSで `python` がない場合は `python3`）。

```sh
cd backend
python -m venv .venv
```

仮想環境を有効にします。

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS：

```sh
source .venv/bin/activate
```

```sh
python -m pip install -r requirements.txt
```

DB設定は `backend/.env.example` の変数名を参照し、利用者自身が環境変数またはローカルの `.env` に設定してください。秘密情報をAIに渡さないでください。画面を `http://localhost:3000` で開く場合、`CORS_ORIGINS` にそのURLを指定します。

```sh
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

すでに別の場所に接続設定がある場合は、コピーせず次の起動オプションで利用できます。ファイルの中身を表示する必要はありません。

```sh
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --env-file "既存の設定ファイルの絶対パス"
```

Swaggerは <http://localhost:8000/docs> です。起動だけではDB接続は確認されません。`/api/search?limit=2` が200を返すことまで確認します。

## 画面を起動する

別のターミナルをリポジトリ直下で開きます。

```sh
cd frontend
npm ci
npm run dev -- --hostname 127.0.0.1
```

Windows PowerShellで `npm` の実行ポリシーエラーが出る場合は `npm.cmd` に置き換えてください。

<http://localhost:3000> を開きます。APIの接続先は既定で `http://localhost:8000` です。変更する場合は、画面起動前に `NEXT_PUBLIC_API_URL` を設定します。この変数には秘密情報を入れません。

## 確認すること

1. 「いまの検索」で検索し、商品が表示される。
2. 「取引先へのお礼」で個包装と価格帯を指定して検索する。
3. 存在しないキーワードで「条件に合う商品がありません」が出る。
4. APIを停止して検索し、「APIにつながりません：…」が出る。
5. 検索中は検索・タブ切替ボタンが無効になり、終了すると戻る。

画面の静的確認と本番ビルド：

```sh
cd frontend
npm run lint
npm run build
```

実行コードには穴埋めは残していません。接続設定がない場合はDB検索できません。ダミーの検索結果へ自動で切り替える処理はありません。
