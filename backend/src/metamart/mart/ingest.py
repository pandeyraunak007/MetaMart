"""JSON-catalog ingest: write a model into the mart schema as version 1.

The catalog format is documented in `backend/seed_data/*.json` examples.
Each call creates a new model + version 1 + all objects, with cross-references
resolved through a local `id_map` (local string IDs in the JSON → DB obj_ids).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from metamart.mart.models import (
    M70Model,
    M70ModelVersion,
    M70Object,
    M70Relationship,
)
from metamart.mart.specializations import (
    M70Attribute,
    M70Domain,
    M70Entity,
    M70GlossaryTerm,
    M70Key,
    M70KeyMember,
    M70LineageEdge,
    M70RelationshipLogical,
    M70SubjectArea,
)


def ingest_catalog(
    db: Session,
    *,
    catalog: dict[str, Any],
    library_obj_id: int,
    folder_obj_id: int,
    author_user_id: int,
) -> M70Model:
    """Import a JSON catalog as version 1 of a new model under `folder_obj_id`."""
    model = _create_model(db, catalog=catalog, folder_obj_id=folder_obj_id, author_user_id=author_user_id)
    version = _create_initial_version(db, model_obj_id=model.obj_id, author_user_id=author_user_id)
    v = version.version_id
    id_map: dict[str, int] = {}

    _ingest_subject_areas(db, catalog, model.obj_id, author_user_id, v, id_map)
    _ingest_domains(db, catalog, model.obj_id, author_user_id, v, id_map)
    _ingest_glossary(db, catalog, model.obj_id, author_user_id, v, id_map)
    _ingest_entities(db, catalog, model.obj_id, author_user_id, v, id_map)
    _ingest_relationships(db, catalog, model.obj_id, author_user_id, v, id_map)
    _ingest_lineage(db, catalog, model.obj_id, author_user_id, v, id_map)

    db.flush()
    return model


# ── helpers ─────────────────────────────────────────────────────

def _new_obj(db: Session, *, obj_type: str, parent: int | None, creator: int) -> M70Object:
    obj = M70Object(
        obj_type=obj_type,
        parent_obj_id=parent,
        created_by=creator,
        modified_by=creator,
    )
    db.add(obj)
    db.flush()
    return obj


def _create_model(
    db: Session, *, catalog: dict[str, Any], folder_obj_id: int, author_user_id: int
) -> M70Model:
    obj = _new_obj(db, obj_type="MODEL", parent=folder_obj_id, creator=author_user_id)
    model = M70Model(
        obj_id=obj.obj_id,
        folder_obj_id=folder_obj_id,
        name=catalog["name"],
        model_type=catalog.get("model_type", "physical"),
        description=catalog.get("description"),
    )
    db.add(model)
    db.flush()
    return model


def _create_initial_version(
    db: Session, *, model_obj_id: int, author_user_id: int
) -> M70ModelVersion:
    version = M70ModelVersion(
        model_obj_id=model_obj_id,
        version_num=1,
        author_user_id=author_user_id,
        comment="Initial import",
    )
    db.add(version)
    db.flush()
    return version


def _ingest_subject_areas(db, catalog, model_obj_id, creator, v, id_map):
    for sa in catalog.get("subject_areas", []):
        obj = _new_obj(db, obj_type="SUBJECT_AREA", parent=model_obj_id, creator=creator)
        id_map[sa["id"]] = obj.obj_id
        db.add(
            M70SubjectArea(
                obj_id=obj.obj_id,
                version_from=v,
                model_obj_id=model_obj_id,
                name=sa["name"],
                description=sa.get("description"),
            )
        )


def _ingest_domains(db, catalog, model_obj_id, creator, v, id_map):
    for d in catalog.get("domains", []):
        obj = _new_obj(db, obj_type="DOMAIN", parent=model_obj_id, creator=creator)
        id_map[d["id"]] = obj.obj_id
        db.add(
            M70Domain(
                obj_id=obj.obj_id,
                version_from=v,
                name=d["name"],
                data_type=d["data_type"],
                default_value=d.get("default_value"),
                check_constraint=d.get("check_constraint"),
                description=d.get("description"),
            )
        )


def _ingest_glossary(db, catalog, model_obj_id, creator, v, id_map):
    for g in catalog.get("glossary", []):
        obj = _new_obj(db, obj_type="GLOSSARY_TERM", parent=model_obj_id, creator=creator)
        id_map[g["id"]] = obj.obj_id
        db.add(
            M70GlossaryTerm(
                obj_id=obj.obj_id,
                version_from=v,
                name=g["name"],
                definition=g["definition"],
                status=g.get("status", "draft"),
            )
        )


def _ingest_entities(db, catalog, model_obj_id, creator, v, id_map):
    for e in catalog.get("entities", []):
        e_obj = _new_obj(db, obj_type="ENTITY", parent=model_obj_id, creator=creator)
        id_map[e["id"]] = e_obj.obj_id
        db.add(
            M70Entity(
                obj_id=e_obj.obj_id,
                version_from=v,
                model_obj_id=model_obj_id,
                subject_area_obj_id=id_map.get(e.get("subject_area")),
                logical_name=e["logical_name"],
                physical_name=e["physical_name"],
                comment=e.get("comment"),
                is_view=e.get("is_view", False),
                is_staging=e.get("is_staging", False),
                is_standalone=e.get("is_standalone", False),
            )
        )
        db.flush()

        for a in e.get("attributes", []):
            a_obj = _new_obj(db, obj_type="ATTRIBUTE", parent=e_obj.obj_id, creator=creator)
            id_map[a["id"]] = a_obj.obj_id
            db.add(
                M70Attribute(
                    obj_id=a_obj.obj_id,
                    version_from=v,
                    entity_obj_id=e_obj.obj_id,
                    logical_name=a["logical_name"],
                    physical_name=a["physical_name"],
                    data_type=a["data_type"],
                    is_nullable=a.get("is_nullable", True),
                    position=a.get("position", 0),
                    comment=a.get("comment"),
                    domain_obj_id=id_map.get(a.get("domain")),
                )
            )
        db.flush()

        for k in e.get("keys", []):
            k_obj = _new_obj(db, obj_type="KEY", parent=e_obj.obj_id, creator=creator)
            id_map[k["id"]] = k_obj.obj_id
            db.add(
                M70Key(
                    obj_id=k_obj.obj_id,
                    version_from=v,
                    entity_obj_id=e_obj.obj_id,
                    key_type=k["key_type"],
                    name=k.get("name"),
                )
            )
            db.flush()
            for i, member_local_id in enumerate(k["members"]):
                m_obj = _new_obj(db, obj_type="KEY_MEMBER", parent=k_obj.obj_id, creator=creator)
                db.add(
                    M70KeyMember(
                        obj_id=m_obj.obj_id,
                        version_from=v,
                        key_obj_id=k_obj.obj_id,
                        attribute_obj_id=id_map[member_local_id],
                        sort_order=i,
                        sort_direction="ASC",
                    )
                )

        for term_local_id in e.get("glossary_terms", []):
            target = id_map.get(term_local_id)
            if target is not None:
                db.add(
                    M70Relationship(
                        parent_obj_id=e_obj.obj_id,
                        child_obj_id=target,
                        rel_type="HAS_GLOSSARY_TERM",
                        version_from=v,
                    )
                )


def _ingest_relationships(db, catalog, model_obj_id, creator, v, id_map):
    for r in catalog.get("relationships", []):
        parent = id_map.get(r["parent"])
        child = id_map.get(r["child"])
        if parent is None or child is None:
            continue
        r_obj = _new_obj(db, obj_type="RELATIONSHIP", parent=model_obj_id, creator=creator)
        db.add(
            M70RelationshipLogical(
                obj_id=r_obj.obj_id,
                version_from=v,
                parent_entity_obj_id=parent,
                child_entity_obj_id=child,
                name=r.get("name"),
                cardinality=r.get("cardinality", "one_to_many"),
                is_identifying=r.get("is_identifying", False),
            )
        )
        # Also write an FK edge in m70_relationship for the rule engine to walk.
        db.add(
            M70Relationship(
                parent_obj_id=parent,
                child_obj_id=child,
                rel_type="FK",
                version_from=v,
            )
        )


def _ingest_lineage(db, catalog, model_obj_id, creator, v, id_map):
    for ln in catalog.get("lineage", []):
        src = id_map.get(ln["source"])
        tgt = id_map.get(ln["target"])
        if src is None or tgt is None:
            continue
        ln_obj = _new_obj(db, obj_type="LINEAGE_EDGE", parent=model_obj_id, creator=creator)
        db.add(
            M70LineageEdge(
                obj_id=ln_obj.obj_id,
                version_from=v,
                source_obj_id=src,
                target_obj_id=tgt,
                transformation_sql=ln.get("transformation_sql"),
            )
        )
        db.add(
            M70Relationship(
                parent_obj_id=src,
                child_obj_id=tgt,
                rel_type="LINEAGE",
                version_from=v,
            )
        )
