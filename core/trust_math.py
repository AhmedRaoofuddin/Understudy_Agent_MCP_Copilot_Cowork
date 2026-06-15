"""The trust math: the Wilson score lower bound.

We score how often an agent matches the team human judgment, but we never use
the raw success rate. A raw rate of three out of three looks perfect yet means
almost nothing. The Wilson lower bound is conservative with small samples, so a
task class only earns autonomy after enough evidence. Successes and sample size
are floats here, because each verdict is weighted by reviewer quality and by the
real outcome (see projections).
"""

from __future__ import annotations

import math


def wilson_lower_bound(successes: float, sample_size: float, z_score: float = 1.96) -> float:
    """Return the lower bound of the Wilson score interval, clamped to zero and one.

    With a tiny sample the bound sits well below the observed rate. As clean
    evidence accumulates the bound rises toward the rate. A high risk task class
    therefore needs many clean samples before the bound clears its threshold.
    """
    if sample_size <= 0:
        return 0.0

    observed_rate = successes / sample_size
    z_squared = z_score * z_score

    denominator = 1.0 + z_squared / sample_size
    center = observed_rate + z_squared / (2.0 * sample_size)
    spread = z_score * math.sqrt(
        (observed_rate * (1.0 - observed_rate) + z_squared / (4.0 * sample_size)) / sample_size
    )

    lower_bound = (center - spread) / denominator
    return max(0.0, min(lower_bound, 1.0))
