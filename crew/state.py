"""The shared task state that flows through the Understudy Loop.

This is a plain dataclass so the loop runs with no external dependency. At the
MCP and API boundary the same fields are validated with Pydantic, where typed
request models are worth their dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from core.gatekeeper import Decision


@dataclass
class TaskState:
    domain: str
    verb: str
    payload: Dict[str, Any]
    task_id: str
    reviewer_id: str = "reviewer"
    proposal: Optional[Dict[str, Any]] = None
    decision: Optional[Decision] = None
    result: Optional[Dict[str, Any]] = None
    verdict: Optional[str] = None
    edit_distance: float = 0.0
    outcome: Optional[str] = None
    acted: bool = False
    notes: Dict[str, Any] = field(default_factory=dict)
