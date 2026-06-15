"""The Gatekeeper: the deterministic ask versus act decision.

This is the safety core and the Appraise step of the Understudy Loop. Given a
proposed action it classifies the risk bucket, folds the trust snapshot from the
event log, compares the trust to the risk weighted target, applies the hard
ceiling, and returns a Decision. No model runs here, so the decision is
reproducible and auditable. The Gatekeeper also records verdicts and outcomes as
idempotent appends to the event log.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from core.bucketing import Bucket, BucketConfig, bucket_from_key, classify
from core.concurrency import idempotency_key
from core.event_log import KIND_OUTCOME, KIND_VERDICT, EventLog
from core.projections import compute_reviewer_weights, fold_bucket_trust
from core.risk_policy import AutonomyLevel, RiskPolicy
from core.settings import DEFAULT_SETTINGS, Settings


@dataclass(frozen=True)
class Decision:
    bucket_key: str
    trust_lower_bound: float
    target_confidence: float
    autonomy_level: AutonomyLevel
    requires_human: bool
    task_count: int
    failed_closed: bool
    reason: str


class Gatekeeper:
    def __init__(
        self,
        event_log: EventLog,
        bucket_config: Optional[BucketConfig] = None,
        risk_policy: Optional[RiskPolicy] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.event_log = event_log
        self.bucket_config = bucket_config or BucketConfig()
        self.risk_policy = risk_policy or RiskPolicy()
        self.settings = settings or DEFAULT_SETTINGS

    def classify(self, domain: str, verb: str, payload: Mapping[str, object]) -> Bucket:
        return classify(domain, verb, payload, self.bucket_config)

    def evaluate(self, domain: str, verb: str, payload: Mapping[str, object]) -> Decision:
        bucket = self.classify(domain, verb, payload)
        reviewer_weights = compute_reviewer_weights(self.event_log.all_events(), self.settings)
        snapshot = fold_bucket_trust(
            self.event_log.events_for_bucket(bucket.key), reviewer_weights, self.settings
        )
        target = self.risk_policy.target_confidence(bucket)
        ceiling = self.risk_policy.autonomy_ceiling(bucket)

        proposed_level, reason = self._decide_level(snapshot, target)
        final_level = AutonomyLevel(min(int(proposed_level), int(ceiling)))
        if final_level != proposed_level:
            reason = reason + ", then capped to " + final_level.name + " by the risk ceiling"

        return Decision(
            bucket_key=bucket.key,
            trust_lower_bound=snapshot.trust_lower_bound,
            target_confidence=target,
            autonomy_level=final_level,
            requires_human=final_level != AutonomyLevel.AUTONOMOUS,
            task_count=snapshot.task_count,
            failed_closed=bucket.failed_closed,
            reason=reason,
        )

    def list_trust(self) -> list:
        """Return a trust snapshot for every task class seen in the event log.

        This powers the trust dial view, where a team can see exactly what each
        task class has earned the right to do on its own.
        """
        reviewer_weights = compute_reviewer_weights(self.event_log.all_events(), self.settings)
        keys = sorted({event.bucket_key for event in self.event_log.all_events()})
        rows = []
        for key in keys:
            snapshot = fold_bucket_trust(
                self.event_log.events_for_bucket(key), reviewer_weights, self.settings
            )
            bucket = bucket_from_key(key)
            target = self.risk_policy.target_confidence(bucket)
            proposed_level, _ = self._decide_level(snapshot, target)
            ceiling = self.risk_policy.autonomy_ceiling(bucket)
            final_level = AutonomyLevel(min(int(proposed_level), int(ceiling)))
            rows.append(
                {
                    "bucket_key": key,
                    "trust_lower_bound": round(snapshot.trust_lower_bound, 4),
                    "target_confidence": target,
                    "autonomy_level": final_level.name,
                    "task_count": snapshot.task_count,
                }
            )
        return rows

    def _decide_level(self, snapshot, target: float):
        if snapshot.task_count < self.settings.min_samples_to_judge:
            return AutonomyLevel.ASK_ALWAYS, "bootstrapping with too few samples to judge"
        if snapshot.recent_failure:
            return AutonomyLevel.ASK_ALWAYS, "demoted after a recent rejection or reversal"
        if snapshot.trust_lower_bound >= target:
            return AutonomyLevel.AUTONOMOUS, "trust lower bound is at or above the target"
        if snapshot.trust_lower_bound >= target * self.settings.uncertain_band_ratio:
            return AutonomyLevel.ASK_WHEN_UNSURE, "trust is inside the uncertain band"
        return AutonomyLevel.ASK_ALWAYS, "trust is below the uncertain band"

    def record_verdict(
        self,
        task_id: str,
        bucket_key: str,
        reviewer_id: str,
        verdict: str,
        edit_distance: float = 0.0,
        run_id: str = "local",
        step: str = "verdict",
    ) -> bool:
        key = idempotency_key(run_id, step, task_id, bucket_key, reviewer_id, verdict)
        return self.event_log.append(
            key,
            bucket_key,
            KIND_VERDICT,
            task_id,
            {"reviewer_id": reviewer_id, "verdict": verdict, "edit_distance": edit_distance},
        )

    def record_outcome(
        self,
        task_id: str,
        bucket_key: str,
        outcome: str,
        run_id: str = "local",
        step: str = "outcome",
    ) -> bool:
        key = idempotency_key(run_id, step, task_id, bucket_key, outcome)
        return self.event_log.append(
            key, bucket_key, KIND_OUTCOME, task_id, {"outcome": outcome}
        )
