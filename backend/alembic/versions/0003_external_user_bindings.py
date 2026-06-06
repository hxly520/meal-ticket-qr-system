"""add external user sync and card bindings

Revision ID: 0003_external_user_bindings
Revises: 0002_multi_ticket_approval
Create Date: 2026-06-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_external_user_bindings"
down_revision: str | None = "0002_multi_ticket_approval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_user_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("department_code", sa.String(length=120), nullable=True),
        sa.Column("department_name", sa.String(length=120), nullable=True),
        sa.Column("employee_no", sa.String(length=120), nullable=True),
        sa.Column("card_no", sa.String(length=120), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "source",
            "external_id",
            name="uq_external_user_source_external_id",
        ),
    )
    op.create_table(
        "card_user_bindings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("wecom_userid", sa.String(length=120), nullable=False, unique=True),
        sa.Column("wanoa_pin", sa.String(length=120), nullable=False, unique=True),
        sa.Column("wecom_name", sa.String(length=120), nullable=True),
        sa.Column("wanoa_name", sa.String(length=120), nullable=True),
        sa.Column("wecom_department", sa.String(length=120), nullable=True),
        sa.Column("wanoa_department", sa.String(length=120), nullable=True),
        sa.Column("wanoa_card_no", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("last_balance", sa.Numeric(12, 2), nullable=True),
        sa.Column("balance_status", sa.String(length=30), nullable=True),
        sa.Column("balance_message", sa.String(length=255), nullable=True),
        sa.Column("last_balance_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "external_sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="running"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_external_user_candidates_source_name",
        "external_user_candidates",
        ["source", "name"],
    )
    op.create_index(
        "ix_card_user_bindings_names",
        "card_user_bindings",
        ["wecom_name", "wanoa_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_card_user_bindings_names", table_name="card_user_bindings")
    op.drop_index("ix_external_user_candidates_source_name", table_name="external_user_candidates")
    op.drop_table("external_sync_runs")
    op.drop_table("card_user_bindings")
    op.drop_table("external_user_candidates")
