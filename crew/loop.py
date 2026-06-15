"""The Understudy Loop runner.

This runs the six phases in order: Recall, Reason, Appraise, Act or Defer,
Observe, Evolve. It runs fully offline with the deterministic model client, so
the whole framework can be exercised in tests without a model, a browser, or a
Copilot tenant. The same node functions are wired into LangGraph in graph.py for
production, where the gate becomes a durable interrupt.

Autonomy is earned through human verdicts and revoked through bad outcomes. When
a task runs autonomously there is no self approval. We record only the real
outcome, so a reverted autonomous action triggers a demotion on the next pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from core.event_log import (
    OUTCOME_CONFIRMED,
    VERDICT_APPROVE,
    VERDICT_EDIT,
    VERDICT_REJECT,
)
from core.gatekeeper import Gatekeeper
from crew.agents import appraiser, hands, inspector, mentor, planner
from crew.model_client import DeterministicModelClient
from crew.playbook import Playbook, PlaybookStore


@dataclass
class HumanVerdict:
    verdict: str
    edit_distance: float = 0.0


@dataclass
class LoopResult:
    task_id: str
    bucket_key: str
    autonomy_level: str
    requires_human: bool
    acted: bool
    verdict: Optional[str]
    outcome: Optional[str]
    trust_lower_bound: float
    proposal_summary: str


HumanGate = Callable[[Any, Dict[str, Any]], HumanVerdict]
Executor = Callable[[Dict[str, Any]], Dict[str, Any]]
Verifier = Callable[[Dict[str, Any], Dict[str, Any]], str]


class UnderstudyLoop:
    def __init__(
        self,
        gatekeeper: Gatekeeper,
        playbook_store: Optional[PlaybookStore] = None,
        model_client: Optional[object] = None,
        executor: Optional[Executor] = None,
        human_gate: Optional[HumanGate] = None,
        verifier: Optional[Verifier] = None,
    ) -> None:
        self.gatekeeper = gatekeeper
        self.playbooks = playbook_store or PlaybookStore()
        self.model_client = model_client or DeterministicModelClient()
        self.executor = executor or (lambda proposal: {"status": "done"})
        self.human_gate = human_gate
        self.verifier = verifier

    def confirm_playbook(self, playbook: Playbook) -> Playbook:
        playbook.confirmed = True
        return self.playbooks.upsert(playbook)

    def run_task(
        self, domain: str, verb: str, payload: Dict[str, Any], task_id: str, reviewer_id: str = "reviewer"
    ) -> LoopResult:
        playbook = self.playbooks.get(domain, verb)
        proposal = planner.propose(self.model_client, domain, verb, payload, playbook)
        proposal["task_id"] = task_id
        decision = appraiser.appraise(self.gatekeeper, domain, verb, payload)

        acted = False
        verdict: Optional[str] = None
        edit_distance = 0.0
        result: Dict[str, Any] = {"status": "skipped"}

        if decision.requires_human:
            human = self._ask_human(decision, proposal)
            verdict = human.verdict
            edit_distance = human.edit_distance
            if verdict in (VERDICT_APPROVE, VERDICT_EDIT):
                result = hands.execute(self.executor, proposal)
                acted = True
            else:
                result = {"status": "rejected"}
        else:
            result = hands.execute(self.executor, proposal)
            acted = True

        outcome: Optional[str] = None
        if acted:
            outcome = inspector.verify(self.verifier, proposal, result)

        mentor.evolve(
            self.gatekeeper, task_id, decision.bucket_key, reviewer_id, verdict, edit_distance, outcome
        )

        return LoopResult(
            task_id=task_id,
            bucket_key=decision.bucket_key,
            autonomy_level=decision.autonomy_level.name,
            requires_human=decision.requires_human,
            acted=acted,
            verdict=verdict,
            outcome=outcome,
            trust_lower_bound=decision.trust_lower_bound,
            proposal_summary=str(proposal.get("summary", "")),
        )

    def _ask_human(self, decision, proposal) -> HumanVerdict:
        if self.human_gate is None:
            return HumanVerdict(VERDICT_APPROVE, 0.0)
        return self.human_gate(decision, proposal)
