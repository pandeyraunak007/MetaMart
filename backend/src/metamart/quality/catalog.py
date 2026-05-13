"""Read-only snapshot of a model's state at a specific version.

Rules walk this in-memory structure rather than querying the DB themselves.
The snapshot is a clean DTO layer between SQLAlchemy mapped objects and rule
functions — easier to unit-test and swap out for synthetic data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from metamart.mart.models import M70Relationship
from metamart.mart.specializations import (
    M70Attribute,
    M70Domain,
    M70Entity,
    M70GlossaryTerm,
    M70Key,
    M70KeyMember,
    M70LineageEdge,
)
from metamart.quality.types import Dimension


@dataclass
class Attribute:
    obj_id: int
    entity_obj_id: int
    logical_name: str
    physical_name: str
    data_type: str
    is_nullable: bool = True
    position: int = 0
    comment: str | None = None
    domain_obj_id: int | None = None


@dataclass
class Key:
    obj_id: int
    entity_obj_id: int
    key_type: str  # PK | AK | IE
    name: str | None = None
    member_attr_obj_ids: list[int] = field(default_factory=list)


@dataclass
class Entity:
    obj_id: int
    model_obj_id: int
    logical_name: str
    physical_name: str
    subject_area_obj_id: int | None = None
    comment: str | None = None
    is_view: bool = False
    is_staging: bool = False
    is_standalone: bool = False
    attributes: list[Attribute] = field(default_factory=list)
    keys: list[Key] = field(default_factory=list)
    glossary_term_ids: list[int] = field(default_factory=list)


@dataclass
class Domain:
    obj_id: int
    name: str
    data_type: str
    description: str | None = None


@dataclass
class GlossaryTerm:
    obj_id: int
    name: str
    definition: str
    status: str = "draft"


@dataclass
class LineageEdge:
    obj_id: int
    source_obj_id: int
    target_obj_id: int
    transformation_sql: str | None = None


@dataclass
class Relationship:
    parent_obj_id: int
    child_obj_id: int
    rel_type: str  # FK | LINEAGE | HAS_GLOSSARY_TERM


@dataclass
class CatalogSnapshot:
    model_obj_id: int
    version_id: int
    entities: list[Entity] = field(default_factory=list)
    domains: list[Domain] = field(default_factory=list)
    glossary_terms: list[GlossaryTerm] = field(default_factory=list)
    lineage_edges: list[LineageEdge] = field(default_factory=list)
    fk_relationships: list[Relationship] = field(default_factory=list)

    # ── lookup conveniences ──────────────────────────────────

    @property
    def entity_by_id(self) -> dict[int, Entity]:
        return {e.obj_id: e for e in self.entities}

    @property
    def attribute_by_id(self) -> dict[int, Attribute]:
        return {a.obj_id: a for e in self.entities for a in e.attributes}

    @property
    def domain_by_id(self) -> dict[int, Domain]:
        return {d.obj_id: d for d in self.domains}

    @property
    def glossary_by_id(self) -> dict[int, GlossaryTerm]:
        return {g.obj_id: g for g in self.glossary_terms}

    def population_for_dimension(self, dim: Dimension) -> int:
        total_attrs = sum(len(e.attributes) for e in self.entities)
        if dim == Dimension.NAMING:
            return len(self.entities) + total_attrs
        if dim == Dimension.NORMALIZATION:
            return len(self.entities)
        if dim == Dimension.ORPHANS:
            return sum(1 for e in self.entities if not e.is_standalone)
        if dim == Dimension.PKS:
            return sum(1 for e in self.entities if not e.is_view and not e.is_staging)
        if dim == Dimension.DATATYPES:
            return total_attrs
        if dim == Dimension.GLOSSARY:
            # Weighted population: entities count 2×, attributes 1×.
            return 2 * len(self.entities) + total_attrs
        if dim == Dimension.LINEAGE:
            # v1 heuristic: warehouse-style entities by physical_name prefix.
            prefixes = ("fact_", "dim_", "mart_")
            return sum(1 for e in self.entities if e.physical_name.lower().startswith(prefixes))
        return 0


# ── DB reader ────────────────────────────────────────────────

def _alive(model_class, version_id: int):
    return [
        model_class.version_from <= version_id,
        or_(model_class.version_to.is_(None), model_class.version_to > version_id),
    ]


def read_catalog_at_version(
    db: Session,
    *,
    model_obj_id: int,
    version_id: int,
) -> CatalogSnapshot:
    """Hydrate a `CatalogSnapshot` from the `m70_*` tables at a given version."""
    e_rows = (
        db.execute(
            select(M70Entity)
            .where(M70Entity.model_obj_id == model_obj_id)
            .where(*_alive(M70Entity, version_id))
        )
        .scalars()
        .all()
    )
    entity_ids = [e.obj_id for e in e_rows]

    a_rows = (
        db.execute(
            select(M70Attribute)
            .where(M70Attribute.entity_obj_id.in_(entity_ids))
            .where(*_alive(M70Attribute, version_id))
        )
        .scalars()
        .all()
        if entity_ids
        else []
    )
    attrs_by_entity: dict[int, list[Attribute]] = {}
    for a in a_rows:
        attrs_by_entity.setdefault(a.entity_obj_id, []).append(
            Attribute(
                obj_id=a.obj_id,
                entity_obj_id=a.entity_obj_id,
                logical_name=a.logical_name,
                physical_name=a.physical_name,
                data_type=a.data_type,
                is_nullable=a.is_nullable,
                position=a.position,
                comment=a.comment,
                domain_obj_id=a.domain_obj_id,
            )
        )
    for lst in attrs_by_entity.values():
        lst.sort(key=lambda x: (x.position, x.obj_id))

    k_rows = (
        db.execute(
            select(M70Key)
            .where(M70Key.entity_obj_id.in_(entity_ids))
            .where(*_alive(M70Key, version_id))
        )
        .scalars()
        .all()
        if entity_ids
        else []
    )
    key_ids = [k.obj_id for k in k_rows]

    km_rows = (
        db.execute(
            select(M70KeyMember)
            .where(M70KeyMember.key_obj_id.in_(key_ids))
            .where(*_alive(M70KeyMember, version_id))
        )
        .scalars()
        .all()
        if key_ids
        else []
    )
    members_by_key: dict[int, list[int]] = {}
    for km in sorted(km_rows, key=lambda x: (x.key_obj_id, x.sort_order)):
        members_by_key.setdefault(km.key_obj_id, []).append(km.attribute_obj_id)

    keys_by_entity: dict[int, list[Key]] = {}
    for k in k_rows:
        keys_by_entity.setdefault(k.entity_obj_id, []).append(
            Key(
                obj_id=k.obj_id,
                entity_obj_id=k.entity_obj_id,
                key_type=k.key_type,
                name=k.name,
                member_attr_obj_ids=members_by_key.get(k.obj_id, []),
            )
        )

    d_rows = (
        db.execute(select(M70Domain).where(*_alive(M70Domain, version_id))).scalars().all()
    )
    domains = [
        Domain(obj_id=d.obj_id, name=d.name, data_type=d.data_type, description=d.description)
        for d in d_rows
    ]

    g_rows = (
        db.execute(
            select(M70GlossaryTerm).where(*_alive(M70GlossaryTerm, version_id))
        )
        .scalars()
        .all()
    )
    glossary = [
        GlossaryTerm(obj_id=g.obj_id, name=g.name, definition=g.definition, status=g.status)
        for g in g_rows
    ]

    gl_rows = (
        db.execute(
            select(M70Relationship)
            .where(M70Relationship.parent_obj_id.in_(entity_ids))
            .where(M70Relationship.rel_type == "HAS_GLOSSARY_TERM")
            .where(*_alive(M70Relationship, version_id))
        )
        .scalars()
        .all()
        if entity_ids
        else []
    )
    glossary_links_by_entity: dict[int, list[int]] = {}
    for r in gl_rows:
        glossary_links_by_entity.setdefault(r.parent_obj_id, []).append(r.child_obj_id)

    entities: list[Entity] = [
        Entity(
            obj_id=e.obj_id,
            model_obj_id=e.model_obj_id,
            subject_area_obj_id=e.subject_area_obj_id,
            logical_name=e.logical_name,
            physical_name=e.physical_name,
            comment=e.comment,
            is_view=e.is_view,
            is_staging=e.is_staging,
            is_standalone=e.is_standalone,
            attributes=attrs_by_entity.get(e.obj_id, []),
            keys=keys_by_entity.get(e.obj_id, []),
            glossary_term_ids=glossary_links_by_entity.get(e.obj_id, []),
        )
        for e in e_rows
    ]

    fk_rows = (
        db.execute(
            select(M70Relationship)
            .where(
                or_(
                    M70Relationship.parent_obj_id.in_(entity_ids),
                    M70Relationship.child_obj_id.in_(entity_ids),
                )
            )
            .where(M70Relationship.rel_type == "FK")
            .where(*_alive(M70Relationship, version_id))
        )
        .scalars()
        .all()
        if entity_ids
        else []
    )
    fk_rels = [
        Relationship(
            parent_obj_id=r.parent_obj_id, child_obj_id=r.child_obj_id, rel_type=r.rel_type
        )
        for r in fk_rows
    ]

    ln_rows = (
        db.execute(select(M70LineageEdge).where(*_alive(M70LineageEdge, version_id)))
        .scalars()
        .all()
    )
    lineage = [
        LineageEdge(
            obj_id=ln.obj_id,
            source_obj_id=ln.source_obj_id,
            target_obj_id=ln.target_obj_id,
            transformation_sql=ln.transformation_sql,
        )
        for ln in ln_rows
    ]

    return CatalogSnapshot(
        model_obj_id=model_obj_id,
        version_id=version_id,
        entities=entities,
        domains=domains,
        glossary_terms=glossary,
        lineage_edges=lineage,
        fk_relationships=fk_rels,
    )
