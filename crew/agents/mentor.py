"""Mentor: fold the verdict and the outcome back into memory.

This is the Evolve step. It appends the human verdict (when there was one) and
the real outcome to the event log. Trust is recomputed from the log on the next
Appraise, so there is no mutable score to corrupt and no race to lose.
"""

from __future__ import annotations

from typing import Optional

from core.gatekeeper import Gatekeeper


def evolve(
    gatekeeper: Gatekeeper,
    task_id: str,
    bucket_key: str,
    reviewer_id: str,
    verdict: Optional[str],
    edit_distance: float,
    outcome: Optional[str],
) -> None:
    if verdict is not None:
        gatekeeper.record_verdict(task_id, bucket_key, reviewer_id, verdict, edit_distance)
    if outcome is not None:
        gatekeeper.record_outcome(task_id, bucket_key, outcome)
