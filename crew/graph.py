"""LangGraph adapter for the Understudy Loop (production path).

The offline runner in loop.py proves the framework with no dependencies. In
production we wire the same node functions into a LangGraph StateGraph so we get
durable state, retries, and a real human interrupt at the Appraise gate. This
module imports langgraph lazily, so importing the rest of the project never
requires it. Install langgraph to use build_graph.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TypedDict

from core.gatekeeper import Gatekeeper
from crew.agents import appraiser, hands, inspector, mentor, planner
from crew.model_client import DeterministicModelClient
from crew.playbook import PlaybookStore


class LoopState(TypedDict, total=False):
    domain: str
    verb: str
    payload: Dict[str, Any]
    task_id: str
    reviewer_id: str
    proposal: Dict[str, Any]
    decision: Any
    requires_human: bool
    verdict: Optional[str]
    edit_distance: float
    result: Dict[str, Any]
    acted: bool
    outcome: Optional[str]


def build_graph(
    gatekeeper: Gatekeeper,
    playbook_store: Optional[PlaybookStore] = None,
    model_client: Optional[object] = None,
    executor=None,
    checkpointer=None,
):
    """Build and compile the Understudy Loop as a LangGraph StateGraph.

    The gate node calls interrupt when a human decision is needed, which pauses
    the run and resumes it after the human responds. This is the production form
    of the Appraise step.
    """
    try:
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import interrupt
    except ImportError as error:
        raise RuntimeError(
            "langgraph is required for build_graph. Install it, or use "
            "crew.loop.UnderstudyLoop for the dependency free runner."
        ) from error

    store = playbook_store or PlaybookStore()
    client = model_client or DeterministicModelClient()
    run_executor = executor or (lambda proposal: {"status": "done"})

    def recall_and_reason(state: LoopState) -> LoopState:
        playbook = store.get(state["domain"], state["verb"])
        proposal = planner.propose(
            client, state["domain"], state["verb"], state["payload"], playbook
        )
        return {"proposal": proposal}

    def appraise(state: LoopState) -> LoopState:
        decision = appraiser.appraise(
            gatekeeper, state["domain"], state["verb"], state["payload"]
        )
        return {"decision": decision, "requires_human": decision.requires_human}

    def human_gate(state: LoopState) -> LoopState:
        human = interrupt(
            {
                "reason": state["decision"].reason,
                "bucket_key": state["decision"].bucket_key,
                "proposal": state["proposal"],
            }
        )
        return {
            "verdict": human.get("verdict"),
            "edit_distance": float(human.get("edit_distance", 0.0)),
        }

    def act(state: LoopState) -> LoopState:
        result = hands.execute(run_executor, state["proposal"])
        return {"result": result, "acted": True}

    def observe_and_evolve(state: LoopState) -> LoopState:
        outcome = inspector.verify(None, state["proposal"], state.get("result", {})) if state.get("acted") else None
        mentor.evolve(
            gatekeeper,
            state["task_id"],
            state["decision"].bucket_key,
            state.get("reviewer_id", "reviewer"),
            state.get("verdict"),
            float(state.get("edit_distance", 0.0)),
            outcome,
        )
        return {"outcome": outcome}

    def route_after_appraise(state: LoopState) -> str:
        return "human_gate" if state.get("requires_human") else "act"

    graph = StateGraph(LoopState)
    graph.add_node("recall_and_reason", recall_and_reason)
    graph.add_node("appraise", appraise)
    graph.add_node("human_gate", human_gate)
    graph.add_node("act", act)
    graph.add_node("observe_and_evolve", observe_and_evolve)

    graph.add_edge(START, "recall_and_reason")
    graph.add_edge("recall_and_reason", "appraise")
    graph.add_conditional_edges("appraise", route_after_appraise, ["human_gate", "act"])
    graph.add_edge("human_gate", "act")
    graph.add_edge("act", "observe_and_evolve")
    graph.add_edge("observe_and_evolve", END)

    return graph.compile(checkpointer=checkpointer)
