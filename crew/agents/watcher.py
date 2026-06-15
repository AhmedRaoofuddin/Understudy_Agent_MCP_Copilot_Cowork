"""Watcher: capture how a team does a task.

For now it records a demonstration as an ordered list of step descriptions. In
production it captures Cowork actions and browser actions through the Playwright
MCP and turns them into the same shape. Capture is deterministic.
"""

from __future__ import annotations

from typing import List


def capture(steps: List[str]) -> List[str]:
    return [step.strip() for step in steps if step and step.strip()]
