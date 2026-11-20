import unittest
from unittest.mock import MagicMock

import pymysql
from connection_pool import ConnectionPool


class PoolTests(unittest.TestCase):
    def test_successful_commit_or_rollback_does_not_send_duplicate_reset(self):
        raw = MagicMock()
        pool = ConnectionPool(lambda: raw, size=1)
        lease = pool.acquire()
        lease.commit()
        lease.close()
        raw.rollback.assert_not_called()
        lease = pool.acquire()
        lease.cursor()
        lease.rollback()
        lease.close()
        raw.rollback.assert_called_once()
        pool.shutdown()
    def test_reuses_connection_and_clears_transaction_before_return(self):
        raw = MagicMock()
        factory = MagicMock(return_value=raw)
        pool = ConnectionPool(factory, size=1)
        first = pool.acquire()
        first.close()
        first.close()  # 二重返却で上限を壊さない。
        second = pool.acquire()
        self.assertIs(second.raw, raw)
        factory.assert_called_once()
        raw.rollback.assert_called_once()
        second.close()
        pool.shutdown()
        raw.close.assert_called_once()

    def test_broken_reset_is_discarded_and_failed_open_releases_slot(self):
        broken, healthy = MagicMock(), MagicMock()
        broken.rollback.side_effect = OSError('private')
        factory = MagicMock(side_effect=[broken, OSError('private'), healthy])
        pool = ConnectionPool(factory, size=1, timeout=0)
        pool.acquire().close()
        broken.close.assert_called_once()
        with self.assertRaises(OSError):
            pool.acquire()
        lease = pool.acquire()
        self.assertIs(lease.raw, healthy)
        lease.close()
        pool.shutdown()

    def test_capacity_and_expiry(self):
        factory = MagicMock(side_effect=[MagicMock(), MagicMock()])
        pool = ConnectionPool(factory, size=1, timeout=0, max_age=0)
        lease = pool.acquire()
        with self.assertRaises(pymysql.OperationalError):
            pool.acquire()
        lease.close()
        second = pool.acquire()
        self.assertIsNot(second.raw, lease.raw)
        second.close()
