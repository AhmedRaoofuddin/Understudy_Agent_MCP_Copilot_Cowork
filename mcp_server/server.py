"""The Understudy MCP server.

This exposes the deterministic trust gate to any MCP aware client: Microsoft
Copilot and Copilot Cowork, Copilot Studio agents, and other agent tools. A team
routes a consequential action through evaluate_gate before acting, records the
human verdict and the real outcome, and the gate decides when that task class has
earned the right to run on its own. The event log persists to a file, so the
server keeps its memory across restarts.

Run it with:  python -m mcp_server.server
"""

from __future__ import annotations

import os
from typing import Any, Dict

from core.event_log import FileEventLog
from core.gatekeeper import Gatekeeper
from crew.model_router import ModelRouter

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as error:  # pragma: no cover
    raise RuntimeError(
        "the mcp package is required to run the Understudy MCP server. "
        "Install it with: pip install mcp"
    ) from error


EVENT_LOG_PATH = os.environ.get("UNDERSTUDY_EVENT_LOG", "understudy_events.jsonl")

event_log = FileEventLog(EVENT_LOG_PATH)
gatekeeper = Gatekeeper(event_log)
model_router = ModelRouter.from_env()

server = FastMCP("understudy")


@server.tool()
def evaluate_gate(domain: str, verb: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Decide whether a proposed action can run on its own or must ask a human.

    Call this before any consequential action. It returns the autonomy level,
    whether a human is required, the trust score and target, the risk bucket, and
    the model tier that suits this task.
    """
    decision = gatekeeper.evaluate(domain, verb, payload)
    bucket = gatekeeper.classify(domain, verb, payload)
    return {
        "bucket_key": decision.bucket_key,
        "autonomy_level": decision.autonomy_level.name,
        "requires_human": decision.requires_human,
        "trust_lower_bound": round(decision.trust_lower_bound, 4),
        "target_confidence": decision.target_confidence,
        "task_count": decision.task_count,
        "failed_closed": decision.failed_closed,
        "reason": decision.reason,
        "suggested_model": model_router.model_for(bucket),
    }


@server.tool()
def submit_verdict(
    task_id: str,
    bucket_key: str,
    reviewer_id: str,
    verdict: str,
    edit_distance: float = 0.0,
) -> Dict[str, Any]:
    """Record a human verdict for a task. Verdict is APPROVE, EDIT, or REJECT."""
    recorded = gatekeeper.record_verdict(task_id, bucket_key, reviewer_id, verdict, edit_distance)
    return {"recorded": recorded}


@server.tool()
def submit_outcome(task_id: str, bucket_key: str, outcome: str) -> Dict[str, Any]:
    """Record the real outcome of an action. Outcome is CONFIRMED or REVERTED."""
    recorded = gatekeeper.record_outcome(task_id, bucket_key, outcome)
    return {"recorded": recorded}


@server.tool()
def trust_snapshot(domain: str, verb: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Read the current trust for a task class without changing any state."""
    decision = gatekeeper.evaluate(domain, verb, payload)
    return {
        "bucket_key": decision.bucket_key,
        "trust_lower_bound": round(decision.trust_lower_bound, 4),
        "target_confidence": decision.target_confidence,
        "autonomy_level": decision.autonomy_level.name,
        "task_count": decision.task_count,
    }


@server.tool()
def trust_matrix() -> Dict[str, Any]:
    """Return the trust reading for every task class the gate has seen."""
    return {"rows": gatekeeper.list_trust()}


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
