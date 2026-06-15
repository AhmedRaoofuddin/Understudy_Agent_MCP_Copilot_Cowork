"""End to end demo of the Understudy Loop running offline.

It shows the whole earned autonomy story on one low risk task class:

  watch a couple of demonstrations, induce a playbook, confirm it,
  then run the same task repeatedly with a diligent reviewer who approves and
  outcomes that confirm. The loop walks up the ladder from ask always, through
  ask when unsure, to autonomous. Then one autonomous action is reverted, and
  the loop immediately demotes the class back to a human gate.

Run it with:  python understudy/simulations/crew_demo.py
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.event_log import OUTCOME_CONFIRMED, OUTCOME_REVERTED, VERDICT_APPROVE, EventLog  # noqa: E402
from core.gatekeeper import Gatekeeper  # noqa: E402
from crew.agents import scribe, watcher  # noqa: E402
from crew.loop import HumanVerdict, UnderstudyLoop  # noqa: E402
from crew.model_client import DeterministicModelClient  # noqa: E402
from crew.playbook import PlaybookStore  # noqa: E402

PASSED = 0
FAILED = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    mark = "PASS" if condition else "FAIL"
    if condition:
        PASSED += 1
    else:
        FAILED += 1
    suffix = ("  " + detail) if detail else ""
    print("  [" + mark + "] " + label + suffix)


def main() -> int:
    print("Understudy Loop end to end demo")
    print("===============================")

    model = DeterministicModelClient()
    store = PlaybookStore()
    gate = Gatekeeper(EventLog())

    domain, verb = "MARKETING", "CREATE"
    payload = {"campaign": "spring", "segment": "smb"}

    demo_one = watcher.capture(["open the brief", "draft the post", "apply the brand voice", "queue it"])
    demo_two = watcher.capture(["open the brief", "draft the post", "apply the brand voice", "queue it"])
    draft = scribe.induce_playbook(model, domain, verb, [demo_one, demo_two])

    def always_approve(decision, proposal) -> HumanVerdict:
        return HumanVerdict(VERDICT_APPROVE, 0.0)

    def verifier(proposal, result) -> str:
        return OUTCOME_REVERTED if proposal.get("task_id") == "t11" else OUTCOME_CONFIRMED

    loop = UnderstudyLoop(
        gatekeeper=gate,
        playbook_store=store,
        model_client=model,
        executor=lambda proposal: {"status": "published"},
        human_gate=always_approve,
        verifier=verifier,
    )
    loop.confirm_playbook(draft)
    print("  playbook confirmed with steps: " + " | ".join(draft.steps))
    print()

    results = {}
    for index in range(1, 15):
        task_id = "t" + str(index)
        result = loop.run_task(domain, verb, payload, task_id, reviewer_id="diligent_dana")
        results[task_id] = result
        print(
            "  "
            + task_id.ljust(4)
            + " level=" + result.autonomy_level.ljust(16)
            + " human=" + str(result.requires_human).ljust(6)
            + " trust=" + str(round(result.trust_lower_bound, 3)).ljust(6)
            + " outcome=" + str(result.outcome)
        )

    print()
    check("first run asks a human", results["t1"].requires_human is True)
    check("first run is bootstrapping", results["t1"].autonomy_level == "ASK_ALWAYS")

    graduated = any(not results["t" + str(i)].requires_human for i in range(1, 11))
    check("the class graduates to autonomous before the reversal", graduated)

    reverted_autonomously = (
        results["t11"].requires_human is False and results["t11"].outcome == OUTCOME_REVERTED
    )
    check("the reverted action ran autonomously", reverted_autonomously)

    check("the class is demoted right after the reversal", results["t12"].requires_human is True)

    print("\nResult: " + str(PASSED) + " passed, " + str(FAILED) + " failed")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
