import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.event_log import VERDICT_APPROVE, EventLog
from core.gatekeeper import Gatekeeper
from integrations.crm import GatedCrm, InMemoryCrm


class InMemoryCrmTests(unittest.TestCase):
    def test_read_write(self):
        crm = InMemoryCrm()
        crm.write("Account", "a1", {"tier": "gold"})
        self.assertEqual(crm.read("Account", "a1")["tier"], "gold")


class GatedCrmTests(unittest.TestCase):
    def test_write_holds_for_human_when_untrusted(self):
        gated = GatedCrm(InMemoryCrm(), Gatekeeper(EventLog()))
        result = gated.write("t1", "UPDATE", "Account", "a1", {"tier": "gold"}, "dana")
        self.assertTrue(result.requires_human)
        self.assertFalse(result.applied)

    def test_write_applies_after_approval(self):
        crm = InMemoryCrm()
        gated = GatedCrm(crm, Gatekeeper(EventLog()))
        result = gated.write(
            "t1", "UPDATE", "Account", "a1", {"tier": "gold"}, "dana", human_verdict=VERDICT_APPROVE
        )
        self.assertTrue(result.applied)
        self.assertEqual(crm.read("Account", "a1")["tier"], "gold")

    def test_class_graduates_to_autonomous_write(self):
        crm = InMemoryCrm()
        gated = GatedCrm(crm, Gatekeeper(EventLog()))
        for index in range(12):
            gated.write(
                "seed" + str(index),
                "UPDATE",
                "Account",
                "a" + str(index),
                {"tier": "gold"},
                "dana",
                human_verdict=VERDICT_APPROVE,
            )
        result = gated.write("final", "UPDATE", "Account", "z", {"tier": "gold"}, "dana")
        self.assertFalse(result.requires_human)
        self.assertTrue(result.applied)


if __name__ == "__main__":
    unittest.main()
