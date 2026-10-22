"""ticket reason, push tracking and approval idempotency

Revision ID: 0005_ticket_reason_push
Revises: 0004_low_balance_alerts
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_ticket_reason_push"
down_revision: str | None = "0004_low_balance_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("meal_tickets", sa.Column("apply_reason", sa.String(length=500), nullable=True))
    op.add_column(
        "meal_tickets",
        sa.Column("push_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "meal_tickets",
        sa.Column("last_push_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "meal_tickets",
        sa.Column("last_push_error", sa.String(length=255), nullable=True),
    )

    op.add_column(
        "wecom_approval_events",
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "wecom_approval_events",
        sa.Column("last_error", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "wecom_approval_events",
        sa.Column("processing", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "wecom_approval_events",
        sa.Column("processing_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 历史数据回填：从审批报文的顶层中文字段里取申请原因
    op.execute(
        """
        UPDATE meal_tickets AS t
        SET apply_reason = left(e.raw_payload::jsonb ->> '申请原因', 500)
        FROM wecom_approval_events AS e
        WHERE t.approval_sp_no = e.sp_no
          AND t.apply_reason IS NULL
          AND (e.raw_payload::jsonb ->> '申请原因') IS NOT NULL
        """
    )

    # 幂等兜底：同一审批单+餐次+人序号唯一（手工票 approval_sp_no 为 NULL，不受影响）
    op.create_index(
        "uq_meal_tickets_approval_slot",
        "meal_tickets",
        ["approval_sp_no", "meal_type", "diner_index"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_meal_tickets_approval_slot", table_name="meal_tickets")
    op.drop_column("wecom_approval_events", "processing_at")
    op.drop_column("wecom_approval_events", "processing")
    op.drop_column("wecom_approval_events", "last_error")
    op.drop_column("wecom_approval_events", "attempts")
    op.drop_column("meal_tickets", "last_push_error")
    op.drop_column("meal_tickets", "last_push_at")
    op.drop_column("meal_tickets", "push_count")
    op.drop_column("meal_tickets", "apply_reason")
