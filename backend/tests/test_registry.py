"""Behavior tests for the rule registry."""
import pytest

from metamart.quality.registry import RuleRegistry
from metamart.quality.types import Dimension, Severity


def test_register_and_lookup() -> None:
    reg = RuleRegistry()

    @reg.register(rule_id="t.rule", dimension=Dimension.NAMING, default_severity=Severity.WARN)
    def my_rule(catalog, params):  # noqa: ARG001
        return []

    spec = reg.get("t.rule")
    assert spec.rule_id == "t.rule"
    assert spec.dimension == Dimension.NAMING
    assert spec.default_severity == Severity.WARN
    assert spec.func is my_rule


def test_register_duplicate_raises() -> None:
    reg = RuleRegistry()

    @reg.register(rule_id="dup", dimension=Dimension.NAMING)
    def a(catalog, params):  # noqa: ARG001
        return []

    with pytest.raises(ValueError):
        @reg.register(rule_id="dup", dimension=Dimension.NAMING)
        def b(catalog, params):  # noqa: ARG001
            return []


def test_all_returns_registered_rules() -> None:
    reg = RuleRegistry()

    @reg.register(rule_id="r1", dimension=Dimension.NAMING)
    def r1(catalog, params):  # noqa: ARG001
        return []

    @reg.register(rule_id="r2", dimension=Dimension.PKS)
    def r2(catalog, params):  # noqa: ARG001
        return []

    ids = {s.rule_id for s in reg.all()}
    assert ids == {"r1", "r2"}


def test_clear_drops_registrations() -> None:
    reg = RuleRegistry()

    @reg.register(rule_id="r", dimension=Dimension.NAMING)
    def r(catalog, params):  # noqa: ARG001
        return []

    reg.clear()
    assert reg.all() == []
