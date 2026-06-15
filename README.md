<div align="center">

# Understudy

### *Watched, then trusted.*

**An earned autonomy trust gate for AI agents, delivered as an MCP server for Microsoft Copilot Cowork and Copilot.**

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![tests](https://img.shields.io/badge/tests-45%20passing-2ea44f?logo=pytest&logoColor=white)
![core deps](https://img.shields.io/badge/core%20deps-zero-2ea44f)
![protocol](https://img.shields.io/badge/protocol-MCP-7c3aed)
![status](https://img.shields.io/badge/status-working%20prototype-f59e0b)

</div>

![Understudy, from team to earned autonomy across the Copilot workflow](docs/hero.png)

> An understudy watches the lead, learns the role, and only goes on alone once they have earned it. Understudy does that for an AI agent. It watches how your team works, learns the playbook, and lets the agent act by itself only after it has repeatedly matched your team's judgment. The first time an autonomous action goes wrong, it pulls the agent straight back to asking a human.

**The one line version.** *Autonomy should be earned and revocable, not a switch someone flips in a config file and forgets.* Understudy turns that idea into a small, deterministic engine that any Copilot, Cowork, or CRM agent can call before it acts.

## The wall every team hits

Roll out an agent and you face the same bad choice on every single task. Keep a human approving everything, and you get no time back and reviewers who stop reading and rubber stamp. Or flip on full autonomy, and one wrong action becomes a real financial, legal, or reputational mess. There has never been an *evidence based* way to decide which work an agent has earned the right to do alone, judged by your standards, and no way to take that right back when it slips.

Understudy is the missing middle.

## How it thinks: the Understudy Loop

Plain prompting is a single shot. Understudy runs a *loop*, the way the builders of Copilot Cowork, Claude Code, and OpenClaw all argue modern agents should. Our loop takes the ReAct pattern of thought, action, and observation and adds the two things ReAct never had: a **deterministic trust gate** and a **learning step**. It is a chain of loops, not a chain of prompts.

![The Understudy Loop](docs/understudy_loop.png)

1. **Recall** the learned playbook for this task class.
2. **Reason** through a ReAct trace to a concrete proposal. *This is where chain of thought lives.*
3. **Appraise.** The deterministic gate scores trust and decides act or ask. *No model runs here.*
4. **Act or Defer.** Run it, or route it to a human.
5. **Observe** the real outcome.
6. **Evolve.** Fold the verdict and the outcome back into the playbook and the trust score.

It maps cleanly onto the human in the loop pattern: *machine flags, human decides, machine learns, human decides again.*

## Why it will not betray you

The learning part is probabilistic and never perfect. That is fine, because it is *always* bounded by the deterministic gate. Everything that matters for safety is plain code with no model in the path.

- Trust is the **lower bound of a Wilson score interval**, so three out of three is treated as weak evidence, not proof.
- A reviewer who approves everything *and* whose approvals do not hold up is down weighted. A rubber stamper cannot inflate trust.
- A confirmed autonomous action never raises trust, because that would be the agent grading itself. A *reverted* one counts as a lasting failure.
- High stakes classes such as hiring, privileged access, and large payments carry a **hard ceiling** and never reach full autonomy.
- Risk classification **fails closed**. An unknown money like field is treated as critical, never as low value.

### The part senior engineers will care about

Multi agent systems quietly corrupt shared state under load: two agents read a value, change it, write it back, and silently lose each other's work. Understudy treats agent memory like a distributed system. The event log is **append only** and is the single source of truth, so trust is folded from it on read and there is no counter to overwrite. Every write carries an **idempotency key**, so a retry never double counts. Materialized state uses **compare and set** with a safe retry, and concurrent updates merge by rule, not last write wins.

The proof harness fires three hundred concurrent writes:

```
naive read then write counter : 22 of 300   (most updates silently lost)
understudy versioned store     : 300 of 300
understudy event log           : 300 of 300, hash chain verified
```

## See it earn, and lose, autonomy

One task class, run repeatedly with a diligent reviewer and confirmed outcomes, then one bad outcome at t11:

```
t1..t8   ASK_ALWAYS       trust climbs 0.0 to 0.65   bootstrapping
t9       ASK_WHEN_UNSURE  trust 0.676
t10      AUTONOMOUS       trust 0.701                no human needed
t11      AUTONOMOUS       then the outcome is REVERTED
t12      ASK_ALWAYS       trust drops to 0.596       demoted at once
```

That is the whole thesis in twelve lines: *earn it, use it, lose it the moment it fails.*

## Install in one breath

The single command writes a ready MCP client config and picks which model serves each risk tier based on how hard you plan to lean on it.

```
pip install -e ".[mcp]"
understudy install --usage balanced
```

`balanced` sends low risk work to the fast model, standard work to the mid model, and high risk and reasoning heavy work to the strongest model. `light` and `heavy` shift that, and you can override any tier. Add the generated block to your Copilot, Copilot Studio, or other MCP client, or run it directly with `understudy serve-mcp`.

## Wire it into what you already run

Your agents and skills keep doing the work. They just route the risky step through the gate.

- `evaluate_gate(domain, verb, payload)` returns the autonomy level, whether a human is required, the trust score and target, the risk bucket, and the suggested model.
- `submit_verdict(task_id, bucket_key, reviewer_id, verdict, edit_distance)` records APPROVE, EDIT, or REJECT.
- `submit_outcome(task_id, bucket_key, outcome)` records CONFIRMED or REVERTED.
- `trust_snapshot(...)` reads trust without changing anything.
- `trust_matrix()` returns trust for every task class the gate has seen.

There is also a REST surface and a trust dial dashboard for an operations or IT lead: `pip install -e ".[api]"` then `understudy serve-api`.

## It rides on top of your skill files

Your teams already write skill files for Copilot Cowork and Copilot Studio, one per process, and those change for every company. *That is the right home for the work itself.* Understudy does not replace them. It is the trust and learning layer they call. A skill keeps describing how to draft the campaign or code the invoice. Before it commits the consequential step it calls `evaluate_gate`. Early on the gate says ask a human. As approvals stack up and outcomes hold, the *same skill, unchanged,* earns the right to run that step alone. Because it speaks MCP, the same gate works across the Copilot family and other agent runtimes that read the protocol.

## What it does for the business

- **Reclaim review time** as trust grows, without the risk of blind autonomy, and the shift is *measured, not guessed*.
- **Stop repeat mistakes.** A bad autonomous action is demoted at once, so one error does not become ten.
- **Answer the question every risk officer asks**, which is what exactly are the agents allowed to do, backed by a signed, tamper evident record.
- **Keep spend proportional to need**, since the router reserves the strongest model for the work that truly needs it.

## Project status, with no spin

Everything that is code is built and tested. The handful of items that need your own tenant, keys, or users are called out as exactly that, not hidden.

Built and tested (45 unit tests, the proof harness, the end to end demo all green):

- the deterministic core, the Understudy Loop, and the MCP server, which loads as a FastMCP server with its tools registered
- a CRM connector that routes writes through the gate, with a complete in memory reference adapter
- a live browser capture adapter for the Watcher, tested offline and ready to drive the Playwright MCP
- the real model client path, unit tested through an injected client
- a Copilot plugin packaging scaffold that assembles the Teams app bundle

Needs your resources, not more code:

- a live Copilot Cowork tenant to install the packaged plugin and to validate the manifest against the current preview schema
- credentials to point the CRM connector at a real Salesforce, HubSpot, or Dynamics instance
- a connected Playwright MCP to capture real browser sessions, and an API key to run the real model client
- real teams using it, to turn the simulated proofs into field data

## Run the proofs

Nothing here needs a network or a Copilot tenant.

```
python -m unittest discover -s tests -t .
understudy prove
understudy demo
```

## Map of the code

```
understudy/
  core/          deterministic engine, no model in the path
  crew/          the Understudy Loop agents, the ReAct engine, and browser capture
  integrations/  the CRM connector that routes writes through the gate
  mcp_server/    the MCP server, named to avoid shadowing the SDK
  api/           REST surface and trust dial dashboard
  packaging/     the Copilot plugin bundle builder
  simulations/   the proof harness and the end to end demo
  tests/         the unit suite
  cli.py         prove, demo, serve-mcp, serve-api, install
```

## Roadmap

- A Postgres backed event log for multi node deployments, behind the same interface the file backed log already implements.
- Connect the browser capture adapter to a live Playwright MCP, so playbooks are learned from real sessions.
- Real Salesforce, HubSpot, and Dynamics adapters behind the CRM connector interface.
- A tenant trial with the packaged plugin, to move from working prototype to field proven.

## Questions worth asking

**Is this another agent that does my work?** No. It decides how much your agents are trusted to do alone. Your skills still do the work.

**Will the autonomy ever do something reckless?** The deterministic gate is the only thing that can grant it, high stakes classes are capped so they never reach it, and a reverted outcome demotes the class immediately.

**Does it lock me into a vendor?** No. The core is plain Python with zero dependencies, storage is a simple append only log, and the surface is open MCP.

## License

MIT. Built and maintained by **Ahmed Raoofuddin**.
