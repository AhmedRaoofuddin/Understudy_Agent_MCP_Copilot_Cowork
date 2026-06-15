import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.event_log import OUTCOME_CONFIRMED, OUTCOME_REVERTED, VERDICT_APPROVE, EventLog
from core.gatekeeper import Gatekeeper
from crew.loop import HumanVerdict, UnderstudyLoop


class UnderstudyLoopTests(unittest.TestCase):
    def _build_loop(self, revert_task_id=None):
        def always_approve(decision, proposal):
            return HumanVerdict(VERDICT_APPROVE, 0.0)

        def verifier(proposal, result):
            if revert_task_id is not None and proposal.get("task_id") == revert_task_id:
                return OUTCOME_REVERTED
            return OUTCOME_CONFIRMED

        return UnderstudyLoop(
            gatekeeper=Gatekeeper(EventLog()),
            human_gate=always_approve,
            verifier=verifier,
        )

    def test_first_run_asks_a_human(self):
        loop = self._build_loop()
        result = loop.run_task("MARKETING", "CREATE", {"campaign": "x"}, "t1")
        self.assertTrue(result.requires_human)
        self.assertEqual(result.autonomy_level, "ASK_ALWAYS")

    def test_class_graduates_then_demotes_on_reversal(self):
        loop = self._build_loop(revert_task_id="t11")
        outcomes = {}
        for index in range(1, 13):
            task_id = "t" + str(index)
            outcomes[task_id] = loop.run_task("MARKETING", "CREATE", {"campaign": "x"}, task_id)

        graduated = any(not outcomes["t" + str(i)].requires_human for i in range(1, 11))
        self.assertTrue(graduated)

        self.assertFalse(outcomes["t11"].requires_human)
        self.assertEqual(outcomes["t11"].outcome, OUTCOME_REVERTED)

        self.assertTrue(outcomes["t12"].requires_human)


if __name__ == "__main__":
    unittest.main()
