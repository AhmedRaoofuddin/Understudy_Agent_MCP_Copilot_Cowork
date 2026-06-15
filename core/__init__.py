"""Understudy core: the deterministic safety engine.

No module in this package calls a model. Every decision here is plain,
reproducible computation: risk bucketing, trust math, the append only event
log, the concurrency layer, and the ask versus act gate. The probabilistic
parts of the product (learning a team playbook) live in the crew package and
are always bounded by this core.
"""

__version__ = "0.1.0"
