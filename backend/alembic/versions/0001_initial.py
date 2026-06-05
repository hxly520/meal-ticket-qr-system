"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("wecom_userid", sa.String(length=120), nullable=True, unique=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("roles", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "meal_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket_no", sa.String(length=40), nullable=False, unique=True),
        sa.Column("employee_userid", sa.String(length=120), nullable=True),
        sa.Column("employee_name", sa.String(length=120), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("meal_date", sa.Date(), nullable=False),
        sa.Column("meal_type", sa.String(length=20), nullable=False),
        sa.Column("diner_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("diner_index", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="unused"),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approval_sp_no", sa.String(length=120), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "wecom_approval_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sp_no", sa.String(length=120), nullable=False, unique=True),
        sa.Column("template_id", sa.String(length=120), nullable=True),
        sa.Column("applicant_userid", sa.String(length=120), nullable=True),
        sa.Column("sp_status", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("process_result", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "verification_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("meal_tickets.id"), nullable=True),
        sa.Column("verifier_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("ip", sa.String(length=80), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=80), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=120), nullable=False, unique=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_table("audit_logs")
    op.drop_table("verification_logs")
    op.drop_table("wecom_approval_events")
    op.drop_table("meal_tickets")
    op.drop_table("users")
