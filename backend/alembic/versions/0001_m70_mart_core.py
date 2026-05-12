"""initial M70_* mart core schema (M1)

Revision ID: 0001
Revises:
Create Date: 2026-05-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── Users / groups ──────────────────────────────────────────
    op.create_table(
        "m70_user",
        sa.Column("user_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(128), nullable=False, unique=True),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("email", sa.String(256), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "m70_group",
        sa.Column("group_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
    )
    op.create_table(
        "m70_user_group",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("m70_user.user_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("group_id", sa.BigInteger(), sa.ForeignKey("m70_group.group_id", ondelete="CASCADE"), primary_key=True),
    )

    # ─── Identity hub ────────────────────────────────────────────
    op.create_table(
        "m70_object",
        sa.Column("obj_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("obj_type", sa.String(32), nullable=False),
        sa.Column("parent_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id", ondelete="CASCADE"), nullable=True),
        sa.Column("mart_id", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("m70_user.user_id"), nullable=True),
        sa.Column("created_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("modified_by", sa.BigInteger(), sa.ForeignKey("m70_user.user_id"), nullable=True),
        sa.Column("modified_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_m70_object_type", "m70_object", ["obj_type"])
    op.create_index("ix_m70_object_parent", "m70_object", ["parent_obj_id"])
    op.create_index("ix_m70_object_type_parent", "m70_object", ["obj_type", "parent_obj_id"])

    # ─── EAV (versioned) ─────────────────────────────────────────
    op.create_table(
        "m70_property_def",
        sa.Column("prop_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prop_name", sa.String(128), nullable=False),
        sa.Column("prop_type", sa.String(16), nullable=False),
        sa.Column("applies_to_obj_type", sa.String(32), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("prop_name", "applies_to_obj_type", name="uq_property_def_name_type"),
    )
    op.create_table(
        "m70_property",
        sa.Column("obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("prop_id", sa.Integer(), sa.ForeignKey("m70_property_def.prop_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("version_from", sa.BigInteger(), primary_key=True),
        sa.Column("version_to", sa.BigInteger(), nullable=True),
        sa.Column("val_string", sa.Text(), nullable=True),
        sa.Column("val_numeric", sa.Numeric(38, 10), nullable=True),
        sa.Column("val_clob", sa.Text(), nullable=True),
        sa.Column("val_blob", sa.LargeBinary(), nullable=True),
        sa.Column("val_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_m70_property_lookup", "m70_property", ["prop_id", "val_string"])
    op.create_index("ix_m70_property_at_version", "m70_property", ["obj_id", "version_from", "version_to"])

    op.create_table(
        "m70_relationship",
        sa.Column("rel_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("parent_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id", ondelete="CASCADE"), nullable=False),
        sa.Column("child_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id", ondelete="CASCADE"), nullable=False),
        sa.Column("rel_type", sa.String(32), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version_from", sa.BigInteger(), nullable=False),
        sa.Column("version_to", sa.BigInteger(), nullable=True),
        sa.Column("created_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_m70_rel_parent_type", "m70_relationship", ["parent_obj_id", "rel_type", "version_from"])
    op.create_index("ix_m70_rel_child_type", "m70_relationship", ["child_obj_id", "rel_type", "version_from"])

    # ─── Hierarchy (admin tables, not versioned) ─────────────────
    op.create_table(
        "m70_library",
        sa.Column("obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_user_id", sa.BigInteger(), sa.ForeignKey("m70_user.user_id"), nullable=True),
    )
    op.create_table(
        "m70_folder",
        sa.Column("obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("parent_folder_obj_id", sa.BigInteger(), sa.ForeignKey("m70_folder.obj_id"), nullable=True),
        sa.Column("library_obj_id", sa.BigInteger(), sa.ForeignKey("m70_library.obj_id"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
    )
    op.create_index("ix_m70_folder_parent", "m70_folder", ["parent_folder_obj_id"])
    op.create_index("ix_m70_folder_library", "m70_folder", ["library_obj_id"])

    op.create_table(
        "m70_model",
        sa.Column("obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("folder_obj_id", sa.BigInteger(), sa.ForeignKey("m70_folder.obj_id"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("model_type", sa.String(16), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_m70_model_folder", "m70_model", ["folder_obj_id"])

    # ─── Versioning ──────────────────────────────────────────────
    op.create_table(
        "m70_model_version",
        sa.Column("version_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("model_obj_id", sa.BigInteger(), sa.ForeignKey("m70_model.obj_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_num", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.BigInteger(), sa.ForeignKey("m70_user.user_id"), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_named", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("named_label", sa.String(128), nullable=True),
        sa.UniqueConstraint("model_obj_id", "version_num", name="uq_model_version_num"),
    )
    op.create_index("ix_m70_version_model", "m70_model_version", ["model_obj_id"])

    op.create_table(
        "m70_lock",
        sa.Column("obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("locked_by_user_id", sa.BigInteger(), sa.ForeignKey("m70_user.user_id"), nullable=False),
        sa.Column("locked_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_ts", sa.DateTime(timezone=True), nullable=True),
    )

    # ─── Permissions & audit ─────────────────────────────────────
    op.create_table(
        "m70_permission",
        sa.Column("perm_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("grantee_id", sa.BigInteger(), nullable=False),
        sa.Column("grantee_type", sa.String(16), nullable=False),
        sa.Column("obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id", ondelete="CASCADE"), nullable=False),
        sa.Column("perm_mask", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("granted_by", sa.BigInteger(), sa.ForeignKey("m70_user.user_id"), nullable=True),
        sa.Column("granted_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("grantee_id", "grantee_type", "obj_id", name="uq_perm_grantee_obj"),
    )
    op.create_index("ix_m70_perm_obj", "m70_permission", ["obj_id"])
    op.create_index("ix_m70_perm_grantee", "m70_permission", ["grantee_id", "grantee_type"])

    op.create_table(
        "m70_audit_log",
        sa.Column("audit_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("obj_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), sa.ForeignKey("m70_user.user_id"), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("details", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_m70_audit_obj_ts", "m70_audit_log", ["obj_id", "ts"])
    op.create_index("ix_m70_audit_action_ts", "m70_audit_log", ["action", "ts"])

    # ─── Convenience view replacing m70_model.current_version_id ─
    op.execute(
        """
        CREATE VIEW v_current_model_version AS
        SELECT
            mv.model_obj_id,
            mv.version_id   AS current_version_id,
            mv.version_num  AS current_version_num
        FROM m70_model_version mv
        JOIN (
            SELECT model_obj_id, MAX(version_num) AS max_num
            FROM m70_model_version
            GROUP BY model_obj_id
        ) latest
          ON latest.model_obj_id = mv.model_obj_id
         AND latest.max_num     = mv.version_num
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_current_model_version")
    op.drop_table("m70_audit_log")
    op.drop_table("m70_permission")
    op.drop_table("m70_lock")
    op.drop_table("m70_model_version")
    op.drop_table("m70_model")
    op.drop_table("m70_folder")
    op.drop_table("m70_library")
    op.drop_table("m70_relationship")
    op.drop_table("m70_property")
    op.drop_table("m70_property_def")
    op.drop_table("m70_object")
    op.drop_table("m70_user_group")
    op.drop_table("m70_group")
    op.drop_table("m70_user")
