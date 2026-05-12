"""SQLAlchemy mappers for the M70_* erwin Mart-compatible schema.

M1 scope: identity hub, hierarchy (library/folder/model), versioning anchor,
permissions, audit, and the EAV/relationship plumbing that specializations
in M2.5 will use. Entity/attribute/key specialization mappers land in M2.5.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from metamart.db import Base


# ─── Users / groups ───────────────────────────────────────────

class M70User(Base):
    __tablename__ = "m70_user"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), unique=True)
    display_name: Mapped[str] = mapped_column(String(256))
    email: Mapped[str | None] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class M70Group(Base):
    __tablename__ = "m70_group"
    group_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)


class M70UserGroup(Base):
    __tablename__ = "m70_user_group"
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_user.user_id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_group.group_id", ondelete="CASCADE"), primary_key=True
    )


# ─── Identity hub (NOT versioned) ─────────────────────────────

class M70Object(Base):
    __tablename__ = "m70_object"
    obj_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    obj_type: Mapped[str] = mapped_column(String(32))
    parent_obj_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE")
    )
    mart_id: Mapped[int] = mapped_column(BigInteger, server_default="1")
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("m70_user.user_id"))
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    modified_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("m70_user.user_id"))
    modified_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, server_default="false")

    __table_args__ = (
        Index("ix_m70_object_type", "obj_type"),
        Index("ix_m70_object_parent", "parent_obj_id"),
        Index("ix_m70_object_type_parent", "obj_type", "parent_obj_id"),
    )


# ─── EAV (versioned via SCD Type 2) ───────────────────────────

class M70PropertyDef(Base):
    __tablename__ = "m70_property_def"
    prop_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prop_name: Mapped[str] = mapped_column(String(128))
    prop_type: Mapped[str] = mapped_column(String(16))
    applies_to_obj_type: Mapped[str] = mapped_column(String(32))
    is_required: Mapped[bool] = mapped_column(Boolean, server_default="false")

    __table_args__ = (
        UniqueConstraint("prop_name", "applies_to_obj_type", name="uq_property_def_name_type"),
    )


class M70Property(Base):
    __tablename__ = "m70_property"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    prop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("m70_property_def.prop_id", ondelete="CASCADE"), primary_key=True
    )
    version_from: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_to: Mapped[int | None] = mapped_column(BigInteger)
    val_string: Mapped[str | None] = mapped_column(Text)
    val_numeric: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    val_clob: Mapped[str | None] = mapped_column(Text)
    val_blob: Mapped[bytes | None] = mapped_column(LargeBinary)
    val_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_m70_property_lookup", "prop_id", "val_string"),
        Index("ix_m70_property_at_version", "obj_id", "version_from", "version_to"),
    )


class M70Relationship(Base):
    __tablename__ = "m70_relationship"
    rel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE")
    )
    child_obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE")
    )
    rel_type: Mapped[str] = mapped_column(String(32))
    seq: Mapped[int] = mapped_column(Integer, server_default="0")
    version_from: Mapped[int] = mapped_column(BigInteger)
    version_to: Mapped[int | None] = mapped_column(BigInteger)
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_m70_rel_parent_type", "parent_obj_id", "rel_type", "version_from"),
        Index("ix_m70_rel_child_type", "child_obj_id", "rel_type", "version_from"),
    )


# ─── Hierarchy (administrative, NOT versioned) ────────────────

class M70Library(Base):
    __tablename__ = "m70_library"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("m70_user.user_id"))


class M70Folder(Base):
    __tablename__ = "m70_folder"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    parent_folder_obj_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("m70_folder.obj_id")
    )
    library_obj_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("m70_library.obj_id"))
    name: Mapped[str] = mapped_column(String(256))

    __table_args__ = (
        Index("ix_m70_folder_parent", "parent_folder_obj_id"),
        Index("ix_m70_folder_library", "library_obj_id"),
    )


class M70Model(Base):
    __tablename__ = "m70_model"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    folder_obj_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("m70_folder.obj_id"))
    name: Mapped[str] = mapped_column(String(256))
    model_type: Mapped[str] = mapped_column(String(16))
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_m70_model_folder", "folder_obj_id"),)


# ─── Versioning anchor ────────────────────────────────────────

class M70ModelVersion(Base):
    __tablename__ = "m70_model_version"
    version_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    model_obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_model.obj_id", ondelete="CASCADE")
    )
    version_num: Mapped[int] = mapped_column(Integer)
    author_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("m70_user.user_id"))
    comment: Mapped[str | None] = mapped_column(Text)
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_named: Mapped[bool] = mapped_column(Boolean, server_default="false")
    named_label: Mapped[str | None] = mapped_column(String(128))

    __table_args__ = (
        UniqueConstraint("model_obj_id", "version_num", name="uq_model_version_num"),
        Index("ix_m70_version_model", "model_obj_id"),
    )


class M70Lock(Base):
    __tablename__ = "m70_lock"
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True
    )
    locked_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("m70_user.user_id"))
    locked_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ─── Permissions & audit ──────────────────────────────────────

class M70Permission(Base):
    __tablename__ = "m70_permission"
    perm_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    grantee_id: Mapped[int] = mapped_column(BigInteger)
    grantee_type: Mapped[str] = mapped_column(String(16))
    obj_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("m70_object.obj_id", ondelete="CASCADE")
    )
    perm_mask: Mapped[int] = mapped_column(BigInteger, server_default="0")
    granted_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("m70_user.user_id"))
    granted_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("grantee_id", "grantee_type", "obj_id", name="uq_perm_grantee_obj"),
        Index("ix_m70_perm_obj", "obj_id"),
        Index("ix_m70_perm_grantee", "grantee_id", "grantee_type"),
    )


class M70AuditLog(Base):
    __tablename__ = "m70_audit_log"
    audit_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    obj_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(64))
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("m70_user.user_id"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    details: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_m70_audit_obj_ts", "obj_id", "ts"),
        Index("ix_m70_audit_action_ts", "action", "ts"),
    )


# perm_mask bitmask values
PERM_READ = 1
PERM_WRITE = 2
PERM_DELETE = 4
PERM_ADMIN = 8
PERM_MANAGE_PERMS = 16
PERM_MANAGE_RULES = 32
PERM_WAIVE_FINDINGS = 64
