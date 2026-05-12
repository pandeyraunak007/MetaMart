"""M70 specialization tables (M2.5)

Adds SCD Type 2 specialization tables for the entity/attribute/key/relationship
domain, plus domains, glossary, lineage edges, and the UDP registry. All
versioned with the half-open `[version_from, version_to)` convention.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _versioned_pk_cols() -> list:
    return [
        sa.Column(
            "obj_id",
            sa.BigInteger(),
            sa.ForeignKey("m70_object.obj_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("version_from", sa.BigInteger(), primary_key=True),
        sa.Column("version_to", sa.BigInteger(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "m70_subject_area",
        *_versioned_pk_cols(),
        sa.Column("model_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_m70_subject_area_model", "m70_subject_area", ["model_obj_id", "version_from"])

    op.create_table(
        "m70_entity",
        *_versioned_pk_cols(),
        sa.Column("model_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id"), nullable=False),
        sa.Column("subject_area_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id"), nullable=True),
        sa.Column("logical_name", sa.String(256), nullable=False),
        sa.Column("physical_name", sa.String(256), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("is_view", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_staging", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_standalone", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_m70_entity_model", "m70_entity", ["model_obj_id", "version_from"])
    op.create_index("ix_m70_entity_sa", "m70_entity", ["subject_area_obj_id", "version_from"])
    op.create_index("ix_m70_entity_physical_name", "m70_entity", ["physical_name"])

    op.create_table(
        "m70_attribute",
        *_versioned_pk_cols(),
        sa.Column("entity_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id"), nullable=False),
        sa.Column("logical_name", sa.String(256), nullable=False),
        sa.Column("physical_name", sa.String(256), nullable=False),
        sa.Column("data_type", sa.String(64), nullable=False),
        sa.Column("is_nullable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("domain_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id"), nullable=True),
    )
    op.create_index("ix_m70_attribute_entity", "m70_attribute", ["entity_obj_id", "version_from"])
    op.create_index("ix_m70_attribute_physical_name", "m70_attribute", ["physical_name"])

    op.create_table(
        "m70_key",
        *_versioned_pk_cols(),
        sa.Column("entity_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id"), nullable=False),
        sa.Column("key_type", sa.String(8), nullable=False),
        sa.Column("name", sa.String(256), nullable=True),
    )
    op.create_index("ix_m70_key_entity", "m70_key", ["entity_obj_id", "version_from"])
    op.create_index("ix_m70_key_type", "m70_key", ["entity_obj_id", "key_type", "version_from"])

    op.create_table(
        "m70_key_member",
        *_versioned_pk_cols(),
        sa.Column("key_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id"), nullable=False),
        sa.Column("attribute_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_direction", sa.String(4), nullable=False, server_default="'ASC'"),
    )
    op.create_index("ix_m70_keymember_key", "m70_key_member", ["key_obj_id", "version_from"])

    op.create_table(
        "m70_relationship_logical",
        *_versioned_pk_cols(),
        sa.Column("parent_entity_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id"), nullable=False),
        sa.Column("child_entity_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id"), nullable=False),
        sa.Column("name", sa.String(256), nullable=True),
        sa.Column("cardinality", sa.String(32), nullable=True),
        sa.Column("is_identifying", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_m70_rel_log_parent", "m70_relationship_logical", ["parent_entity_obj_id", "version_from"])
    op.create_index("ix_m70_rel_log_child", "m70_relationship_logical", ["child_entity_obj_id", "version_from"])

    op.create_table(
        "m70_domain",
        *_versioned_pk_cols(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("data_type", sa.String(64), nullable=False),
        sa.Column("default_value", sa.String(256), nullable=True),
        sa.Column("check_constraint", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_m70_domain_name", "m70_domain", ["name"])

    op.create_table(
        "m70_glossary_term",
        *_versioned_pk_cols(),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="'draft'"),
    )
    op.create_index("ix_m70_glossary_name", "m70_glossary_term", ["name"])

    op.create_table(
        "m70_lineage_edge",
        *_versioned_pk_cols(),
        sa.Column("source_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id"), nullable=False),
        sa.Column("target_obj_id", sa.BigInteger(), sa.ForeignKey("m70_object.obj_id"), nullable=False),
        sa.Column("transformation_sql", sa.Text(), nullable=True),
    )
    op.create_index("ix_m70_lineage_source", "m70_lineage_edge", ["source_obj_id", "version_from"])
    op.create_index("ix_m70_lineage_target", "m70_lineage_edge", ["target_obj_id", "version_from"])

    op.create_table(
        "m70_udp",
        *_versioned_pk_cols(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("value_type", sa.String(16), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("m70_udp")
    op.drop_table("m70_lineage_edge")
    op.drop_table("m70_glossary_term")
    op.drop_table("m70_domain")
    op.drop_table("m70_relationship_logical")
    op.drop_table("m70_key_member")
    op.drop_table("m70_key")
    op.drop_table("m70_attribute")
    op.drop_table("m70_entity")
    op.drop_table("m70_subject_area")
