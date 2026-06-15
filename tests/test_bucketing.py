import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.bucketing import (
    ACCESS_EXTERNAL,
    ACCESS_INTERNAL,
    VALUE_CRITICAL,
    VALUE_HIGH,
    VALUE_LOW,
    BucketConfig,
    bucket_from_key,
    classify,
)

CONFIG = BucketConfig()


class BucketingTests(unittest.TestCase):
    def test_known_low_value_internal(self):
        bucket = classify("ACCOUNTS", "UPDATE", {"amount": 250}, CONFIG)
        self.assertEqual(bucket.value_tier, VALUE_LOW)
        self.assertEqual(bucket.access_scope, ACCESS_INTERNAL)
        self.assertFalse(bucket.failed_closed)

    def test_high_value_threshold(self):
        bucket = classify("ACCOUNTS", "UPDATE", {"amount": "15000"}, CONFIG)
        self.assertEqual(bucket.value_tier, VALUE_HIGH)

    def test_critical_value_threshold(self):
        bucket = classify("ACCOUNTS", "UPDATE", {"amount": 145000}, CONFIG)
        self.assertEqual(bucket.value_tier, VALUE_CRITICAL)

    def test_unknown_money_field_fails_closed(self):
        bucket = classify("ACCOUNTS", "PAY", {"contract_value": 5_000_000}, CONFIG)
        self.assertTrue(bucket.failed_closed)
        self.assertEqual(bucket.value_tier, VALUE_CRITICAL)

    def test_external_marker_sets_external(self):
        bucket = classify("SALES", "SEND", {"recipient": "client@external.com"}, CONFIG)
        self.assertEqual(bucket.access_scope, ACCESS_EXTERNAL)

    def test_verb_synonyms_normalize(self):
        altered = classify("ACCOUNTS", "ALTER", {}, CONFIG).verb
        modified = classify("ACCOUNTS", "MODIFY", {}, CONFIG).verb
        self.assertEqual(altered, "UPDATE")
        self.assertEqual(modified, "UPDATE")

    def test_bucket_from_key_round_trip(self):
        bucket = classify("IT", "DELETE", {"amount": 5}, CONFIG)
        rebuilt = bucket_from_key(bucket.key)
        self.assertEqual(rebuilt.domain, "IT")
        self.assertEqual(rebuilt.verb, "DELETE")
        self.assertEqual(rebuilt.value_tier, bucket.value_tier)


if __name__ == "__main__":
    unittest.main()
