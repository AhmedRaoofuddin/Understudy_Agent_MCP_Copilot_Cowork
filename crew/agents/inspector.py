"""Inspector: verify the real outcome of an action.

Approval is not the same as correctness. The Inspector reports what actually
happened after the action ran, so the Mentor can fold the truth back into trust.
With no verifier supplied it assumes the action was confirmed, which keeps the
offline loop simple while leaving the real check pluggable.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from core.event_log import OUTCOME_CONFIRMED

Verifier = Callable[[Dict[str, Any], Dict[str, Any]], str]


def verify(
    verifier: Optional[Verifier], proposal: Dict[str, Any], result: Dict[str, Any]
) -> str:
    if verifier is None:
        return OUTCOME_CONFIRMED
    return verifier(proposal, result)
