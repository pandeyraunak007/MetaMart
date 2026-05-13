"""Naming consistency rules."""
import re

from metamart.quality.catalog import CatalogSnapshot
from metamart.quality.registry import registry
from metamart.quality.types import Dimension, Finding, Severity

SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
DEFAULT_MAX_LEN = 64

DEFAULT_RESERVED = frozenset(
    {
        "select", "from", "where", "table", "user", "order", "group",
        "join", "having", "case", "when", "then", "else", "end",
        "create", "drop", "alter", "primary", "key", "foreign", "index",
        "view", "trigger", "function", "procedure",
    }
)


def _to_snake(name: str) -> str:
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s2 = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s1)
    return s2.lower()


@registry.register(
    rule_id="naming.snake_case_physical",
    dimension=Dimension.NAMING,
    default_severity=Severity.WARN,
)
def snake_case_physical(catalog: CatalogSnapshot, params: dict) -> list[Finding]:
    findings: list[Finding] = []
    for e in catalog.entities:
        if not SNAKE_CASE_RE.match(e.physical_name):
            findings.append(
                Finding(
                    rule_id="naming.snake_case_physical",
                    dimension=Dimension.NAMING,
                    severity=Severity.WARN,
                    target_obj_id=e.obj_id,
                    message=f"Entity '{e.physical_name}' violates snake_case",
                    remediation=f"Rename to '{_to_snake(e.physical_name)}'",
                )
            )
        for a in e.attributes:
            if not SNAKE_CASE_RE.match(a.physical_name):
                findings.append(
                    Finding(
                        rule_id="naming.snake_case_physical",
                        dimension=Dimension.NAMING,
                        severity=Severity.WARN,
                        target_obj_id=a.obj_id,
                        message=f"Attribute '{e.physical_name}.{a.physical_name}' violates snake_case",
                        remediation=f"Rename to '{_to_snake(a.physical_name)}'",
                    )
                )
    return findings


@registry.register(
    rule_id="naming.max_length",
    dimension=Dimension.NAMING,
    default_severity=Severity.WARN,
    default_params={"max_length": DEFAULT_MAX_LEN},
)
def max_length(catalog: CatalogSnapshot, params: dict) -> list[Finding]:
    max_len = int(params.get("max_length", DEFAULT_MAX_LEN))
    findings: list[Finding] = []
    for e in catalog.entities:
        if len(e.physical_name) > max_len:
            findings.append(
                Finding(
                    rule_id="naming.max_length",
                    dimension=Dimension.NAMING,
                    severity=Severity.WARN,
                    target_obj_id=e.obj_id,
                    message=f"Entity name '{e.physical_name}' exceeds {max_len} chars",
                )
            )
        for a in e.attributes:
            if len(a.physical_name) > max_len:
                findings.append(
                    Finding(
                        rule_id="naming.max_length",
                        dimension=Dimension.NAMING,
                        severity=Severity.WARN,
                        target_obj_id=a.obj_id,
                        message=f"Attribute name '{e.physical_name}.{a.physical_name}' exceeds {max_len} chars",
                    )
                )
    return findings


@registry.register(
    rule_id="naming.reserved_word",
    dimension=Dimension.NAMING,
    default_severity=Severity.ERROR,
    default_params={"reserved": sorted(DEFAULT_RESERVED)},
)
def reserved_word(catalog: CatalogSnapshot, params: dict) -> list[Finding]:
    reserved = {w.lower() for w in params.get("reserved", DEFAULT_RESERVED)}
    findings: list[Finding] = []
    for e in catalog.entities:
        if e.physical_name.lower() in reserved:
            findings.append(
                Finding(
                    rule_id="naming.reserved_word",
                    dimension=Dimension.NAMING,
                    severity=Severity.ERROR,
                    target_obj_id=e.obj_id,
                    message=f"Entity '{e.physical_name}' is a SQL reserved word",
                )
            )
        for a in e.attributes:
            if a.physical_name.lower() in reserved:
                findings.append(
                    Finding(
                        rule_id="naming.reserved_word",
                        dimension=Dimension.NAMING,
                        severity=Severity.ERROR,
                        target_obj_id=a.obj_id,
                        message=f"Attribute '{e.physical_name}.{a.physical_name}' is a SQL reserved word",
                    )
                )
    return findings
