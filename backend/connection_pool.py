"""共通API用の小さな接続プール。資格情報は保持・出力せず既存接続を利用する。"""
import atexit
import queue
import threading
import time

import pymysql


class Lease:
    def __init__(self, pool, raw, created):
        self.pool, self.raw, self.created = pool, raw, created
        self.closed = False
        self.needs_reset = True

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def cursor(self, *args, **kwargs):
        self.needs_reset = True
        return self.raw.cursor(*args, **kwargs)

    def begin(self):
        self.needs_reset = True
        return self.raw.begin()

    def commit(self):
        result = self.raw.commit()
        self.needs_reset = False
        return result

    def rollback(self):
        result = self.raw.rollback()
        self.needs_reset = False
        return result

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            # トランザクションやREAD ONLY指定を次の利用者へ持ち越さない。
            if self.needs_reset:
                self.raw.rollback()
            if time.monotonic() - self.created < self.pool.max_age:
                self.pool.idle.put_nowait((self.raw, self.created))
                return
        except Exception:
            pass
        finally:
            self.pool.slots.release()
        try:
            self.raw.close()
        except Exception:
            pass


class ConnectionPool:
    def __init__(self, factory, size=8, max_age=120, timeout=5):
        self.factory, self.max_age, self.timeout = factory, max_age, timeout
        self.idle = queue.LifoQueue(maxsize=size)
        self.slots = threading.BoundedSemaphore(size)

    def acquire(self):
        if not self.slots.acquire(timeout=self.timeout):
            raise pymysql.OperationalError(2003, "DB接続が混雑しています")
        try:
            while True:
                try:
                    raw, created = self.idle.get_nowait()
                except queue.Empty:
                    return Lease(self, self.factory(), time.monotonic())
                if time.monotonic() - created < self.max_age:
                    return Lease(self, raw, created)
                try:
                    raw.close()
                except Exception:
                    pass
        except Exception:
            self.slots.release()
            raise

    def shutdown(self):
        while True:
            try:
                raw, _ = self.idle.get_nowait()
            except queue.Empty:
                break
            try:
                raw.close()
            except Exception:
                pass


def _open():
    from database import get_connection
    return get_connection()


pool = ConnectionPool(_open)
atexit.register(pool.shutdown)
