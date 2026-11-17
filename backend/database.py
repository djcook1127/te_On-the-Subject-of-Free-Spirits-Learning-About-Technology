# DBに接続し、データの取得・登録・更新・削除と、保存の確定・取り消しを行うプログラムです。
#
# 接続情報は .env に置く（Workbench に入れたものと同じ5つ）。コードに書かない。GitHub に上げない。
#   DB_HOST     = ホスト名（xxx.mysql.database.azure.com）
#   DB_PORT     = 3306
#   DB_USER     = 配られたユーザー名（例 tech0gen13-class1）
#   DB_PASSWORD = 班のパスワード
#   DB_NAME     = 班のDB名（例 giftia_t101 ＝ クラス1の班1）
#   DB_SSL_CA   = 配布された SSL証明書のパス（任意。入れると Workbench の「Verify CA」と同じく相手を確かめる）

import os
from contextlib import contextmanager

import pymysql
from dotenv import load_dotenv

load_dotenv()  # 同じフォルダの .env を読み、os.environ に入れる


def get_connection():
    """班のDBへの接続を1つ作って返す。使い終わったら close() する（fetch_all が面倒を見る）"""
    required = ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(f".env に設定がありません: {', '.join(missing)}（.env.example を .env にコピーして埋める）")

    # Azure は暗号化（SSL/TLS）しない接続を断る。証明書のパスがあれば、相手が Azure のサーバーかも確かめる
    ssl = {"ca": os.environ["DB_SSL_CA"]} if os.environ.get("DB_SSL_CA") else {"ssl_disabled": False}

    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,  # 行を {列名: 値} の形で受け取る（JSON にしやすい）
        connect_timeout=10,
        ssl=ssl,
    )


def fetch_all(query: str, params: tuple = ()) -> list[dict]:
    """SELECT を実行して、行を dict のリストで返す。
    値は params で渡す（SQL の中の %s に入る）。文字列に直接つなげると、入力次第で DB を壊される。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


# ── ここから追加（3週目〜）：書き込み用 ─────────────────────────
# pymysql は、書き込んだだけでは DB に反映されない。commit()（確定）して初めて保存される。
# 途中で失敗したら rollback()（取り消し）して、書きかけの状態を残さない。


def insert(query: str, params: tuple = ()) -> int:
    """INSERT を1つ実行して確定し、追加した行の id を返す"""
    # ① 接続して、1件の登録処理を実行する。
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            new_id = cur.lastrowid
        # ② 登録を確定し、追加した行の番号を返す。
        conn.commit()
        return new_id
    except Exception:
        # 途中で失敗したら、未確定の登録を取り消す。
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(query: str, params: tuple = ()) -> int:
    """UPDATE・DELETEを実行し、影響した行数を返す。0は対象なし・変更なしの場合。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            changed_rows = cur.execute(query, params)
        conn.commit()
        return changed_rows
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def transaction():
    """複数の書き込みを「全部成功」か「全部取り消し」にまとめる。
    例：ルームを作る（ルーム追加 → 幹事をメンバーに追加 → ルームに幹事を記録）
        with transaction() as cur:
            cur.execute("INSERT ...", (...))
            room_id = cur.lastrowid
            ...
    with の中で例外が起きたら、それまでの書き込みはすべて取り消される"""
    # ① 複数の書き込みで共通して使う接続を作る。
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # ② いったん呼び出し元へ移り、withの中のSQLを実行してもらう。
            yield cur

        # ③ すべて成功して戻ってきたら、まとめて保存を確定する。
        conn.commit()
    except Exception:
        # 途中で失敗した場合は、ここまでの書き込みをまとめて取り消す。
        conn.rollback()
        # 呼び出し元にも失敗を伝える。
        raise
    finally:
        # 成功・失敗のどちらでも、接続を閉じる。
        conn.close()
