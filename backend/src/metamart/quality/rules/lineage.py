"""Lineage completeness rule."""
from metamart.quality.catalog import CatalogSnapshot
from metamart.quality.registry import registry
from metamart.quality.types import Dimension, Finding, Severity

WAREHOUSE_PREFIXES = ("fact_", "dim_", "mart_")


@registry.register(
    rule_id="lineage.missing_inbound",
    dimension=Dimension.LINEAGE,
    default_severity=Severity.ERROR,
)
def missing_inbound(catalog: CatalogSnapshot, params: dict) -> list[Finding]:
    """Warehouse-style entities (fact_/dim_/mart_ prefix) should have ≥1 inbound
    lineage edge. v1 heuristic: prefix-based; a future rule pack can configure
    via params {"warehouse_prefixes": [...]} or by reading UDPs."""
    prefixes = tuple(params.get("warehouse_prefixes", WAREHOUSE_PREFIXES))
    inbound_targets: set[int] = {ln.target_obj_id for ln in catalog.lineage_edges}

    findings: list[Finding] = []
    for e in catalog.entities:
        if not e.physical_name.lower().startswith(prefixes):
            continue
        if e.obj_id not in inbound_targets:
            findings.append(
                Finding(
                    rule_id="lineage.missing_inbound",
                    dimension=Dimension.LINEAGE,
                    severity=Severity.ERROR,
                    target_obj_id=e.obj_id,
                    message=(
                        f"Warehouse entity '{e.physical_name}' has no inbound lineage edge"
                    ),
                    remediation="Trace the upstream source(s) populating this entity",
                )
            )
    return findings
