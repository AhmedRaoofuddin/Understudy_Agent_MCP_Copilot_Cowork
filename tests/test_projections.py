import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.event_log import (
    OUTCOME_CONFIRMED,
    OUTCOME_REVERTED,
    VERDICT_APPROVE,
    EventLog,
)
from core.gatekeeper import Gatekeeper
from core.projections import compute_reviewer_weights, fold_bucket_trust
from core.settings import DEFAULT_SETTINGS


def seed(gate, bucket_key, reviewer, count, reverted=0):
    for index in range(count):
        task_id = reviewer + "_" + str(index)
        gate.record_verdict(task_id, bucket_key, reviewer, VERDICT_APPROVE, 0.0)
        outcome = OUTCOME_REVERTED if index < reverted else OUTCOME_CONFIRMED
        gate.record_outcome(task_id, bucket_key, outcome)


class ReviewerWeightTests(unittest.TestCase):
    def test_diligent_reviewer_keeps_full_weight(self):
        gate = Gatekeeper(EventLog())
        key = gate.classify("MARKETING", "CREATE", {}).key
        seed(gate, key, "dana", 10, reverted=0)
        weights = compute_reviewer_weights(gate.event_log.all_events(), DEFAULT_SETTINGS)
        self.assertEqual(weights["dana"], 1.0)

    def test_rubber_stamper_is_down_weighted(self):
        gate = Gatekeeper(EventLog())
        key = gate.classify("MARKETING", "CREATE", {}).key
        seed(gate, key, "rick", 10, reverted=5)
        weights = compute_reviewer_weights(gate.event_log.all_events(), DEFAULT_SETTINGS)
        self.assertLess(weights["rick"], 1.0)


class FoldTrustTests(unittest.TestCase):
    def test_reversals_lower_trust(self):
        gate_clean = Gatekeeper(EventLog())
        key = gate_clean.classify("MARKETING", "CREATE", {}).key
        seed(gate_clean, key, "dana", 12, reverted=0)
        weights_clean = compute_reviewer_weights(gate_clean.event_log.all_events(), DEFAULT_SETTINGS)
        clean = fold_bucket_trust(gate_clean.event_log.events_for_bucket(key), weights_clean, DEFAULT_SETTINGS)

        gate_dirty = Gatekeeper(EventLog())
        seed(gate_dirty, key, "dana", 12, reverted=4)
        weights_dirty = compute_reviewer_weights(gate_dirty.event_log.all_events(), DEFAULT_SETTINGS)
        dirty = fold_bucket_trust(gate_dirty.event_log.events_for_bucket(key), weights_dirty, DEFAULT_SETTINGS)

        self.assertGreater(clean.trust_lower_bound, dirty.trust_lower_bound)


if __name__ == "__main__":
    unittest.main()
