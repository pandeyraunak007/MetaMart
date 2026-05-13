"""Plugin-style rule registry.

Rules are functions `(catalog: CatalogSnapshot, params: dict) -> list[Finding]`
registered via the `@registry.register(...)` decorator. The engine walks
`registry.all()` and produces findings.

Optional companion: each rule may register an `auto_fix` function via
`@registry.register_fix(rule_id=...)`. Given a finding and the user's raw
catalog dict, the fix returns a patched catalog plus a human-readable
description (or None if it can't fix this particular instance).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from metamart.quality.types import Dimension, Severity

if TYPE_CHECKING:
    from metamart.quality.catalog import CatalogSnapshot
    from metamart.quality.types import Finding


RuleFunc = Callable[["CatalogSnapshot", dict], list["Finding"]]
# (catalog_dict, finding, snapshot) -> (patched_catalog | None, description).
# Returning None means "this finding isn't actually fixable in context"
# (e.g. the violation already self-resolved or required state isn't there).
FixFunc = Callable[
    [dict, "Finding", "CatalogSnapshot"],
    tuple[dict | None, str],
]


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    dimension: Dimension
    func: RuleFunc
    default_severity: Severity
    default_params: dict


class RuleRegistry:
    def __init__(self) -> None:
        self._rules: dict[str, RuleSpec] = {}
        self._fixers: dict[str, FixFunc] = {}

    def register(
        self,
        *,
        rule_id: str,
        dimension: Dimension,
        default_severity: Severity = Severity.WARN,
        default_params: dict | None = None,
    ) -> Callable[[RuleFunc], RuleFunc]:
        def decorator(func: RuleFunc) -> RuleFunc:
            if rule_id in self._rules:
                raise ValueError(f"Rule '{rule_id}' is already registered")
            self._rules[rule_id] = RuleSpec(
                rule_id=rule_id,
                dimension=dimension,
                func=func,
                default_severity=default_severity,
                default_params=default_params or {},
            )
            return func

        return decorator

    def register_fix(self, *, rule_id: str) -> Callable[[FixFunc], FixFunc]:
        def decorator(func: FixFunc) -> FixFunc:
            if rule_id in self._fixers:
                raise ValueError(f"Fixer for '{rule_id}' is already registered")
            self._fixers[rule_id] = func
            return func

        return decorator

    def fixer(self, rule_id: str) -> FixFunc | None:
        return self._fixers.get(rule_id)

    def has_fixer(self, rule_id: str) -> bool:
        return rule_id in self._fixers

    def get(self, rule_id: str) -> RuleSpec:
        return self._rules[rule_id]

    def all(self) -> list[RuleSpec]:
        return list(self._rules.values())

    def clear(self) -> None:
        self._rules.clear()
        self._fixers.clear()


# Global registry. M4's rule modules decorate against this.
registry = RuleRegistry()
