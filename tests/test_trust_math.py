import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trust_math import wilson_lower_bound


class TrustMathTests(unittest.TestCase):
    def test_zero_sample_is_zero(self):
        self.assertEqual(wilson_lower_bound(0, 0), 0.0)

    def test_single_success_is_very_conservative(self):
        self.assertLess(wilson_lower_bound(1, 1), 0.3)

    def test_small_clean_sample_is_below_high_bar(self):
        bound = wilson_lower_bound(15, 15)
        self.assertGreater(bound, 0.75)
        self.assertLess(bound, 0.82)

    def test_large_clean_sample_clears_high_bar(self):
        self.assertGreater(wilson_lower_bound(150, 150), 0.96)

    def test_more_evidence_raises_the_bound(self):
        self.assertGreater(wilson_lower_bound(30, 30), wilson_lower_bound(15, 15))

    def test_bound_is_clamped_between_zero_and_one(self):
        self.assertGreaterEqual(wilson_lower_bound(5, 5), 0.0)
        self.assertLessEqual(wilson_lower_bound(5, 5), 1.0)


if __name__ == "__main__":
    unittest.main()
