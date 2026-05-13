"""Naming consistency rules + their auto-fixes."""
from __future__ import annotations

import hashlib
import re
from typing import Any

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


# ── auto-fix helpers ─────────────────────────────────────────

def _safe_slug(name: str) -> str:
    """Aggressively normalize to ASCII snake_case so the result satisfies
    `SNAKE_CASE_RE`. Drops non-word chars and collapses runs of underscores.
    """
    s = _to_snake(name)
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "col"
    if not re.match(r"^[a-z]", s):
        s = "_" + s if s.startswith("_") else f"col_{s}"
    return s


def _truncated(name: str, max_len: int) -> str:
    """Truncate to max_len keeping a 6-char hash suffix when shortening, so
    the result stays unique vs other long names that share a common prefix.
    """
    if len(name) <= max_len:
        return name
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]
    keep = max(1, max_len - 7)  # 7 = "_" + 6-char hash
    return f"{name[:keep]}_{digest}"


def _suffix_for_reserved(name: str, kind: str) -> str:
    """Append `_col` or `_tbl` to escape a SQL reserved word."""
    suffix = "_tbl" if kind == "entity" else "_col"
    return f"{name}{suffix}"


def _find_entity_in_dict(
    catalog_dict: dict, physical_name: str
) -> dict | None:
    for e in catalog_dict.get("entities") or []:
        if isinstance(e, dict) and e.get("physical_name") == physical_name:
            return e
    return None


def _find_attribute_in_dict(
    catalog_dict: dict, entity_name: str, attribute_name: str
) -> tuple[dict | None, dict | None]:
    """Return (entity_dict, attribute_dict) or (None, None) if not found."""
    entity = _find_entity_in_dict(catalog_dict, entity_name)
    if not entity:
        return None, None
    for a in entity.get("attributes") or []:
        if isinstance(a, dict) and a.get("physical_name") == attribute_name:
            return entity, a
    return entity, None


def _rename_entity(
    catalog_dict: dict, old_physical: str, new_physical: str
) -> str | None:
    """Rename the entity's physical_name in catalog_dict + cascade refs.

    Returns new name on success, None if entity not found. Cascades into
    relationships only — keys/attributes hang off the entity dict, so they
    move with it.
    """
    entity = _find_entity_in_dict(catalog_dict, old_physical)
    if entity is None:
        return None
    entity["physical_name"] = new_physical
    # Relationship parent/child use entity local IDs (e.g. "e_customer_0"),
    # not physical names, so they don't need cascading. Same for lineage.
    return new_physical


def _rename_attribute(
    catalog_dict: dict,
    entity_name: str,
    old_attr: str,
    new_attr: str,
) -> str | None:
    entity, attr = _find_attribute_in_dict(catalog_dict, entity_name, old_attr)
    if attr is None:
        return None
    attr["physical_name"] = new_attr
    # Key members reference attributes by local ID, not name, so no cascade.
    return new_attr


def _resolve_target(
    finding: Finding, snapshot: CatalogSnapshot
) -> tuple[str, str, Any] | None:
    """Identify what the finding's target_obj_id refers to.

    Returns ("entity", entity_physical_name, entity) or
    ("attribute", entity_physical_name, attribute) or None.
    """
    entity = snapshot.entity_by_id.get(finding.target_obj_id)
    if entity is not None:
        return ("entity", entity.physical_name, entity)
    attr = snapshot.attribute_by_id.get(finding.target_obj_id)
    if attr is not None:
        parent = snapshot.entity_by_id.get(attr.entity_obj_id)
        if parent is None:
            return None
        return ("attribute", parent.physical_name, attr)
    return None


# ── auto-fix functions ───────────────────────────────────────

@registry.register_fix(rule_id="naming.snake_case_physical")
def fix_snake_case(
    catalog_dict: dict, finding: Finding, snapshot: CatalogSnapshot
) -> tuple[dict | None, str]:
    target = _resolve_target(finding, snapshot)
    if target is None:
        return None, "target not found in snapshot"
    kind, entity_name, obj = target
    old = obj.physical_name
    new = _safe_slug(old)
    if old == new:
        return None, "already snake_case"
    if kind == "entity":
        if _rename_entity(catalog_dict, old, new) is None:
            return None, f"entity '{old}' not in catalog dict"
        return catalog_dict, f"Renamed entity '{old}' → '{new}'"
    if _rename_attribute(catalog_dict, entity_name, old, new) is None:
        return None, f"attribute '{entity_name}.{old}' not in catalog dict"
    return catalog_dict, f"Renamed attribute '{entity_name}.{old}' → '{entity_name}.{new}'"


@registry.register_fix(rule_id="naming.max_length")
def fix_max_length(
    catalog_dict: dict, finding: Finding, snapshot: CatalogSnapshot
) -> tuple[dict | None, str]:
    target = _resolve_target(finding, snapshot)
    if target is None:
        return None, "target not found in snapshot"
    kind, entity_name, obj = target
    old = obj.physical_name
    # Reuse the same default the rule uses; the rule's params get baked into
    # the message but we don't have them here, so default is fine for v1.
    new = _truncated(old, DEFAULT_MAX_LEN)
    if old == new:
        return None, "already within length"
    if kind == "entity":
        if _rename_entity(catalog_dict, old, new) is None:
            return None, f"entity '{old}' not in catalog dict"
        return catalog_dict, f"Truncated entity '{old}' → '{new}'"
    if _rename_attribute(catalog_dict, entity_name, old, new) is None:
        return None, f"attribute '{entity_name}.{old}' not in catalog dict"
    return catalog_dict, f"Truncated attribute '{entity_name}.{old}' → '{entity_name}.{new}'"


@registry.register_fix(rule_id="naming.reserved_word")
def fix_reserved_word(
    catalog_dict: dict, finding: Finding, snapshot: CatalogSnapshot
) -> tuple[dict | None, str]:
    target = _resolve_target(finding, snapshot)
    if target is None:
        return None, "target not found in snapshot"
    kind, entity_name, obj = target
    old = obj.physical_name
    new = _suffix_for_reserved(old, kind)
    if kind == "entity":
        if _rename_entity(catalog_dict, old, new) is None:
            return None, f"entity '{old}' not in catalog dict"
        return catalog_dict, f"Renamed reserved-word entity '{old}' → '{new}'"
    if _rename_attribute(catalog_dict, entity_name, old, new) is None:
        return None, f"attribute '{entity_name}.{old}' not in catalog dict"
    return catalog_dict, f"Renamed reserved-word attribute '{entity_name}.{old}' → '{entity_name}.{new}'"
