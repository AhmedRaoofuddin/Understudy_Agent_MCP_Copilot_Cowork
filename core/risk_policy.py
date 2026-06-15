"""Risk policy: how much confidence a task class needs, and its hard ceiling.

Two ideas live here. The target confidence sets how high the trust lower bound
must climb before a task class can act on its own. A low value internal task
graduates at a modest bar. A critical value or external task demands a near
perfect history. The autonomy ceiling is a hard cap for classes that must always
keep a human in the loop no matter how high the trust climbs, such as hiring
decisions, privileged access changes, and large payments.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from core.bucketing import (
    ACCESS_EXTERNAL,
    ACCESS_INTERNAL,
    VALUE_CRITICAL,
    VALUE_LOW,
    Bucket,
)


class AutonomyLevel(IntEnum):
    ASK_ALWAYS = 0
    ASK_WHEN_UNSURE = 1
    AUTONOMOUS = 2


@dataclass(frozen=True)
class RiskPolicy:
    low_internal_target: float = 0.70
    standard_target: float = 0.85
    high_risk_target: float = 0.96

    def target_confidence(self, bucket: Bucket) -> float:
        if bucket.value_tier == VALUE_CRITICAL or bucket.access_scope == ACCESS_EXTERNAL:
            return self.high_risk_target
        if bucket.value_tier == VALUE_LOW and bucket.access_scope == ACCESS_INTERNAL:
            return self.low_internal_target
        return self.standard_target

    def autonomy_ceiling(self, bucket: Bucket) -> AutonomyLevel:
        if bucket.domain == "TALENT" and bucket.verb == "DECIDE":
            return AutonomyLevel.ASK_WHEN_UNSURE
        if bucket.domain == "IT" and bucket.access_scope == ACCESS_EXTERNAL:
            return AutonomyLevel.ASK_WHEN_UNSURE
        if bucket.value_tier == VALUE_CRITICAL and bucket.verb in ("SEND", "PAY", "DELETE"):
            return AutonomyLevel.ASK_WHEN_UNSURE
        return AutonomyLevel.AUTONOMOUS
