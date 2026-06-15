import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.concurrency import (
    VersionClash,
    VersionedStore,
    add_counter,
    append_items,
    canonical_json,
    idempotency_key,
    union_sets,
)


class IdempotencyKeyTests(unittest.TestCase):
    def test_same_parts_give_same_key(self):
        self.assertEqual(idempotency_key("run", 1, {"a": 1}), idempotency_key("run", 1, {"a": 1}))

    def test_different_parts_give_different_keys(self):
        self.assertNotEqual(idempotency_key("run", 1), idempotency_key("run", 2))

    def test_canonical_json_is_order_independent(self):
        self.assertEqual(canonical_json({"a": 1, "b": 2}), canonical_json({"b": 2, "a": 1}))


class VersionedStoreTests(unittest.TestCase):
    def test_missing_key_starts_at_version_zero(self):
        store = VersionedStore()
        self.assertEqual(store.get("missing"), (0, None))

    def test_stale_version_raises(self):
        store = VersionedStore()
        store.compare_and_set("key", 0, "first")
        with self.assertRaises(VersionClash):
            store.compare_and_set("key", 0, "stale")

    def test_concurrent_increments_lose_no_updates(self):
        store = VersionedStore()
        total = 500

        def increment(_: int) -> None:
            store.update_with_retry("count", lambda value: add_counter(value, 1))

        with ThreadPoolExecutor(max_workers=32) as pool:
            list(pool.map(increment, range(total)))

        _, value = store.get("count")
        self.assertEqual(value, total)


class MergeReducerTests(unittest.TestCase):
    def test_add_counter(self):
        self.assertEqual(add_counter(None, 3), 3)
        self.assertEqual(add_counter(2, 3), 5)

    def test_union_sets(self):
        self.assertEqual(union_sets({1, 2}, {2, 3}), {1, 2, 3})

    def test_append_items(self):
        self.assertEqual(append_items([1], [2, 3]), [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
