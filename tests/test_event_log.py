import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.event_log import KIND_VERDICT, EventLog, FileEventLog


class EventLogTests(unittest.TestCase):
    def test_append_then_duplicate_is_ignored(self):
        log = EventLog()
        self.assertTrue(log.append("e1", "B", KIND_VERDICT, "t1", {"v": "APPROVE"}))
        self.assertFalse(log.append("e1", "B", KIND_VERDICT, "t1", {"v": "APPROVE"}))
        self.assertEqual(log.count(), 1)

    def test_events_for_bucket_filters(self):
        log = EventLog()
        log.append("e1", "B1", KIND_VERDICT, "t1", {})
        log.append("e2", "B2", KIND_VERDICT, "t2", {})
        self.assertEqual(len(log.events_for_bucket("B1")), 1)

    def test_hash_chain_verifies(self):
        log = EventLog()
        for index in range(5):
            log.append("e" + str(index), "B", KIND_VERDICT, "t" + str(index), {"i": index})
        self.assertTrue(log.verify_chain())

    def test_file_log_round_trips(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "events.jsonl")
            first = FileEventLog(path)
            first.append("e1", "B", KIND_VERDICT, "t1", {"v": "APPROVE"})
            first.append("e2", "B", KIND_VERDICT, "t2", {"v": "REJECT"})

            second = FileEventLog(path)
            self.assertEqual(second.count(), 2)
            self.assertTrue(second.verify_chain())
            self.assertFalse(second.append("e1", "B", KIND_VERDICT, "t1", {"v": "APPROVE"}))


if __name__ == "__main__":
    unittest.main()
