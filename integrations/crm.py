"""A CRM connector that routes writes through the trust gate.

This is the pattern for CRM driven teams. Reads pass straight through. A write is
appraised first. If the task class has earned autonomy, the write runs and the
outcome is recorded. Otherwise it is held for a human and runs only after an
approve or edit verdict. InMemoryCrm is a complete reference adapter used in the
tests and local runs. A real Salesforce, HubSpot, or Dynamics adapter implements
the same two methods, read and write, against its own API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol

from core.event_log import OUTCOME_CONFIRMED, VERDICT_APPROVE, VERDICT_EDIT
from core.gatekeeper import Decision, Gatekeeper


class CrmConnector(Protocol):
    def read(self, entity: str, record_id: str) -> Dict[str, Any]: ...
    def write(self, entity: str, record_id: str, changes: Dict[str, Any]) -> Dict[str, Any]: ...


@dataclass
class InMemoryCrm:
    """A complete in process CRM, enough to run and test the gated flow end to end."""

    records: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def read(self, entity: str, record_id: str) -> Dict[str, Any]:
        return dict(self.records.get(entity + ":" + record_id, {}))

    def write(self, entity: str, record_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        key = entity + ":" + record_id
        current = self.records.get(key, {})
        current.update(changes)
        self.records[key] = current
        return dict(current)


@dataclass
class GatedWriteResult:
    applied: bool
    requires_human: bool
    decision: Decision
    record: Optional[Dict[str, Any]]


class GatedCrm:
    def __init__(self, crm: CrmConnector, gatekeeper: Gatekeeper, domain: str = "CRM") -> None:
        self.crm = crm
        self.gatekeeper = gatekeeper
        self.domain = domain

    def read(self, entity: str, record_id: str) -> Dict[str, Any]:
        return self.crm.read(entity, record_id)

    def appraise(self, verb: str, entity: str, record_id: str, changes: Dict[str, Any]) -> Decision:
        payload: Dict[str, Any] = {"entity": entity, "record_id": record_id}
        payload.update(changes)
        return self.gatekeeper.evaluate(self.domain, verb, payload)

    def write(
        self,
        task_id: str,
        verb: str,
        entity: str,
        record_id: str,
        changes: Dict[str, Any],
        reviewer_id: str,
        human_verdict: Optional[str] = None,
        edit_distance: float = 0.0,
    ) -> GatedWriteResult:
        decision = self.appraise(verb, entity, record_id, changes)

        if not decision.requires_human:
            record = self.crm.write(entity, record_id, changes)
            self.gatekeeper.record_outcome(task_id, decision.bucket_key, OUTCOME_CONFIRMED)
            return GatedWriteResult(True, False, decision, record)

        if human_verdict is None:
            return GatedWriteResult(False, True, decision, None)

        self.gatekeeper.record_verdict(
            task_id, decision.bucket_key, reviewer_id, human_verdict, edit_distance
        )
        if human_verdict in (VERDICT_APPROVE, VERDICT_EDIT):
            record = self.crm.write(entity, record_id, changes)
            self.gatekeeper.record_outcome(task_id, decision.bucket_key, OUTCOME_CONFIRMED)
            return GatedWriteResult(True, True, decision, record)

        return GatedWriteResult(False, True, decision, None)
