"""Orphan entity rule."""
from metamart.quality.catalog import CatalogSnapshot
from metamart.quality.registry import registry
from metamart.quality.types import Dimension, Finding, Severity


@registry.register(
    rule_id="orphans.no_relationships",
    dimension=Dimension.ORPHANS,
    default_severity=Severity.WARN,
)
def no_relationships(catalog: CatalogSnapshot, params: dict) -> list[Finding]:
    connected: set[int] = set()
    for r in catalog.fk_relationships:
        connected.add(r.parent_obj_id)
        connected.add(r.child_obj_id)
    for ln in catalog.lineage_edges:
        connected.add(ln.source_obj_id)
        connected.add(ln.target_obj_id)

    findings: list[Finding] = []
    for e in catalog.entities:
        if e.is_standalone:
            continue
        if e.obj_id not in connected:
            findings.append(
                Finding(
                    rule_id="orphans.no_relationships",
                    dimension=Dimension.ORPHANS,
                    severity=Severity.WARN,
                    target_obj_id=e.obj_id,
                    message=f"Entity '{e.physical_name}' has no FK or lineage edges",
                    remediation="Connect via FK, mark as is_standalone, or remove",
                )
            )
    return findings
