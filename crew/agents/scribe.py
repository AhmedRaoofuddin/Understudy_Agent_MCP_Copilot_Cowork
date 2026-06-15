"""Scribe: turn demonstrations into an editable playbook draft.

This is the research hard part, so the output is always an editable draft that a
human confirms, never a hidden guess. The Scribe uses the model to order and
generalize the steps. With the deterministic client it returns a simple ordered
draft, which is enough to run the loop offline.
"""

from __future__ import annotations

from typing import List

from crew.playbook import Playbook

SCRIBE_SYSTEM = (
    "ROLE: scribe. Turn the demonstrations into an ordered, editable playbook. "
    "Return one line per step prefixed with STEP:."
)


def induce_playbook(
    model_client, domain: str, verb: str, demonstrations: List[List[str]]
) -> Playbook:
    flattened = "\n".join("- " + "; ".join(demo) for demo in demonstrations)
    prompt = (
        "Induce a reusable playbook for the task class "
        + domain + " " + verb + ".\n\nDemonstrations:\n" + flattened
    )
    raw = model_client.generate(SCRIBE_SYSTEM, prompt)

    steps: List[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("STEP:"):
            steps.append(stripped[len("STEP:") :].strip())

    if not steps and demonstrations:
        steps = list(demonstrations[0])

    return Playbook(domain=domain, verb=verb, steps=steps, confirmed=False)
