"""Quality REST endpoints. v1 ships the stateless `/score-json` utility;
DB-backed scan/snapshot endpoints land in M5."""
import copy
from typing import Any

from fastapi import APIRouter, Body, HTTPException, status

import metamart.quality  # noqa: F401  -- registers all built-in rules

from metamart.quality.adapters import looks_like_catalog_wrapper, normalize_catalog
from metamart.quality.engine import score_catalog
from metamart.quality.ingest_json import catalog_from_json
from metamart.quality.pack import default_pack
from metamart.quality.registry import registry as default_registry
from metamart.quality.schemas import FindingRead, ScanResultRead, SubScoreRead
from metamart.quality.types import ScanResult

router = APIRouter(prefix="/quality", tags=["quality"])


@router.post("/score-json", response_model=ScanResultRead)
def api_score_json(catalog: Any = Body(...)) -> ScanResultRead:
    """Score a user-supplied catalog using the Default rule pack.

    Accepts either a catalog object or a list. A single-element list whose
    only item looks like a whole-catalog wrapper (e.g. erwin "Save As JSON"
    files) is unwrapped; other lists are treated as a bare entities array.
    """
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

    result = score_catalog(snapshot, default_pack())
    return _to_schema(result)


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

    # Find the actual finding to pass to the fixer (it carries severity etc).
    pack = default_pack()
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

    patched, description = fixer(copy.deepcopy(normalized), finding, snapshot)
    if patched is None:
        return {
            "applied": False,
            "description": description,
            "catalog": normalized,
            "result": _to_schema(pre).model_dump(),
        }

    new_snapshot = catalog_from_json(copy.deepcopy(patched))
    new_result = score_catalog(new_snapshot, pack)
    return {
        "applied": True,
        "description": description,
        "catalog": patched,
        "result": _to_schema(new_result).model_dump(),
    }


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

    pack = default_pack()
    current = _normalize_to_native(catalog)
    applied: list[dict[str, Any]] = []

    # Iterate fix-and-rescore until no fixable findings remain. A small cap
    # keeps us from looping forever if a buggy fixer keeps re-introducing
    # the same finding.
    for _ in range(50):
        snapshot = catalog_from_json(copy.deepcopy(current))
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
        patched, description = fixer(copy.deepcopy(current), finding, snapshot)
        if patched is None:
            # Fix declined for this finding — don't loop forever on it.
            allowed = (allowed or {f.rule_id for f in default_registry.all()}) - {finding.rule_id}
            continue
        applied.append(
            {
                "rule_id": finding.rule_id,
                "target_obj_id": finding.target_obj_id,
                "description": description,
            }
        )
        current = patched

    final_snapshot = catalog_from_json(copy.deepcopy(current))
    final_result = score_catalog(final_snapshot, pack)
    return {
        "catalog": current,
        "applied": applied,
        "result": _to_schema(final_result).model_dump(),
    }


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
