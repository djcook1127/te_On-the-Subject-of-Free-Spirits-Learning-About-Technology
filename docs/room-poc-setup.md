# ルーム作成PoCの起動手順

画面：[ルームを作る](http://127.0.0.1:3001/rooms/new)。API：[Swagger](http://127.0.0.1:8000/docs)。両方のサーバーが起動している間に利用できる。

既存の接続設定をAPIが利用する。設定の内容や秘密情報はチャットへ貼らない。班の開発DBには今回の実行許可を受けてdb/schema.sqlの2テーブルを作成済み。別環境での再利用時は適用状況を確認する。IF NOT EXISTSは既存テーブルの列を更新しない。

## Windows（PowerShell）

ターミナル1：APIを起動する。CORSの指定はこのプロセスだけに適用し、環境ファイルは変更しない。

```powershell
Set-Location -LiteralPath 'C:\Users\Takeru Goto\Giftia\backend'
$env:CORS_ORIGINS='http://127.0.0.1:3001,http://localhost:3000'
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

ターミナル2：画面をビルドして起動する。依存パッケージは今回インストール済み。

```powershell
Set-Location -LiteralPath 'C:\Users\Takeru Goto\Giftia\frontend'
npm.cmd run build
npm.cmd run start -- --hostname 127.0.0.1 --port 3001
```

画面を編集しながら確認するときは、startの代わりに次を使う。同じポートの既存サーバーは、そのターミナルでCtrl+Cを押してから切り替える。

```powershell
npm.cmd run dev -- --hostname 127.0.0.1 --port 3001
```

## macOS

各ターミナルをリポジトリのルートで開いて実行する。既存のDB接続設定と依存パッケージを準備した環境向け。

ターミナル1：

```bash
cd backend
CORS_ORIGINS='http://127.0.0.1:3001,http://localhost:3000' python3 -m uvicorn main:app --host 127.0.0.1 --port 8000
```

ターミナル2：

```bash
cd frontend
npm ci --no-audit --no-fund
npm run build
npm run start -- --hostname 127.0.0.1 --port 3001
```

## APIテストと静的チェック

APIテストは標準のunittestと、FastAPIのTestClientを使う。TestClient用にhttpxが必要（今回の環境には導入済み）。新しい本番用ライブラリは追加していない。テストは環境ファイルを読み込まず、班のDBにも接続しない。

リポジトリのルートから実行する。

Windows：

```powershell
python -m unittest discover -s backend -p 'test_*.py' -v
Set-Location frontend
npm.cmd run lint
npm.cmd run build
```

macOS：

```bash
python3 -m unittest discover -s backend -p 'test_*.py' -v
cd frontend
npm run lint
npm run build
```

## 日付と今回の範囲

- 受け取り期限は日本時間の今日以降、土日祝日以外を選ぶ。
- 日本の祝日データは2026・2027年に対応。他の年は、データを更新するまで設定できない。
- 一人あたり負担額は総予算を参加予定人数で割り、1円単位で切り上げる。
- メンバー参加やプロフィールなどは次の実装範囲。作成画面の人数は実際の参加済み人数を表さない。
