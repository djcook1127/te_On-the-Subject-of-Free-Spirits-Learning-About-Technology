# 共同決定ルームのAzureリリース準備

共同決定では、画面をApp Service、APIをAzure Functions、保存先を班の共通MySQLにする。画面は自分と同じHTTPSオリジンの `/api` にリクエストし、Next.jsの書き換え設定でFunctionsに転送する。

## 招待リンク

- 主催者はルーム入口でリンクを発行・再発行・無効化できる。有効期限は発行から7日。受信者はリンク先で名前を入力し、参加後にCookieを受け取る。
- ルーム番号だけで開くと、共通MySQLモードではルーム情報を閲覧できない。参加済みのCookieがなければ、参加登録にはそのルームの有効な招待が必要。
- リンクを受け取った人が転送すると転送先も参加できる。無効化・再発行は未参加者の招待に効く。登録済み参加者のCookieは引き続き有効。
- 既存ルームも同じ制約になる。既存の主催者Cookieがあればリンクを新規発行できる。Cookieを失った場合の主催者復元は別途検討する。

## リリースするときの順番

1. **DBの準備**。担当者が接続先を確認し、既存の002〜005が適用済みであることを確かめた後、`backend/` で `python manage_shared_storage.py --env-file <既存の設定ファイル> apply-invites` を実行する。006は招待テーブルを追加する。アプリ起動時にDDLは実行しない。
2. **APIの成果物を作る**。リポジトリ直下で `python backend/package_function.py <出力先>/giftia-api.zip` を実行する。ZIP直下に `function_app.py`・`host.json`・`requirements.txt` が入り、祝日データも含まれる。Functions Flexにはこの成果物をリモートビルド付きでデプロイする。
3. **Functionsの環境変数を設定する**。DBの資格情報はAzureの環境変数に入れる。 `CORS_ORIGINS` には実際の画面のHTTPSオリジンを指定する。Functionsは共同決定APIを共通MySQLモードで起動し、HTTPS専用のCookieを発行する。 `/api/health` で商品テーブルと招待テーブルの読み取りを確認する。
4. **画面をビルドする**。App Serviceの画面ビルドで `GIFTIA_API_UPSTREAM` にFunctionsのHTTPSオリジンを設定する。ビルドはリポジトリ内の `shared/` を参照できる状態で行う。Next.jsがブラウザー向けの接続先を同じオリジンに設定する。APIのオリジンを変えたときは画面を再ビルドする。
5. **ブラウザーを2つ使って確認する**。主催者が作成 → 招待発行 → 参加者が登録 → 投票 → 決定まで確認する。番号だけのアクセス、期限切れ・無効化、参加者によるリンク発行も確認する。検索だけではCookieや書き込みの確認はできない。

## 講義手順書 1.3 の確認

| 手順書のファイル | この班の構成 |
|---|---|
| `backend/function_app.py` | ASGIの入口から `selection_rooms:app` を呼ぶ。共同決定、共通MySQLの商品検索、`/api/health` を用意する |
| `backend/host.json` | Functionsのルート接頭辞を空にし、FastAPIの `/api/...` をそのまま使う |
| `backend/.funcignore` | ローカル設定やテストを除外する。ZIP作成コマンドも必要なファイルを明示指定する |
| `backend/requirements.txt` | Functionsの入口が使用する `azure-functions` を含む |

ローカルの共同決定APIは、従来どおり `selection_rooms:app` をUvicornで起動できる。Functions用ZIPは `backend/` をそのまま圧縮する代わりに、上記の専用コマンドで作成する。リポジトリ直下にある祝日データをZIP内の `shared/` に含めるため。1.3のレビューとマージが済んだら、APIの配置は手順書2章に進む。

## ローカル検証

既存のSQLiteモードで共同決定の回帰テストを行う。共通MySQL側の招待テストは、テスト用MySQLへ006を適用してから実行する。既存データを使う環境でのDDLやテスト用行の作成は、接続先と作業範囲を確認してから行う。
