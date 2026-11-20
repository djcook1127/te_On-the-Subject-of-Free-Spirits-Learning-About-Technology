"""共同決定用の小さなDB窓口。SQL値は常にパラメーターで渡す。"""


class SQLiteStore:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=()):
        return self.connection.execute(query.replace("%s", "?"), params)

    def executemany(self, query, params):
        return self.connection.executemany(query.replace("%s", "?"), params)

    def ensure_state(self, room_id):
        self.execute("INSERT OR IGNORE INTO selection_state(room_id) VALUES (%s)", (room_id,))

    def add_submitters(self, room_id, ids):
        self.executemany("INSERT OR IGNORE INTO selection_submitters(room_id,member_id) VALUES (%s,%s)", [(room_id, mid) for mid in ids])

    def save_vote(self, params):
        self.execute("INSERT INTO selection_votes(room_id,member_id,product_id,stars) VALUES (%s,%s,%s,%s) ON CONFLICT(room_id,member_id,product_id) DO UPDATE SET stars=excluded.stars", params)


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
        self.execute("INSERT INTO selection_state(room_id) VALUES (%s) ON DUPLICATE KEY UPDATE room_id=VALUES(room_id)", (room_id,))

    def add_submitters(self, room_id, ids):
        self.executemany("INSERT INTO selection_submitters(room_id,member_id) VALUES (%s,%s) ON DUPLICATE KEY UPDATE member_id=VALUES(member_id)", [(room_id, mid) for mid in ids])

    def save_vote(self, params):
        self.execute("INSERT INTO selection_votes(room_id,member_id,product_id,stars) VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE stars=VALUES(stars)", params)
