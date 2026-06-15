"""Appraiser: the deterministic trust gate.

This is the Appraise step. It delegates to the core Gatekeeper, which scores
trust from the event log and decides whether the proposal can run on its own or
must go to a human. No model runs here, so the decision is reproducible.
"""

from __future__ import annotations

from typing import Any, Dict

from core.gatekeeper import Decision, Gatekeeper


def appraise(gatekeeper: Gatekeeper, domain: str, verb: str, payload: Dict[str, Any]) -> Decision:
    return gatekeeper.evaluate(domain, verb, payload)
