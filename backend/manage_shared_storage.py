"""共通DBの追加DDL適用と、旧SQLiteからの非破壊コピー。設定内容は出力しない。"""
import argparse
import hashlib
import json
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from shared_rooms import _connect, connection

MIGRATION = Path(__file__).resolve().parent.parent / "db/migrations/002_shared_selection.sql"
EXPECTED = {
    "selection_state": {"room_id", "phase", "decision"},
    "selection_submitters": {"room_id", "member_id", "submitted", "version"},
    "selection_proposals": {"room_id", "member_id", "product_id", "reason", "gift"},
    "selection_notes": {"id", "room_id", "member_id", "kind", "text"},
    "selection_votes": {"room_id", "member_id", "product_id", "stars"},
    "selection_comments": {"id", "room_id", "member_id", "product_id", "text"},
    "consultation_member_sessions": {"token_hash", "room_id", "member_id", "expires_at", "legacy_room_id"},
    "selection_imports": {"source_key", "old_room_id", "new_room_id", "member_map", "imported_at"},
}


def ddl_statements():
    text = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
    statements = [part.strip() for part in text.split(";") if part.strip()]
    if len(statements) != len(EXPECTED) or any(not s.startswith("CREATE TABLE IF NOT EXISTS ") for s in statements):
        raise ValueError("追加テーブル以外のSQLが含まれています")
    return statements


def preflight(cursor):
    cursor.execute("SHOW TABLES")
    tables = {next(iter(row.values())) for row in cursor.fetchall()}
    required = {"consultations": {"id", "title", "budget_total", "member_count", "deliver_by", "organizer_id"},
                "consultation_members": {"id", "consultation_id", "nickname"}}
    for table, columns in {**required, **EXPECTED}.items():
        if table not in tables:
            if table in required:
                raise ValueError("必要な既存テーブルがありません")
            continue
        # tableは上記の固定識別子のみ。値をSQLへ埋め込まない。
        cursor.execute(f"SHOW COLUMNS FROM {table}")
        actual = {row["Field"] for row in cursor.fetchall()}
        if not columns <= actual:
            raise ValueError("既存の列定義が想定と異なります")
    return tables


def apply_schema():
    raw = _connect()
    try:
        with raw.cursor() as cursor:
            existing = preflight(cursor)
            for statement in ddl_statements():
                cursor.execute(statement)
            verified = preflight(cursor)
            if not EXPECTED.keys() <= verified:
                raise ValueError("追加テーブルの確認に失敗しました")
        raw.commit()
        return {"createdTables": sorted(EXPECTED.keys() - existing), "verifiedTables": sorted(EXPECTED)}
    finally:
        raw.close()


def backup_sqlite(source):
    source = Path(source).resolve(strict=True)
    backup_dir = source.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = backup_dir / f"{source.stem}-{stamp}.sqlite3"
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original, closing(sqlite3.connect(destination)) as backup:
        original.backup(backup)
    return destination


def copy_sqlite(source):
    source = Path(source).resolve(strict=True)
    snapshot = backup_sqlite(source)
    source_key = hashlib.sha256(str(source).encode()).hexdigest()
    copied = []
    skipped = []
    with closing(sqlite3.connect(snapshot.as_uri() + "?mode=ro", uri=True)) as old:
        old.row_factory = sqlite3.Row
        names = {r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"consultations", "consultation_members"} <= names:
            raise ValueError("ルーム保存用のSQLiteではありません")
        with connection() as con:
            for room in old.execute("SELECT * FROM consultations ORDER BY id"):
                previous = con.execute("SELECT new_room_id FROM selection_imports WHERE source_key=%s AND old_room_id=%s FOR UPDATE", (source_key, room["id"])).fetchone()
                if previous:
                    skipped.append({"oldRoomId": room["id"], "newRoomId": previous["new_room_id"]})
                    continue
                members = old.execute("SELECT * FROM consultation_members WHERE consultation_id=? ORDER BY id", (room["id"],)).fetchall()
                if room["organizer_id"] not in {m["id"] for m in members}:
                    raise ValueError("旧ルームの主催者を確認できません")
                new_id = con.execute("INSERT INTO consultations(title,budget_total,member_count,deliver_by) VALUES (%s,%s,%s,%s)", (room["title"], room["budget_total"], room["member_count"], room["deliver_by"])).lastrowid
                mapping = {}
                for member in members:
                    mapping[member["id"]] = con.execute("INSERT INTO consultation_members(consultation_id,nickname) VALUES (%s,%s)", (new_id, member["nickname"])).lastrowid
                con.execute("UPDATE consultations SET organizer_id=%s WHERE id=%s", (mapping[room["organizer_id"]], new_id))
                state = old.execute("SELECT phase,decision FROM selection_state WHERE room_id=?", (room["id"],)).fetchone() if "selection_state" in names else None
                con.execute("INSERT INTO selection_state(room_id,phase,decision) VALUES (%s,%s,%s)", (new_id, state["phase"] if state else "collecting", state["decision"] if state else None))
                submitters = old.execute("SELECT * FROM selection_submitters WHERE room_id=?", (room["id"],)).fetchall() if "selection_submitters" in names else []
                if len(submitters) > 5:
                    raise ValueError("旧ルームの提出者が上限を超えています")
                if "selection_proposals" in names and old.execute("SELECT member_id FROM selection_proposals WHERE room_id=? GROUP BY member_id HAVING COUNT(*)>3", (room["id"],)).fetchone():
                    raise ValueError("旧ルームの候補が1人3品を超えています")
                for submitter in submitters:
                    con.execute("INSERT INTO selection_submitters(room_id,member_id,submitted,version) VALUES (%s,%s,%s,%s)", (new_id, mapping[submitter["member_id"]], submitter["submitted"], submitter["version"]))
                definitions = {
                    "selection_proposals": ("product_id", "reason", "gift"),
                    "selection_notes": ("kind", "text"),
                    "selection_votes": ("product_id", "stars"),
                    "selection_comments": ("product_id", "text"),
                }
                for table, fields in definitions.items():
                    if table not in names:
                        continue
                    # table・fieldsは固定の識別子。実データはparamsで渡す。
                    for row in old.execute(f"SELECT * FROM {table} WHERE room_id=? ORDER BY rowid", (room["id"],)):
                        columns = ",".join(("room_id", "member_id", *fields))
                        placeholders = ",".join(["%s"] * (2 + len(fields)))
                        con.execute(f"INSERT INTO {table}({columns}) VALUES ({placeholders})", (new_id, mapping[row["member_id"]], *(row[f] for f in fields)))
                if "local_member_sessions" in names:
                    for session in old.execute("SELECT * FROM local_member_sessions WHERE room_id=?", (room["id"],)):
                        con.execute("INSERT INTO consultation_member_sessions(token_hash,room_id,member_id,expires_at,legacy_room_id) VALUES (%s,%s,%s,%s,%s)", (session["token_hash"], new_id, mapping[session["member_id"]], session["expires_at"], room["id"]))
                for table in ("selection_submitters", *definitions):
                    expected = old.execute(f"SELECT COUNT(*) FROM {table} WHERE room_id=?", (room["id"],)).fetchone()[0] if table in names else 0
                    actual = con.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE room_id=%s", (new_id,)).fetchone()["n"]
                    if expected != actual:
                        raise ValueError("引継ぎ前後の件数が一致しません")
                con.execute("INSERT INTO selection_imports(source_key,old_room_id,new_room_id,member_map) VALUES (%s,%s,%s,%s)", (source_key, room["id"], new_id, json.dumps(mapping)))
                copied.append({"oldRoomId": room["id"], "newRoomId": new_id})
    return {"copied": copied, "alreadyImported": skipped, "backupCreated": True, "rowCountsVerified": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("apply")
    importer = subparsers.add_parser("import-sqlite")
    importer.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(args.env_file)
        result = apply_schema() if args.command == "apply" else copy_sqlite(args.source)
        print(json.dumps(result, ensure_ascii=True))
    except Exception as error:
        # 例外本文には接続先などが含まれ得るため出力しない。
        result = {"ok": False, "errorType": type(error).__name__}
        if error.args and isinstance(error.args[0], int):
            result["errorCode"] = error.args[0]
        print(json.dumps(result))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
