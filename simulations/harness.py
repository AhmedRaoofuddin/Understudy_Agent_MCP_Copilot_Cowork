"""The proof harness for the deterministic core.

This script needs no external libraries and no Copilot tenant. It runs five
scenarios that prove the trust engine behaves correctly under the conditions
that break naive implementations:

  1. A rubber stamping reviewer whose approvals get reverted does not inflate
     trust, so the task class stays gated.
  2. An unknown money like field fails closed to the critical tier instead of
     being mistaken for a low value action.
  3. A critical task class needs a large amount of clean evidence before it
     graduates, not a handful of approvals.
  4. A high volume low risk task class does graduate after enough clean,
     outcome confirmed approvals.
  5. Under concurrent load the append only log and the versioned store lose no
     updates, and a replayed idempotency key is not double counted, while a
     naive read then write counter does lose updates.

Run it with:  python understudy/simulations/harness.py
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.concurrency import VersionedStore, add_counter, idempotency_key  # noqa: E402
from core.event_log import (  # noqa: E402
    OUTCOME_CONFIRMED,
    OUTCOME_REVERTED,
    VERDICT_APPROVE,
    EventLog,
)
from core.gatekeeper import Gatekeeper  # noqa: E402
from core.risk_policy import AutonomyLevel  # noqa: E402

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


def seed_task(
    gate: Gatekeeper,
    task_id: str,
    bucket_key: str,
    reviewer: str,
    verdict: str,
    outcome: str,
    edit_distance: float = 0.0,
) -> None:
    gate.record_verdict(task_id, bucket_key, reviewer, verdict, edit_distance)
    gate.record_outcome(task_id, bucket_key, outcome)


def scenario_rubber_stamp_stays_gated() -> None:
    print("\nScenario 1: a rubber stamper with reverted outcomes stays gated")
    gate = Gatekeeper(EventLog())
    domain, verb, payload = "ACCOUNTS", "UPDATE", {"amount": 250}
    bucket_key = gate.classify(domain, verb, payload).key

    for index in range(30):
        outcome = OUTCOME_REVERTED if index < 12 else OUTCOME_CONFIRMED
        seed_task(gate, "rs_" + str(index), bucket_key, "rubber_rick", VERDICT_APPROVE, outcome)

    decision = gate.evaluate(domain, verb, payload)
    print(
        "    trust="
        + str(round(decision.trust_lower_bound, 3))
        + " target="
        + str(decision.target_confidence)
        + " level="
        + decision.autonomy_level.name
    )
    check(
        "stays gated despite thirty approvals",
        decision.autonomy_level != AutonomyLevel.AUTONOMOUS,
        "reason: " + decision.reason,
    )


def scenario_unknown_field_fails_closed() -> None:
    print("\nScenario 2: an unknown money like field fails closed to critical")
    gate = Gatekeeper(EventLog())
    domain, verb, payload = "ACCOUNTS", "PAY", {"contract_value": 5_000_000}
    bucket = gate.classify(domain, verb, payload)
    decision = gate.evaluate(domain, verb, payload)
    print("    bucket=" + bucket.key + " failed_closed=" + str(bucket.failed_closed))
    check("failed closed on the unknown field", bucket.failed_closed)
    check("treated as the critical target", decision.target_confidence == 0.96)


def scenario_critical_needs_many_samples() -> None:
    print("\nScenario 3: a critical class needs a lot of clean evidence")
    domain, verb, payload = "ACCOUNTS", "UPDATE", {"amount": 145_000}

    gate_small = Gatekeeper(EventLog())
    bucket_key = gate_small.classify(domain, verb, payload).key
    for index in range(15):
        seed_task(gate_small, "c15_" + str(index), bucket_key, "diligent_dana", VERDICT_APPROVE, OUTCOME_CONFIRMED)
    small = gate_small.evaluate(domain, verb, payload)
    print("    after 15 clean approvals: trust=" + str(round(small.trust_lower_bound, 3)) + " level=" + small.autonomy_level.name)
    check("not autonomous on a small sample", small.autonomy_level != AutonomyLevel.AUTONOMOUS)

    gate_large = Gatekeeper(EventLog())
    for index in range(150):
        seed_task(gate_large, "c150_" + str(index), bucket_key, "diligent_dana", VERDICT_APPROVE, OUTCOME_CONFIRMED)
    large = gate_large.evaluate(domain, verb, payload)
    print("    after 150 clean approvals: trust=" + str(round(large.trust_lower_bound, 3)) + " level=" + large.autonomy_level.name)
    check("graduates after enough clean evidence", large.autonomy_level == AutonomyLevel.AUTONOMOUS)


def scenario_low_risk_graduates() -> None:
    print("\nScenario 4: a high volume low risk class graduates")
    gate = Gatekeeper(EventLog())
    domain, verb, payload = "MARKETING", "CREATE", {"campaign": "spring", "segment": "smb"}
    bucket_key = gate.classify(domain, verb, payload).key
    for index in range(12):
        seed_task(gate, "lr_" + str(index), bucket_key, "marketing_mae", VERDICT_APPROVE, OUTCOME_CONFIRMED)
    decision = gate.evaluate(domain, verb, payload)
    print("    trust=" + str(round(decision.trust_lower_bound, 3)) + " target=" + str(decision.target_confidence) + " level=" + decision.autonomy_level.name)
    check("graduates on a modest bar", decision.autonomy_level == AutonomyLevel.AUTONOMOUS)


def scenario_concurrency_no_lost_updates() -> None:
    print("\nScenario 5: concurrent load loses no updates")
    total = 300

    naive_counter = {"value": 0}

    def naive_increment(_: int) -> None:
        current = naive_counter["value"]
        time.sleep(0.0002)
        naive_counter["value"] = current + 1

    store = VersionedStore()

    def safe_increment(_: int) -> None:
        store.update_with_retry("count", lambda value: add_counter(value, 1))

    log = EventLog()

    def append_event(index: int) -> None:
        log.append("evt_" + str(index), "BUCKET", "VERDICT", "task_" + str(index), {"i": index})

    with ThreadPoolExecutor(max_workers=32) as pool:
        list(pool.map(naive_increment, range(total)))
        list(pool.map(safe_increment, range(total)))
        list(pool.map(append_event, range(total)))

    _, safe_value = store.get("count")
    print("    naive counter=" + str(naive_counter["value"]) + " of " + str(total) + " (read then write loses updates)")
    print("    versioned store=" + str(safe_value) + " of " + str(total))
    print("    event log count=" + str(log.count()) + " of " + str(total))

    check("versioned store loses no updates", safe_value == total)
    check("event log loses no updates", log.count() == total)
    check("hash chain verifies", log.verify_chain())

    duplicate_appended = log.append("evt_0", "BUCKET", "VERDICT", "task_0", {"i": 0})
    check("replayed idempotency key is ignored", duplicate_appended is False and log.count() == total)


def main() -> int:
    print("Understudy core proof harness")
    print("=============================")
    scenario_rubber_stamp_stays_gated()
    scenario_unknown_field_fails_closed()
    scenario_critical_needs_many_samples()
    scenario_low_risk_graduates()
    scenario_concurrency_no_lost_updates()

    print("\nResult: " + str(PASSED) + " passed, " + str(FAILED) + " failed")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
