"""Glossary coverage rule. Entities only in v1; attribute coverage is post-MVP
once we model attribute-level HAS_GLOSSARY_TERM links."""
from metamart.quality.catalog import CatalogSnapshot
from metamart.quality.registry import registry
from metamart.quality.types import Dimension, Finding, Severity


@registry.register(
    rule_id="glossary.entity_uncovered",
    dimension=Dimension.GLOSSARY,
    default_severity=Severity.WARN,
)
def entity_uncovered(catalog: CatalogSnapshot, params: dict) -> list[Finding]:
    findings: list[Finding] = []
    for e in catalog.entities:
        if e.is_staging or e.is_standalone:
            continue
        if not e.glossary_term_ids:
            findings.append(
                Finding(
                    rule_id="glossary.entity_uncovered",
                    dimension=Dimension.GLOSSARY,
                    severity=Severity.WARN,
                    target_obj_id=e.obj_id,
                    message=f"Entity '{e.physical_name}' has no linked glossary term",
                    remediation="Link to a BusinessTerm describing what this entity represents",
                )
            )
    return findings
