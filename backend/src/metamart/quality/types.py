"""Core types for the quality engine — findings, scoring weights, rule packs."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


class Dimension(str, Enum):
    NAMING = "naming"
    NORMALIZATION = "normalization"
    ORPHANS = "orphans"
    PKS = "pks"
    DATATYPES = "datatypes"
    GLOSSARY = "glossary"
    LINEAGE = "lineage"


SEVERITY_WEIGHTS: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.WARN: 1,
    Severity.ERROR: 3,
    Severity.CRITICAL: 10,
}


DEFAULT_WEIGHTS: dict[Dimension, float] = {
    Dimension.NAMING: 15.0,
    Dimension.NORMALIZATION: 15.0,
    Dimension.ORPHANS: 10.0,
    Dimension.PKS: 15.0,
    Dimension.DATATYPES: 15.0,
    Dimension.GLOSSARY: 15.0,
    Dimension.LINEAGE: 15.0,
}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    dimension: Dimension
    severity: Severity
    target_obj_id: int
    message: str
    remediation: str | None = None
    # Resolved by the engine after rules run — UI uses this for friendly
    # drill-down without re-walking the catalog. "Entity" or "Entity.attr".
    target_name: str | None = None


@dataclass(frozen=True)
class SubScore:
    dimension: Dimension
    score: float
    finding_count_by_severity: dict[Severity, int]
    population_size: int


@dataclass(frozen=True)
class ScanResult:
    model_obj_id: int
    version_id: int
    pack_id: str
    composite_score: float
    grade: str
    sub_scores: list[SubScore]
    findings: list[Finding]


@dataclass
class RuleConfig:
    """Per-pack override for a registered rule."""

    rule_id: str
    enabled: bool = True
    severity_override: Severity | None = None
    params_override: dict = field(default_factory=dict)


@dataclass
class RulePack:
    pack_id: str
    name: str
    use_geometric_mean: bool = False
    weights: dict[Dimension, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    rules: list[RuleConfig] = field(default_factory=list)
