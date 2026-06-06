"""add low balance alert tracking

Revision ID: 0004_low_balance_alerts
Revises: 0003_external_user_bindings
Create Date: 2026-06-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_low_balance_alerts"
down_revision: str | None = "0003_external_user_bindings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "card_user_bindings",
        sa.Column("low_balance_pushed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("card_user_bindings", "low_balance_pushed_at")
