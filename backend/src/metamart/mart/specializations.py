"""SCD Type 2 specialization mappers (M2.5).

Every table here is versioned with composite PK `(obj_id, version_from)` and
the half-open interval `[version_from, version_to)`. Cross-table FKs reference
`m70_object.obj_id` (the stable identity), never the composite PK.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from metamart.db import Base


class M70SubjectArea(Base):
    __tablename__ = "m70_subject_area"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    version_from: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_to: Mapped[int | None] = mapped_column(BigInteger)
    model_obj_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("m70_object.obj_id"))
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_m70_subject_area_model", "model_obj_id", "version_from"),)


class M70Entity(Base):
    __tablename__ = "m70_entity"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    version_from: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_to: Mapped[int | None] = mapped_column(BigInteger)
    model_obj_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("m70_object.obj_id"))
    subject_area_obj_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id")
    )
    logical_name: Mapped[str] = mapped_column(String(256))
    physical_name: Mapped[str] = mapped_column(String(256))
    comment: Mapped[str | None] = mapped_column(Text)
    is_view: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_staging: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_standalone: Mapped[bool] = mapped_column(Boolean, server_default="false")

    __table_args__ = (
        Index("ix_m70_entity_model", "model_obj_id", "version_from"),
        Index("ix_m70_entity_sa", "subject_area_obj_id", "version_from"),
        Index("ix_m70_entity_physical_name", "physical_name"),
    )


class M70Attribute(Base):
    __tablename__ = "m70_attribute"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    version_from: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_to: Mapped[int | None] = mapped_column(BigInteger)
    entity_obj_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("m70_object.obj_id"))
    logical_name: Mapped[str] = mapped_column(String(256))
    physical_name: Mapped[str] = mapped_column(String(256))
    data_type: Mapped[str] = mapped_column(String(64))
    is_nullable: Mapped[bool] = mapped_column(Boolean, server_default="true")
    position: Mapped[int] = mapped_column(Integer, server_default="0")
    comment: Mapped[str | None] = mapped_column(Text)
    domain_obj_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("m70_object.obj_id"))

    __table_args__ = (
        Index("ix_m70_attribute_entity", "entity_obj_id", "version_from"),
        Index("ix_m70_attribute_physical_name", "physical_name"),
    )


class M70Key(Base):
    __tablename__ = "m70_key"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    version_from: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_to: Mapped[int | None] = mapped_column(BigInteger)
    entity_obj_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("m70_object.obj_id"))
    key_type: Mapped[str] = mapped_column(String(8))
    name: Mapped[str | None] = mapped_column(String(256))

    __table_args__ = (
        Index("ix_m70_key_entity", "entity_obj_id", "version_from"),
        Index("ix_m70_key_type", "entity_obj_id", "key_type", "version_from"),
    )


class M70KeyMember(Base):
    __tablename__ = "m70_key_member"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    version_from: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_to: Mapped[int | None] = mapped_column(BigInteger)
    key_obj_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("m70_object.obj_id"))
    attribute_obj_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("m70_object.obj_id"))
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    sort_direction: Mapped[str] = mapped_column(String(4), server_default="'ASC'")

    __table_args__ = (Index("ix_m70_keymember_key", "key_obj_id", "version_from"),)


class M70RelationshipLogical(Base):
    __tablename__ = "m70_relationship_logical"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    version_from: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_to: Mapped[int | None] = mapped_column(BigInteger)
    parent_entity_obj_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("m70_object.obj_id"))
    child_entity_obj_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("m70_object.obj_id"))
    name: Mapped[str | None] = mapped_column(String(256))
    cardinality: Mapped[str | None] = mapped_column(String(32))
    is_identifying: Mapped[bool] = mapped_column(Boolean, server_default="false")

    __table_args__ = (
        Index("ix_m70_rel_log_parent", "parent_entity_obj_id", "version_from"),
        Index("ix_m70_rel_log_child", "child_entity_obj_id", "version_from"),
    )


class M70Domain(Base):
    __tablename__ = "m70_domain"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    version_from: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_to: Mapped[int | None] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(128))
    data_type: Mapped[str] = mapped_column(String(64))
    default_value: Mapped[str | None] = mapped_column(String(256))
    check_constraint: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_m70_domain_name", "name"),)


class M70GlossaryTerm(Base):
    __tablename__ = "m70_glossary_term"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    version_from: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_to: Mapped[int | None] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(256))
    definition: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), server_default="'draft'")

    __table_args__ = (Index("ix_m70_glossary_name", "name"),)


class M70LineageEdge(Base):
    __tablename__ = "m70_lineage_edge"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    version_from: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_to: Mapped[int | None] = mapped_column(BigInteger)
    source_obj_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("m70_object.obj_id"))
    target_obj_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("m70_object.obj_id"))
    transformation_sql: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_m70_lineage_source", "source_obj_id", "version_from"),
        Index("ix_m70_lineage_target", "target_obj_id", "version_from"),
    )


class M70UDP(Base):
    __tablename__ = "m70_udp"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    version_from: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_to: Mapped[int | None] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(128))
    value_type: Mapped[str] = mapped_column(String(16))
