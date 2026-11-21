"""共同決定用の小さなDB窓口。SQL値は常にパラメーターで渡す。"""
import json


class SQLiteStore:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=()):
        return self.connection.execute(query.replace("%s", "?"), params)

    def executemany(self, query, params):
        return self.connection.executemany(query.replace("%s", "?"), params)

    def ensure_state(self, room_id):
        self.execute("INSERT OR IGNORE INTO selection_state(room_id,organizer_submitted) VALUES (%s,0)", (room_id,))

    def add_submitters(self, room_id, ids):
        self.executemany("INSERT OR IGNORE INTO selection_submitters(room_id,member_id) VALUES (%s,%s)", [(room_id, mid) for mid in ids])

    def save_vote(self, params):
        self.execute("INSERT INTO selection_votes(room_id,member_id,product_id,stars) VALUES (%s,%s,%s,%s) ON CONFLICT(room_id,member_id,product_id) DO UPDATE SET stars=excluded.stars", params)

    def publish_products(self, rows):
        self.executemany("INSERT INTO selection_published_proposals(room_id,member_id,product_id,reason,gift) VALUES (%s,%s,%s,%s,%s) ON CONFLICT(room_id,member_id,product_id) DO UPDATE SET reason=excluded.reason,gift=excluded.gift", rows)

    def curate_product(self, params):
        self.execute("INSERT INTO selection_published_proposals(room_id,member_id,product_id,reason,gift,curated) VALUES (%s,%s,%s,%s,%s,1) ON CONFLICT(room_id,member_id,product_id) DO UPDATE SET reason=excluded.reason,gift=excluded.gift,curated=1", params)


class Result:
    def __init__(self, rows, lastrowid=None):
        self.rows = rows
        self.lastrowid = lastrowid

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def __iter__(self):
        return iter(self.rows)


class MySQLStore:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=()):
        with self.connection.cursor() as cursor:
            cursor.execute(query, params)
            return Result(cursor.fetchall() if cursor.description else [], cursor.lastrowid)

    def executemany(self, query, params):
        if not params:
            return Result([])
        with self.connection.cursor() as cursor:
            cursor.executemany(query, params)
            return Result([], cursor.lastrowid)

    def ensure_state(self, room_id):
        self.execute("INSERT INTO selection_state(room_id,organizer_submitted) VALUES (%s,0) ON DUPLICATE KEY UPDATE room_id=VALUES(room_id)", (room_id,))

    def add_submitters(self, room_id, ids):
        self.executemany("INSERT INTO selection_submitters(room_id,member_id) VALUES (%s,%s) ON DUPLICATE KEY UPDATE member_id=VALUES(member_id)", [(room_id, mid) for mid in ids])

    def save_vote(self, params):
        self.execute("INSERT INTO selection_votes(room_id,member_id,product_id,stars) VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE stars=VALUES(stars)", params)

    def publish_products(self, rows):
        self.executemany("INSERT INTO selection_published_proposals(room_id,member_id,product_id,reason,gift) VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE reason=VALUES(reason),gift=VALUES(gift)", rows)

    def curate_product(self, params):
        self.execute("INSERT INTO selection_published_proposals(room_id,member_id,product_id,reason,gift,curated) VALUES (%s,%s,%s,%s,%s,1) ON DUPLICATE KEY UPDATE reason=VALUES(reason),gift=VALUES(gift),curated=1", params)

    def selection_snapshot(self, room_id, member_id, organizer, phase):
        # 表ごとの取得を1回のSQL往復へ集約。SQL識別子は固定、入力値だけを束縛する。
        columns, params = [], []

        def array(alias, table, fields, condition, values):
            fields_sql = ','.join(f"'{name}',{name}" for name in fields)
            columns.append(f"COALESCE((SELECT JSON_ARRAYAGG(JSON_OBJECT({fields_sql})) FROM {table} WHERE {condition}),JSON_ARRAY()) AS {alias}")
            params.extend(values)

        array('own', 'selection_submitters', ['submitted', 'version'], 'room_id=%s AND member_id=%s', (room_id, member_id))
        array('personal', 'selection_proposals', ['product_id', 'reason', 'gift'], 'room_id=%s AND member_id=%s', (room_id, member_id))
        array('published', 'selection_published_proposals', ['member_id', 'product_id', 'reason', 'gift'], 'room_id=%s', (room_id,))
        array('members', 'consultation_members', ['id', 'nickname'], 'consultation_id=%s AND %s', (room_id, organizer))
        array('own_votes', 'selection_votes', ['product_id', 'stars'], 'room_id=%s AND member_id=%s AND %s', (room_id, member_id, phase != 'collecting'))
        columns.append("""COALESCE((SELECT JSON_ARRAYAGG(JSON_OBJECT('product_id',v.product_id,'total',v.total,'voters',v.voters))
            FROM (SELECT product_id,SUM(stars) AS total,COUNT(*) AS voters FROM selection_votes WHERE room_id=%s AND %s GROUP BY product_id) v),JSON_ARRAY()) AS totals""")
        params.extend((room_id, phase != 'collecting'))
        array('old_notes', 'selection_notes', ['id', 'kind', 'text'], 'room_id=%s', (room_id,))
        array('old_comments', 'selection_comments', ['id', 'product_id', 'text'], 'room_id=%s', (room_id,))
        array('room_comments', 'selection_room_comments', ['id', 'kind', 'text'], 'room_id=%s', (room_id,))
        row = self.execute('SELECT '+','.join(columns), tuple(params)).fetchone()
        result = {key: json.loads(value) if isinstance(value, (str, bytes)) else value for key, value in row.items()}
        # MySQL JSON列は入れ子のobjectになる。既存SQLiteと同じgift文字列へそろえる。
        for key in ('personal', 'published'):
            for item in result[key]:
                if not isinstance(item['gift'], str):
                    item['gift'] = json.dumps(item['gift'], ensure_ascii=False)
        return result
