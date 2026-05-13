"""The engine: runs registered rules against a catalog snapshot and emits a ScanResult."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from sqlalchemy.orm import Session

from metamart.quality.catalog import CatalogSnapshot, read_catalog_at_version
from metamart.quality.registry import RuleRegistry
from metamart.quality.registry import registry as default_registry
from metamart.quality.scoring import compute_composite, compute_sub_score, letter_grade
from metamart.quality.types import (
    Dimension,
    Finding,
    RulePack,
    ScanResult,
    Severity,
    SubScore,
)


def score_catalog(
    catalog: CatalogSnapshot,
    pack: RulePack,
    *,
    rule_registry: RuleRegistry | None = None,
) -> ScanResult:
    """Pure, DB-free scoring path. Useful for unit tests and snapshot replay."""
    reg = rule_registry or default_registry
    cfg_by_id = {rc.rule_id: rc for rc in pack.rules}

    findings: list[Finding] = []
    for spec in reg.all():
        cfg = cfg_by_id.get(spec.rule_id)
        if cfg is not None and not cfg.enabled:
            continue
        params = {**spec.default_params, **(cfg.params_override if cfg else {})}
        rule_out = spec.func(catalog, params)
        if cfg is not None and cfg.severity_override is not None:
            rule_out = [replace(f, severity=cfg.severity_override) for f in rule_out]
        findings.extend(rule_out)

    findings_by_dim: dict[Dimension, list[Finding]] = defaultdict(list)
    for f in findings:
        findings_by_dim[f.dimension].append(f)

    sub_scores: list[SubScore] = []
    sub_score_by_dim: dict[Dimension, float] = {}
    for dim in Dimension:
        dim_findings = findings_by_dim.get(dim, [])
        pop = catalog.population_for_dimension(dim)
        score = compute_sub_score(findings=dim_findings, population_size=pop)
        counts = {s: sum(1 for f in dim_findings if f.severity == s) for s in Severity}
        sub_scores.append(
            SubScore(
                dimension=dim,
                score=score,
                finding_count_by_severity=counts,
                population_size=pop,
            )
        )
        sub_score_by_dim[dim] = score

    composite = compute_composite(
        sub_scores=sub_score_by_dim,
        weights=pack.weights,
        use_geometric_mean=pack.use_geometric_mean,
    )

    return ScanResult(
        model_obj_id=catalog.model_obj_id,
        version_id=catalog.version_id,
        pack_id=pack.pack_id,
        composite_score=composite,
        grade=letter_grade(composite),
        sub_scores=sub_scores,
        findings=findings,
    )


def run_scan(
    db: Session,
    *,
    model_obj_id: int,
    version_id: int,
    pack: RulePack,
    rule_registry: RuleRegistry | None = None,
) -> ScanResult:
    """DB-backed scan: read state at version, then score in memory."""
    catalog = read_catalog_at_version(
        db, model_obj_id=model_obj_id, version_id=version_id
    )
    return score_catalog(catalog, pack, rule_registry=rule_registry)
