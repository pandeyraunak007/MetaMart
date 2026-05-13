"""Scoring math: sub-score per dimension, composite, letter grade."""
from __future__ import annotations

import math
from collections.abc import Sequence

from metamart.quality.types import (
    SEVERITY_WEIGHTS,
    Dimension,
    Finding,
    Severity,
)

# Tiny offset for geometric mean so a single 0 doesn't collapse the composite to 0.
_GEO_EPSILON = 0.01


def compute_sub_score(*, findings: Sequence[Finding], population_size: int) -> float:
    """sub_score = 100 × (1 − Σ(severity_weight × finding_count) / max_possible_penalty).

    `max_possible_penalty` = critical-weight × population_size (worst case: every
    population element produces a critical finding). Clamped to [0, 100].
    """
    if population_size <= 0:
        return 100.0
    max_penalty = SEVERITY_WEIGHTS[Severity.CRITICAL] * population_size
    if max_penalty <= 0:
        return 100.0
    penalty = sum(SEVERITY_WEIGHTS[f.severity] for f in findings)
    score = 100.0 * (1.0 - penalty / max_penalty)
    if score < 0.0:
        return 0.0
    if score > 100.0:
        return 100.0
    return score


def compute_composite(
    *,
    sub_scores: dict[Dimension, float],
    weights: dict[Dimension, float],
    use_geometric_mean: bool = False,
) -> float:
    """Weighted average (default) or weighted geometric mean of sub-scores.

    Geometric mean penalizes a single failing dimension harder than the weighted
    average and is opt-in per rule-pack.
    """
    if not sub_scores:
        return 0.0
    effective = {d: w for d, w in weights.items() if d in sub_scores and w > 0}
    if not effective:
        return 0.0

    weight_sum = sum(effective.values())

    if use_geometric_mean:
        log_sum = sum(
            w * math.log(sub_scores[d] + _GEO_EPSILON) for d, w in effective.items()
        )
        return math.exp(log_sum / weight_sum) - _GEO_EPSILON

    weighted_sum = sum(w * sub_scores[d] for d, w in effective.items())
    return weighted_sum / weight_sum


def letter_grade(composite: float) -> str:
    if composite >= 90:
        return "A"
    if composite >= 80:
        return "B"
    if composite >= 70:
        return "C"
    if composite >= 60:
        return "D"
    return "F"
