"""The crew: the agents that run the Understudy Loop.

The Understudy Loop is our reasoning framework. It extends ReAct with a trust
gate and a learning step, and it maps one to one onto the human in the loop
diagram (machine flags, human decides, machine learns, human decides again).

The six phases per task:

  Recall   load the learned playbook for this task class.
  Reason   use a ReAct trace to produce a concrete proposal.
  Appraise the deterministic Gatekeeper scores trust and decides act or ask.
  Act      perform the action, autonomously or after a human approves.
  Observe  the Inspector verifies the real outcome.
  Evolve   the Mentor folds the verdict and outcome into the playbook and trust.

Recall, Reason, and the optional model calls are the only fuzzy parts, and they
are always bounded by the deterministic Appraise gate from the core package.
"""

__all__ = ["loop", "playbook", "reasoning", "model_client", "state"]
