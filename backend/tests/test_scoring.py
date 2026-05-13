"""Unit tests for sub-score, composite, and letter-grade math."""
import math

from metamart.quality.scoring import (
    compute_composite,
    compute_sub_score,
    letter_grade,
)
from metamart.quality.types import DEFAULT_WEIGHTS, Dimension, Finding, Severity


def _f(severity: Severity, *, dim: Dimension = Dimension.NAMING) -> Finding:
    return Finding(
        rule_id="x",
        dimension=dim,
        severity=severity,
        target_obj_id=1,
        message="m",
    )


def test_subscore_perfect_when_no_findings() -> None:
    assert compute_sub_score(findings=[], population_size=10) == 100.0


def test_subscore_zero_population_is_perfect() -> None:
    assert compute_sub_score(findings=[], population_size=0) == 100.0


def test_subscore_info_findings_do_not_penalize() -> None:
    score = compute_sub_score(findings=[_f(Severity.INFO)] * 5, population_size=10)
    assert score == 100.0


def test_subscore_orders_by_severity_weight() -> None:
    pop = 10
    score_warn = compute_sub_score(findings=[_f(Severity.WARN)], population_size=pop)
    score_err = compute_sub_score(findings=[_f(Severity.ERROR)], population_size=pop)
    score_crit = compute_sub_score(findings=[_f(Severity.CRITICAL)], population_size=pop)
    assert 100.0 > score_warn > score_err > score_crit > 0.0


def test_subscore_clamps_to_zero() -> None:
    # Many criticals against a small population should saturate to 0.
    findings = [_f(Severity.CRITICAL)] * 20
    assert compute_sub_score(findings=findings, population_size=10) == 0.0


def test_composite_weighted_average_uniform() -> None:
    sub = {d: 80.0 for d in Dimension}
    comp = compute_composite(sub_scores=sub, weights=DEFAULT_WEIGHTS)
    assert math.isclose(comp, 80.0)


def test_composite_weighted_average_respects_weights() -> None:
    sub = {Dimension.NAMING: 100.0, Dimension.PKS: 0.0}
    weights = {Dimension.NAMING: 90.0, Dimension.PKS: 10.0}
    comp = compute_composite(sub_scores=sub, weights=weights)
    assert math.isclose(comp, 90.0)


def test_composite_geometric_mean_penalizes_low_dim_harder() -> None:
    sub = {d: 100.0 for d in Dimension}
    sub[Dimension.PKS] = 0.0
    wa = compute_composite(sub_scores=sub, weights=DEFAULT_WEIGHTS)
    gm = compute_composite(
        sub_scores=sub, weights=DEFAULT_WEIGHTS, use_geometric_mean=True
    )
    assert gm < wa


def test_letter_grade_boundaries() -> None:
    assert letter_grade(95) == "A"
    assert letter_grade(90) == "A"
    assert letter_grade(89.999) == "B"
    assert letter_grade(80) == "B"
    assert letter_grade(79.999) == "C"
    assert letter_grade(70) == "C"
    assert letter_grade(60) == "D"
    assert letter_grade(59.999) == "F"
    assert letter_grade(0) == "F"
