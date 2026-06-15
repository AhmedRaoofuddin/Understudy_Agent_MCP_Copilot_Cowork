"""Planner: produce a concrete proposal by reasoning over the playbook.

The Planner runs on the ReAct engine. It reads the confirmed playbook for the
task class and the current payload, reasons through a short trace, and returns a
proposal the Gatekeeper can appraise and the Hands can execute.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from crew.playbook import Playbook
from crew.reasoning import ReActEngine

PLANNER_SYSTEM = (
    "ROLE: planner. Produce a concrete proposal by following the confirmed "
    "playbook for this task class. Reply with THOUGHT then FINAL."
)


def propose(
    model_client,
    domain: str,
    verb: str,
    payload: Dict[str, Any],
    playbook: Optional[Playbook],
) -> Dict[str, Any]:
    engine = ReActEngine(model_client, tools={}, max_steps=3)
    steps_text = "; ".join(playbook.steps) if playbook and playbook.steps else "no playbook yet"
    task = "Propose how to carry out this " + domain + " " + verb + " task."
    context = "Payload: " + str(payload) + "\nPlaybook steps: " + steps_text
    trace = engine.run(PLANNER_SYSTEM, task, context)

    return {
        "summary": trace.final_answer,
        "domain": domain,
        "verb": verb,
        "payload": payload,
        "steps": list(playbook.steps) if playbook else [],
        "reasoning_steps": len(trace.steps),
    }
