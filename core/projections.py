"""Projections: fold the event log into a trust snapshot for a bucket.

The trust score is never stored. It is derived on read by folding the append
only events for a bucket. Two safeguards make the score honest:

  Reviewer weighting. A reviewer who approves almost everything is a rubber
  stamper, so their verdicts are down weighted based on their behaviour across
  the whole log. A reviewer who sometimes edits or rejects keeps full weight.

  Outcome weighting. Approval is not the same as correctness. If an action was
  approved but later reverted, that task counts as a failure regardless of the
  verdict. So trust tracks what actually worked, not what got waved through.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from core.event_log import (
    KIND_OUTCOME,
    KIND_VERDICT,
    OUTCOME_REVERTED,
    VERDICT_APPROVE,
    VERDICT_EDIT,
    VERDICT_REJECT,
    Event,
)
from core.settings import Settings
from core.trust_math import wilson_lower_bound


@dataclass(frozen=True)
class TrustSnapshot:
    trust_lower_bound: float
    effective_sample_size: float
    task_count: int
    recent_failure: bool


def compute_reviewer_weights(all_events: List[Event], settings: Settings) -> Dict[str, float]:
    """Down weight a reviewer only when both signals point to rubber stamping.

    A reviewer is suspect when they approve almost everything and their approvals
    do not hold up, meaning a real share of what they approved was later
    reverted. A diligent reviewer who approves a lot but whose approvals are
    confirmed by outcomes keeps full weight. This avoids punishing someone who
    simply works a low risk queue where most things are genuinely fine.
    """
    outcomes: Dict[str, str] = {
        event.task_id: event.data.get("outcome", "")
        for event in all_events
        if event.kind == KIND_OUTCOME
    }

    review_totals: Dict[str, int] = {}
    pure_approvals: Dict[str, int] = {}
    approvals_with_outcome: Dict[str, int] = {}
    reverted_approvals: Dict[str, int] = {}

    for event in all_events:
        if event.kind != KIND_VERDICT:
            continue
        reviewer = event.data.get("reviewer_id", "unknown")
        review_totals[reviewer] = review_totals.get(reviewer, 0) + 1
        is_pure_approval = (
            event.data.get("verdict") == VERDICT_APPROVE
            and float(event.data.get("edit_distance", 0.0)) == 0.0
        )
        if is_pure_approval:
            pure_approvals[reviewer] = pure_approvals.get(reviewer, 0) + 1
            outcome = outcomes.get(event.task_id, "")
            if outcome:
                approvals_with_outcome[reviewer] = approvals_with_outcome.get(reviewer, 0) + 1
                if outcome == OUTCOME_REVERTED:
                    reverted_approvals[reviewer] = reverted_approvals.get(reviewer, 0) + 1

    weights: Dict[str, float] = {}
    for reviewer, total in review_totals.items():
        approval_rate = pure_approvals.get(reviewer, 0) / total
        judged = approvals_with_outcome.get(reviewer, 0)
        reversal_rate = (reverted_approvals.get(reviewer, 0) / judged) if judged > 0 else 0.0

        seen_enough = total >= settings.reviewer_min_reviews
        high_approval = approval_rate > settings.rubber_stamp_threshold
        approvals_do_not_hold = reversal_rate > settings.rubber_stamp_reversal_floor

        if seen_enough and high_approval and approvals_do_not_hold:
            weights[reviewer] = max(settings.rubber_stamp_min_weight, 1.0 - reversal_rate)
        else:
            weights[reviewer] = 1.0
    return weights


def _base_success(verdict: str, edit_distance: float) -> float:
    if verdict == VERDICT_APPROVE:
        return 1.0
    if verdict == VERDICT_EDIT:
        return max(0.0, 1.0 - edit_distance)
    return 0.0


def fold_bucket_trust(
    bucket_events: List[Event], reviewer_weights: Dict[str, float], settings: Settings
) -> TrustSnapshot:
    verdicts: Dict[str, Dict[str, object]] = {}
    outcomes: Dict[str, str] = {}
    task_order: List[str] = []

    for event in bucket_events:
        if event.kind == KIND_VERDICT:
            verdicts[event.task_id] = {
                "verdict": event.data.get("verdict"),
                "edit_distance": float(event.data.get("edit_distance", 0.0)),
                "reviewer_id": event.data.get("reviewer_id", "unknown"),
            }
            task_order.append(event.task_id)
        elif event.kind == KIND_OUTCOME:
            outcomes[event.task_id] = event.data.get("outcome", "")

    weighted_successes = 0.0
    effective_sample_size = 0.0

    for task_id, record in verdicts.items():
        base = _base_success(str(record["verdict"]), float(record["edit_distance"]))
        if outcomes.get(task_id) == OUTCOME_REVERTED:
            effective = 0.0
        else:
            effective = base
        weight = reviewer_weights.get(str(record["reviewer_id"]), 1.0)
        weighted_successes += weight * effective
        effective_sample_size += weight

    # An autonomous action has an outcome but no human verdict. We never let a
    # confirmed autonomous outcome raise trust, because that would be the agent
    # grading itself. We do let a reverted autonomous outcome count as a lasting
    # failure, so a bad autonomous action pulls trust down on the next pass.
    for task_id, outcome in outcomes.items():
        if task_id not in verdicts and outcome == OUTCOME_REVERTED:
            effective_sample_size += 1.0

    trust = wilson_lower_bound(weighted_successes, effective_sample_size, settings.z_score)

    recent_failure = False
    tail = bucket_events[-(settings.recent_window * 2) :]
    for event in reversed(tail):
        if event.kind == KIND_OUTCOME and event.data.get("outcome") == OUTCOME_REVERTED:
            recent_failure = True
            break
        if event.kind == KIND_VERDICT and event.data.get("verdict") == VERDICT_REJECT:
            recent_failure = True
            break

    return TrustSnapshot(
        trust_lower_bound=trust,
        effective_sample_size=effective_sample_size,
        task_count=len(verdicts),
        recent_failure=recent_failure,
    )
