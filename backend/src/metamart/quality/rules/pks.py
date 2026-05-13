"""Missing primary key rule."""
from metamart.quality.catalog import CatalogSnapshot
from metamart.quality.registry import registry
from metamart.quality.types import Dimension, Finding, Severity


@registry.register(
    rule_id="pks.missing_pk",
    dimension=Dimension.PKS,
    default_severity=Severity.ERROR,
)
def missing_pk(catalog: CatalogSnapshot, params: dict) -> list[Finding]:
    findings: list[Finding] = []
    for e in catalog.entities:
        if e.is_view or e.is_staging:
            continue
        if not any(k.key_type == "PK" for k in e.keys):
            findings.append(
                Finding(
                    rule_id="pks.missing_pk",
                    dimension=Dimension.PKS,
                    severity=Severity.ERROR,
                    target_obj_id=e.obj_id,
                    message=f"Entity '{e.physical_name}' has no primary key",
                    remediation="Define a PK, or tag the entity as a view/staging if appropriate",
                )
            )
    return findings
