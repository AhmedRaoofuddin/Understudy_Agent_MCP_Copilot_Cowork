import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.event_log import OUTCOME_CONFIRMED, VERDICT_APPROVE, VERDICT_REJECT, EventLog
from core.gatekeeper import Gatekeeper
from core.risk_policy import AutonomyLevel


def approve_many(gate, domain, verb, payload, reviewer, count):
    key = gate.classify(domain, verb, payload).key
    for index in range(count):
        task_id = "t" + str(index)
        gate.record_verdict(task_id, key, reviewer, VERDICT_APPROVE, 0.0)
        gate.record_outcome(task_id, key, OUTCOME_CONFIRMED)
    return key


class GatekeeperTests(unittest.TestCase):
    def test_fresh_class_bootstraps_to_ask(self):
        gate = Gatekeeper(EventLog())
        decision = gate.evaluate("MARKETING", "CREATE", {})
        self.assertEqual(decision.autonomy_level, AutonomyLevel.ASK_ALWAYS)
        self.assertTrue(decision.requires_human)

    def test_low_risk_class_graduates(self):
        gate = Gatekeeper(EventLog())
        approve_many(gate, "MARKETING", "CREATE", {"campaign": "x"}, "dana", 12)
        decision = gate.evaluate("MARKETING", "CREATE", {"campaign": "x"})
        self.assertEqual(decision.autonomy_level, AutonomyLevel.AUTONOMOUS)
        self.assertFalse(decision.requires_human)

    def test_hard_ceiling_blocks_full_autonomy(self):
        gate = Gatekeeper(EventLog())
        approve_many(gate, "TALENT", "DECIDE", {}, "dana", 20)
        decision = gate.evaluate("TALENT", "DECIDE", {})
        self.assertEqual(decision.autonomy_level, AutonomyLevel.ASK_WHEN_UNSURE)
        self.assertTrue(decision.requires_human)

    def test_recent_reject_demotes(self):
        gate = Gatekeeper(EventLog())
        key = approve_many(gate, "MARKETING", "CREATE", {"campaign": "x"}, "dana", 12)
        gate.record_verdict("rejected_one", key, "dana", VERDICT_REJECT, 0.0)
        decision = gate.evaluate("MARKETING", "CREATE", {"campaign": "x"})
        self.assertEqual(decision.autonomy_level, AutonomyLevel.ASK_ALWAYS)

    def test_verdict_record_is_idempotent(self):
        gate = Gatekeeper(EventLog())
        key = gate.classify("MARKETING", "CREATE", {}).key
        self.assertTrue(gate.record_verdict("t1", key, "dana", VERDICT_APPROVE, 0.0))
        self.assertFalse(gate.record_verdict("t1", key, "dana", VERDICT_APPROVE, 0.0))


if __name__ == "__main__":
    unittest.main()
