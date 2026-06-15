"""Hands: execute an approved proposal through an injected executor.

In production the executor calls Cowork through MCP, or a browser through the
Playwright MCP. In tests it is a simple function. Keeping execution behind an
injected callable means the loop never hard codes a side effect.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

Executor = Callable[[Dict[str, Any]], Dict[str, Any]]


def execute(executor: Executor, proposal: Dict[str, Any]) -> Dict[str, Any]:
    return executor(proposal)
