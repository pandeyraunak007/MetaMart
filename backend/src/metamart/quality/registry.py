"""Plugin-style rule registry.

Rules are functions `(catalog: CatalogSnapshot, params: dict) -> list[Finding]`
registered via the `@registry.register(...)` decorator. The engine walks
`registry.all()` and produces findings.
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

    def get(self, rule_id: str) -> RuleSpec:
        return self._rules[rule_id]

    def all(self) -> list[RuleSpec]:
        return list(self._rules.values())

    def clear(self) -> None:
        self._rules.clear()


# Global registry. M4's rule modules decorate against this.
registry = RuleRegistry()
