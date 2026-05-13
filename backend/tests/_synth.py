"""Build a `CatalogSnapshot` from a seed-style JSON dict — no DB needed.

Used by tests/test_rules_e2e.py to score the seed catalogs without standing up
Postgres. Local string IDs in the JSON are mapped to stable integer obj_ids.
"""
from __future__ import annotations

from typing import Any

from metamart.quality.catalog import (
    Attribute,
    CatalogSnapshot,
    Domain,
    Entity,
    GlossaryTerm,
    Key,
    LineageEdge,
    Relationship,
)


def synth_catalog_from_json(data: dict[str, Any]) -> CatalogSnapshot:
    next_id = [100]
    id_map: dict[str, int] = {}

    def assign(local: str) -> int:
        if local not in id_map:
            id_map[local] = next_id[0]
            next_id[0] += 1
        return id_map[local]

    domains = [
        Domain(
            obj_id=assign(d["id"]),
            name=d["name"],
            data_type=d["data_type"],
            description=d.get("description"),
        )
        for d in data.get("domains", [])
    ]

    glossary = [
        GlossaryTerm(
            obj_id=assign(g["id"]),
            name=g["name"],
            definition=g["definition"],
            status=g.get("status", "draft"),
        )
        for g in data.get("glossary", [])
    ]

    entities: list[Entity] = []
    fk_rels: list[Relationship] = []
    lineage: list[LineageEdge] = []

    for e in data.get("entities", []):
        entity_id = assign(e["id"])

        attributes = [
            Attribute(
                obj_id=assign(a["id"]),
                entity_obj_id=entity_id,
                logical_name=a["logical_name"],
                physical_name=a["physical_name"],
                data_type=a["data_type"],
                is_nullable=a.get("is_nullable", True),
                position=a.get("position", 0),
                comment=a.get("comment"),
                domain_obj_id=id_map.get(a.get("domain")) if a.get("domain") else None,
            )
            for a in e.get("attributes", [])
        ]

        keys = [
            Key(
                obj_id=assign(k["id"]),
                entity_obj_id=entity_id,
                key_type=k["key_type"],
                name=k.get("name"),
                member_attr_obj_ids=[id_map[m] for m in k["members"] if m in id_map],
            )
            for k in e.get("keys", [])
        ]

        glossary_links = [
            id_map[t] for t in e.get("glossary_terms", []) if t in id_map
        ]

        entities.append(
            Entity(
                obj_id=entity_id,
                model_obj_id=1,
                logical_name=e["logical_name"],
                physical_name=e["physical_name"],
                subject_area_obj_id=None,
                comment=e.get("comment"),
                is_view=e.get("is_view", False),
                is_staging=e.get("is_staging", False),
                is_standalone=e.get("is_standalone", False),
                attributes=attributes,
                keys=keys,
                glossary_term_ids=glossary_links,
            )
        )

    for r in data.get("relationships", []):
        if r["parent"] in id_map and r["child"] in id_map:
            fk_rels.append(
                Relationship(
                    parent_obj_id=id_map[r["parent"]],
                    child_obj_id=id_map[r["child"]],
                    rel_type="FK",
                )
            )

    for ln in data.get("lineage", []):
        src = id_map.get(ln.get("source"))
        tgt = id_map.get(ln.get("target"))
        if src is not None and tgt is not None:
            lineage.append(
                LineageEdge(
                    obj_id=assign(ln.get("id", f"_ln_{src}_{tgt}")),
                    source_obj_id=src,
                    target_obj_id=tgt,
                    transformation_sql=ln.get("transformation_sql"),
                )
            )

    return CatalogSnapshot(
        model_obj_id=1,
        version_id=1,
        entities=entities,
        domains=domains,
        glossary_terms=glossary,
        lineage_edges=lineage,
        fk_relationships=fk_rels,
    )
