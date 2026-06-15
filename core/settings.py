"""Tunable settings for the trust engine.

These values are deliberately conservative. They control how much evidence the
engine needs before it lets an agent act on its own, and how aggressively it
discounts a reviewer who approves almost everything.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    z_score: float = 1.96
    min_samples_to_judge: int = 8
    uncertain_band_ratio: float = 0.8
    reviewer_min_reviews: int = 8
    rubber_stamp_threshold: float = 0.9
    rubber_stamp_min_weight: float = 0.2
    rubber_stamp_reversal_floor: float = 0.1
    recent_window: int = 3


DEFAULT_SETTINGS = Settings()
