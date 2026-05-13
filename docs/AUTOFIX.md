# Auto-fix extension guide

How to add an auto-fix for an existing rule, end to end.

The auto-fix layer lets a rule ship a companion function that mutates the user's catalog to make a finding go away. The frontend renders a **Fix** button on findings whose rule has a registered fixer; clicking it hits `POST /api/v1/quality/fix` and persists the patched catalog into the saved model.

## Where the pieces live

```
backend/src/metamart/quality/
├── registry.py              # rule + fix registries (decorator-based)
├── engine.py                # populates Finding.fixable from the registry
├── router.py                # /quality/fix and /quality/fix-all endpoints
├── types.py                 # Finding.fixable: bool
└── rules/
    └── naming.py            # canonical example: snake_case + max_length + reserved_word
backend/tests/
└── test_fixes.py            # round-trip pattern: detect → fix → re-detect should be empty
```

## The signature

```python
from metamart.quality.registry import registry
from metamart.quality.types import Finding
from metamart.quality.catalog import CatalogSnapshot

@registry.register_fix(rule_id="my_dim.my_rule")
def fix_my_rule(
    catalog_dict: dict,        # the user's raw catalog JSON, native shape
    finding: Finding,          # the specific finding to fix (carries target_obj_id)
    snapshot: CatalogSnapshot, # the in-memory snapshot the rule ran against
) -> tuple[dict | None, str]:
    """Return (patched_catalog, description) on success.
    Return (None, reason) to decline this particular instance — the engine
    won't retry and the caller gets `applied: false` with the reason."""
    ...
```

The function receives the **dict shape** (`{name, model_type, entities: [...]}`) — not the in-memory `CatalogSnapshot`. Mutate the dict; that's what gets persisted and re-scored.

The `snapshot` argument is for context only (resolving `target_obj_id` to the affected entity / attribute). Don't mutate it.

## What good fixers look like

1. **Resolve the target.** `target_obj_id` is the integer assigned by `catalog_from_json`. Use the snapshot's `entity_by_id` and `attribute_by_id` lookups to find which dict entry to patch:

   ```python
   from metamart.quality.rules.naming import _resolve_target
   target = _resolve_target(finding, snapshot)
   if target is None:
       return None, "target not found in snapshot"
   kind, entity_name, obj = target  # kind ∈ {"entity", "attribute"}
   ```

2. **Mutate the dict, not the snapshot.** Walk `catalog_dict["entities"]`, find the entity (by `physical_name`), edit `physical_name` / `attributes` / `keys` in place. The naming module ships small helpers (`_find_entity_in_dict`, `_rename_entity`, `_rename_attribute`) — copy that pattern.

3. **Decline rather than guess.** If the catalog isn't in the expected shape, or the violation already resolved itself, return `(None, "why")`. The engine won't retry the same finding in `/fix-all`, and the API surfaces the reason.

4. **Cascade carefully.** Local IDs (e.g. `e_customer_0`, `a1`) are what `keys.members`, `relationships.parent/child`, and `lineage.source/target` reference — they don't change when a `physical_name` does, so most renames don't need cascading. If your fix changes a *local ID*, you do need to walk every cross-reference.

5. **Make the description user-readable.** It shows up in the toast and in the model's audit log: `"Renamed entity 'CustomerAccount' → 'customer_account'"`, not `"applied transform"`.

## The test pattern

Every fixer should have a test that proves the round-trip — score → fix → re-score doesn't re-flag the same target:

```python
def test_fix_my_rule_round_trip(client: TestClient) -> None:
    cat = {
        "name": "Demo",
        "model_type": "physical",
        "entities": [_entity("BadName", [_attr("a1", "id")])],
    }
    pre = client.post("/v1/quality/score-json", json=cat).json()
    target = next(
        f for f in pre["findings"]
        if f["rule_id"] == "my_dim.my_rule"
        and f["target_name"] == "BadName"
    )
    fix = client.post(
        "/v1/quality/fix",
        json={
            "catalog": cat,
            "rule_id": "my_dim.my_rule",
            "target_obj_id": target["target_obj_id"],
        },
    ).json()
    assert fix["applied"] is True

    post = [f for f in fix["result"]["findings"] if f["rule_id"] == "my_dim.my_rule"]
    assert not any(f["target_name"] == "BadName" for f in post)
```

The `_entity` and `_attr` helpers in `tests/test_fixes.py` keep the catalog setup small. Reuse them.

## Two endpoints, two modes

- **`POST /quality/fix`** — applies one fixer to one finding. Body: `{catalog, rule_id, target_obj_id}`. Response: `{applied: bool, description, catalog: <patched>, result: <rescored>}`. Use this when the user clicks **Fix** on a single row.
- **`POST /quality/fix-all`** — loops fix-and-rescore until no fixable finding remains (capped at 50 iterations as a safety net). Optional `rule_ids: [...]` narrows the scope. Use this when the user clicks **Fix all auto-fixable (N)** in the findings header.

Both endpoints normalize the input through the foreign-format adapter cascade first, so they work on raw erwin DM JSON, dbt manifests, etc. — not just native catalogs.

## Currently shipping fixers

| `rule_id` | What it does |
|-----------|--------------|
| `naming.snake_case_physical` | Rewrites entity / attribute `physical_name` to ASCII snake_case (drops apostrophes, collapses `_+`, prepends `col_` if it'd start with a digit). |
| `naming.max_length` | Truncates names over 64 chars to `prefix_<6-char-sha1>` so collisions stay unique. |
| `naming.reserved_word` | Suffixes reserved words: `user` → `user_tbl`, `order` → `order_col`. |

## What doesn't ship a fixer (and probably shouldn't)

Some violations need human judgment, and a Fix button would be misleading:

- `pks.missing_pk` — synthesizing a surrogate key is plausible but it's a real schema decision; better to ask.
- `datatypes.cross_entity_consistency` — can't pick the canonical type without knowing which one's correct.
- `glossary.entity_uncovered` — there's no auto-fix for "write a definition."
- `orphans.no_relationships` — can't invent a relationship.

Rule of thumb: ship a fixer when there's exactly one obviously-correct transformation and the user would trust a checkbox more than a wizard.
