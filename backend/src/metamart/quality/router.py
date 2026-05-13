"""Quality REST endpoints. v1 ships the stateless `/score-json` utility;
DB-backed scan/snapshot endpoints land in M5."""
import copy
from typing import Any

from fastapi import APIRouter, Body, HTTPException, status

import metamart.quality  # noqa: F401  -- registers all built-in rules

from metamart.quality.adapters import looks_like_catalog_wrapper, normalize_catalog
from metamart.quality.engine import score_catalog
from metamart.quality.erwin_format import (
    rename_attribute as erwin_rename_attribute,
)
from metamart.quality.erwin_format import rename_entity as erwin_rename_entity
from metamart.quality.ingest_json import catalog_from_json
from metamart.quality.pack import default_pack
from metamart.quality.registry import registry as default_registry
from metamart.quality.schemas import FindingRead, ScanResultRead, SubScoreRead
from metamart.quality.types import Finding, RuleConfig, RulePack, ScanResult, Severity

router = APIRouter(prefix="/quality", tags=["quality"])


@router.post("/score-json", response_model=ScanResultRead)
def api_score_json(body: Any = Body(...)) -> ScanResultRead:
    """Score a user-supplied catalog using the Default rule pack.

    The body can be the catalog directly (legacy shape — a JSON object or
    list), OR an envelope `{catalog, pack_overrides?}` so the caller can
    pass per-rule enable / severity / params overrides without forking the
    server-side default pack.
    """
    catalog, pack = _parse_scoring_body(body)
    original = catalog
    catalog = _coerce_to_catalog(catalog)

    try:
        snapshot = catalog_from_json(catalog)
    except (KeyError, TypeError, ValueError) as exc:
        # Attach a structural fingerprint of the original payload so the
        # caller can see WHAT we received and diagnose unsupported shapes
        # without making a separate /inspect call.
        detail = {
            "message": f"invalid catalog: {exc}",
            "shape": _describe_shape(original),
        }
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail) from exc

    result = score_catalog(snapshot, pack)
    return _to_schema(result)


@router.get("/rules")
def api_list_rules() -> dict[str, Any]:
    """Return every registered rule with its metadata.

    Frontend rules editor uses this to render controls without hardcoding
    the registry. Returned shape is stable: `{rules: [{rule_id, dimension,
    default_severity, default_params, has_fixer}]}`.
    """
    return {
        "rules": [
            {
                "rule_id": spec.rule_id,
                "dimension": spec.dimension.value,
                "default_severity": spec.default_severity.value,
                "default_params": spec.default_params,
                "has_fixer": default_registry.has_fixer(spec.rule_id),
            }
            for spec in default_registry.all()
        ]
    }


@router.post("/fix")
def api_fix(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Apply a single auto-fix to a catalog and return the patched version + new score.

    Body: `{catalog: <user catalog>, rule_id: str, target_obj_id: int}`.
    Response: `{catalog, description, result, applied: bool}`.
    """
    catalog = payload.get("catalog")
    rule_id = payload.get("rule_id")
    target_obj_id = payload.get("target_obj_id")
    if catalog is None or not rule_id or target_obj_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "body must include 'catalog', 'rule_id', and 'target_obj_id'",
        )

    fixer = default_registry.fixer(rule_id)
    if fixer is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"no auto-fix registered for rule '{rule_id}'",
        )

    normalized = _normalize_to_native(catalog)
    snapshot = catalog_from_json(copy.deepcopy(normalized))

    # Use the caller's active pack so re-scores after the fix reflect any
    # custom severities / disabled rules they configured.
    pack = _build_pack(payload.get("pack_overrides"))
    pre = score_catalog(snapshot, pack)
    finding = next(
        (
            f for f in pre.findings
            if f.rule_id == rule_id and f.target_obj_id == int(target_obj_id)
        ),
        None,
    )
    if finding is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"no current finding {rule_id} #{target_obj_id} — already fixed or stale",
        )

    out = _apply_one_fix(normalized, snapshot, finding, fixer, pack)
    if not out["applied"]:
        out["result"] = _to_schema(pre).model_dump()
    return out


@router.post("/fix-all")
def api_fix_all(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Apply every auto-fix supported by the rule pack to all current findings.

    Body: `{catalog, rule_ids?: list[str]}`. If `rule_ids` is omitted, every
    registered fixer runs. Each fix is applied in a fresh snapshot so cascades
    don't blow up later fixes.

    Response: `{catalog, applied: [{rule_id, target_obj_id, description}], result}`.
    """
    catalog = payload.get("catalog")
    if catalog is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "body must include 'catalog'")

    allow_rules = payload.get("rule_ids")
    if allow_rules is not None and not isinstance(allow_rules, list):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "'rule_ids' must be a list")
    allowed = set(allow_rules) if allow_rules else None

    pack = _build_pack(payload.get("pack_overrides"))
    # `current_input` is whatever shape we'd send back to /score-json next:
    # the original erwin array (a list) for erwin-sourced models, the native
    # dict otherwise. Each iteration re-normalizes it to score the latest
    # state, then mutates the matching shape in place.
    current_input: Any = catalog
    applied: list[dict[str, Any]] = []

    # Iterate fix-and-rescore until no fixable findings remain. A small cap
    # keeps us from looping forever if a buggy fixer keeps re-introducing
    # the same finding.
    for _ in range(50):
        normalized = _normalize_to_native(current_input)
        snapshot = catalog_from_json(copy.deepcopy(normalized))
        result = score_catalog(snapshot, pack)
        targets = [
            f for f in result.findings
            if f.fixable
            and (allowed is None or f.rule_id in allowed)
        ]
        if not targets:
            break
        finding = targets[0]
        fixer = default_registry.fixer(finding.rule_id)
        if fixer is None:
            break

        out = _apply_one_fix(normalized, snapshot, finding, fixer, pack)
        if not out["applied"]:
            # Fix declined for this finding — don't loop forever on it.
            allowed = (allowed or {f.rule_id for f in default_registry.all()}) - {finding.rule_id}
            continue
        applied.append(
            {
                "rule_id": finding.rule_id,
                "target_obj_id": finding.target_obj_id,
                "description": out["description"],
            }
        )
        current_input = out["catalog"]

    final_normalized = _normalize_to_native(current_input)
    final_snapshot = catalog_from_json(copy.deepcopy(final_normalized))
    final_result = score_catalog(final_snapshot, pack)
    return {
        "catalog": current_input,
        "applied": applied,
        "result": _to_schema(final_result).model_dump(),
    }


def _parse_scoring_body(body: Any) -> tuple[Any, RulePack]:
    """Split the /score-json body into (catalog, pack).

    Two accepted shapes for backward compatibility:
      - The bare catalog (dict or list) — uses the default pack.
      - `{catalog, pack_overrides?}` envelope — applies the overrides.

    The envelope shape is recognized when the dict has a `catalog` key AND
    no `entities` key (the native catalog discriminator). This avoids
    misclassifying a catalog that happens to contain a `catalog` key.
    """
    if (
        isinstance(body, dict)
        and "catalog" in body
        and "entities" not in body
        and "_erwin_native_objects" not in body
    ):
        return body["catalog"], _build_pack(body.get("pack_overrides"))
    return body, default_pack()


def _build_pack(overrides: Any) -> RulePack:
    """Construct a RulePack from optional caller-supplied overrides.

    Override shape: `{rules: [{rule_id, enabled?, severity_override?, params_override?}]}`.
    Anything missing falls back to the rule's registered defaults.
    """
    if overrides is None:
        return default_pack()
    if not isinstance(overrides, dict):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "'pack_overrides' must be an object with a 'rules' list",
        )
    rules_raw = overrides.get("rules") or []
    if not isinstance(rules_raw, list):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "'pack_overrides.rules' must be a list",
        )

    configs: list[RuleConfig] = []
    for raw in rules_raw:
        if not isinstance(raw, dict) or "rule_id" not in raw:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "each pack_overrides.rules[] entry needs a 'rule_id'",
            )
        rule_id = raw["rule_id"]
        # Drop overrides for unknown rules silently — old packs in the
        # client's localStorage shouldn't fail scoring after a rule rename.
        try:
            default_registry.get(rule_id)
        except KeyError:
            continue
        sev_str = raw.get("severity_override")
        sev: Severity | None = None
        if sev_str is not None:
            try:
                sev = Severity(sev_str)
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"invalid severity_override '{sev_str}' for rule '{rule_id}'",
                ) from exc
        params = raw.get("params_override") or {}
        if not isinstance(params, dict):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"params_override for rule '{rule_id}' must be an object",
            )
        configs.append(
            RuleConfig(
                rule_id=rule_id,
                enabled=bool(raw.get("enabled", True)),
                severity_override=sev,
                params_override=params,
            )
        )
    return RulePack(pack_id="custom", name="Custom", rules=configs)


def _normalize_to_native(catalog: Any) -> dict[str, Any]:
    """Coerce arbitrary input into a native catalog dict, raising 400 on garbage."""
    coerced = _coerce_to_catalog(catalog)
    normalized = normalize_catalog(coerced)
    if not isinstance(normalized, dict) or "entities" not in normalized:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "catalog could not be normalized to native shape",
        )
    return normalized


def _apply_one_fix(
    normalized: dict[str, Any],
    snapshot: Any,
    finding: Finding,
    fixer: Any,
    pack: Any,
) -> dict[str, Any]:
    """Run the fixer once, preserving the input format on the way out.

    For erwin-sourced catalogs, the patched native dict from the fixer is
    used only to read the new physical_name; the actual mutation happens on
    the original erwin items array so the response stays openable in erwin
    DM. For native-sourced catalogs, we just return the patched native dict.

    Returns either:
      {applied: True, description, catalog: <list|dict>, result: <scored>}
      {applied: False, description, catalog: <input as-is>}
    """
    fixed_native, description = fixer(copy.deepcopy(normalized), finding, snapshot)
    if fixed_native is None:
        return {
            "applied": False,
            "description": description,
            "catalog": _public_catalog(normalized),
        }

    source_format = normalized.get("_source_format")
    if source_format == "erwin_native":
        target = _resolve_renamed_target(normalized, fixed_native)
        if target is None:
            return {
                "applied": False,
                "description": "could not map fix back to erwin object",
                "catalog": normalized.get("_erwin_items"),
            }
        kind, erwin_oid, new_name = target
        items = copy.deepcopy(normalized["_erwin_items"])
        ok = (
            erwin_rename_attribute(items, erwin_oid, new_name)
            if kind == "attribute"
            else erwin_rename_entity(items, erwin_oid, new_name)
        )
        if not ok:
            return {
                "applied": False,
                "description": f"erwin object {erwin_oid} not found in source array",
                "catalog": normalized.get("_erwin_items"),
            }
        new_normalized = normalize_catalog(items)
        new_snapshot = catalog_from_json(copy.deepcopy(new_normalized))
        new_result = score_catalog(new_snapshot, pack)
        return {
            "applied": True,
            "description": description,
            "catalog": items,
            "result": _to_schema(new_result).model_dump(),
        }

    # Native-source path: the patched native dict is the answer.
    new_snapshot = catalog_from_json(copy.deepcopy(fixed_native))
    new_result = score_catalog(new_snapshot, pack)
    return {
        "applied": True,
        "description": description,
        "catalog": _public_catalog(fixed_native),
        "result": _to_schema(new_result).model_dump(),
    }


def _resolve_renamed_target(
    before: dict[str, Any], after: dict[str, Any]
) -> tuple[str, str, str] | None:
    """Diff `before` and `after` to find which entity/attribute was renamed.

    Returns (kind, erwin_oid, new_physical_name) or None if no rename was
    detected (e.g. the fixer was a no-op, or the entity has no _erwin_oid
    stamp because the catalog wasn't erwin-sourced).
    """
    for old_e, new_e in zip(before.get("entities", []), after.get("entities", [])):
        if old_e.get("_erwin_oid") and old_e.get("physical_name") != new_e.get("physical_name"):
            return ("entity", old_e["_erwin_oid"], new_e["physical_name"])
        for old_a, new_a in zip(old_e.get("attributes", []), new_e.get("attributes", [])):
            if old_a.get("_erwin_oid") and old_a.get("physical_name") != new_a.get("physical_name"):
                return ("attribute", old_a["_erwin_oid"], new_a["physical_name"])
    return None


def _public_catalog(d: dict[str, Any]) -> dict[str, Any]:
    """Strip internal `_*`-prefixed provenance keys from a native catalog dict.

    Users shouldn't see `_erwin_oid` / `_erwin_items` in API responses for
    native-shape outputs. The erwin-source path returns the raw items array
    directly, so it never goes through here.
    """
    out = {k: v for k, v in d.items() if not k.startswith("_")}
    if "entities" in out and isinstance(out["entities"], list):
        cleaned: list[dict[str, Any]] = []
        for e in out["entities"]:
            if not isinstance(e, dict):
                cleaned.append(e)
                continue
            ce = {k: v for k, v in e.items() if not k.startswith("_")}
            if "attributes" in ce and isinstance(ce["attributes"], list):
                ce["attributes"] = [
                    {k: v for k, v in a.items() if not k.startswith("_")}
                    if isinstance(a, dict) else a
                    for a in ce["attributes"]
                ]
            cleaned.append(ce)
        out["entities"] = cleaned
    return out


@router.post("/inspect")
def api_inspect(payload: Any = Body(...)) -> dict[str, Any]:
    """Return a structural fingerprint of any JSON without exposing values.

    Useful for debugging unrecognized formats — paste the output back to
    the team and we'll write a precise adapter without needing your data.
    """
    return {
        "shape": _describe_shape(payload),
        "top_level_type": type(payload).__name__,
        "top_level_keys": (
            list(payload.keys())[:40] if isinstance(payload, dict) else None
        ),
        "list_length": len(payload) if isinstance(payload, list) else None,
    }


# ── helpers ──────────────────────────────────────────────────

def _coerce_to_catalog(catalog: Any) -> Any:
    """Normalize the request body into a dict-shaped catalog.

    - If it's an erwin DM internal flat-array (a top-level list of polymorphic
      `{O_Id, O_Type, Properties, ...}` objects, optionally led by a
      `{Version, Encoding, Description}` header), wrap the whole list under a
      sentinel key so `normalize_catalog` can adapt it.
    - If it's a single-element list whose only item looks like a whole catalog
      wrapper (erwin `{version, Encoding, Description, Objects, ...}` etc.),
      unwrap it.
    - Otherwise, if it's a list, treat as a bare entities array and wrap.
    - If it's neither dict nor list, raise 400.
    """
    if isinstance(catalog, list):
        if _is_erwin_native_array(catalog):
            return {"_erwin_native_objects": catalog}
        if (
            len(catalog) == 1
            and isinstance(catalog[0], dict)
            and looks_like_catalog_wrapper(catalog[0])
        ):
            return catalog[0]
        return {"entities": catalog}
    if not isinstance(catalog, dict):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "body must be a JSON object (a catalog) or a JSON list (entities); "
            f"got {type(catalog).__name__}",
        )
    return catalog


def _is_erwin_native_array(data: list) -> bool:
    """True if a top-level list looks like erwin DM's internal flat-array format."""
    if not data:
        return False
    body_start = 0
    first = data[0]
    if (
        isinstance(first, dict)
        and isinstance(first.get("Description"), str)
        and "erwin" in first["Description"].lower()
    ):
        body_start = 1
    sample = [x for x in data[body_start : body_start + 5] if isinstance(x, dict)]
    if not sample:
        return False
    return all("O_Id" in x and "O_Type" in x for x in sample)


def _describe_shape(data: Any, depth: int = 0, max_depth: int = 5) -> Any:
    """Walk JSON returning keys + type names, never values."""
    if depth >= max_depth:
        return f"<{type(data).__name__} (truncated)>"
    if isinstance(data, dict):
        return {
            k: _describe_shape(v, depth + 1, max_depth)
            for k, v in list(data.items())[:40]
        }
    if isinstance(data, list):
        if not data:
            return "[]"
        sample = _describe_shape(data[0], depth + 1, max_depth)
        return [sample, f"... × {len(data)} items"]
    if isinstance(data, str):
        return f"<str len={len(data)}>"
    if isinstance(data, (int, float, bool)) or data is None:
        return type(data).__name__
    return type(data).__name__


def _to_schema(result: ScanResult) -> ScanResultRead:
    return ScanResultRead(
        pack_id=result.pack_id,
        composite_score=result.composite_score,
        grade=result.grade,
        sub_scores=[
            SubScoreRead(
                dimension=s.dimension.value,
                score=s.score,
                finding_count_by_severity={
                    k.value: v for k, v in s.finding_count_by_severity.items()
                },
                population_size=s.population_size,
            )
            for s in result.sub_scores
        ],
        findings=[
            FindingRead(
                rule_id=f.rule_id,
                dimension=f.dimension.value,
                severity=f.severity.value,
                target_obj_id=f.target_obj_id,
                target_name=f.target_name,
                message=f.message,
                remediation=f.remediation,
                fixable=f.fixable,
            )
            for f in result.findings
        ],
    )
