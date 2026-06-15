"""Model routing: let cost follow usage.

Not every task needs the strongest model. Low risk, high volume work runs on the
fast model. Standard work runs on the mid model. High risk or reasoning heavy
work runs on the strongest model. The router maps a risk bucket to a tier and a
model id, so the integration can spend in proportion to what each task needs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from core.bucketing import ACCESS_EXTERNAL, ACCESS_INTERNAL, VALUE_CRITICAL, VALUE_LOW, Bucket

TIER_FAST = "fast"
TIER_STANDARD = "standard"
TIER_DEEP = "deep"


@dataclass(frozen=True)
class ModelRouter:
    fast_model: str = "claude-haiku-4-5"
    standard_model: str = "claude-sonnet-4-6"
    deep_model: str = "claude-opus-4-8"

    @classmethod
    def from_env(cls) -> "ModelRouter":
        return cls(
            fast_model=os.environ.get("UNDERSTUDY_FAST_MODEL", cls.fast_model),
            standard_model=os.environ.get("UNDERSTUDY_STANDARD_MODEL", cls.standard_model),
            deep_model=os.environ.get("UNDERSTUDY_DEEP_MODEL", cls.deep_model),
        )

    def tier_for(self, bucket: Bucket) -> str:
        if bucket.value_tier == VALUE_CRITICAL or bucket.access_scope == ACCESS_EXTERNAL:
            return TIER_DEEP
        if bucket.value_tier == VALUE_LOW and bucket.access_scope == ACCESS_INTERNAL:
            return TIER_FAST
        return TIER_STANDARD

    def model_for(self, bucket: Bucket) -> str:
        return {
            TIER_FAST: self.fast_model,
            TIER_STANDARD: self.standard_model,
            TIER_DEEP: self.deep_model,
        }[self.tier_for(bucket)]
