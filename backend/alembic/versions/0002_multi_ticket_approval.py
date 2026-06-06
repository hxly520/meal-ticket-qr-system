"""support multiple tickets per approval

Revision ID: 0002_multi_ticket_approval
Revises: 0001_initial
Create Date: 2026-06-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_multi_ticket_approval"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("meal_tickets")}
    if "diner_count" not in columns:
        op.add_column(
            "meal_tickets",
            sa.Column("diner_count", sa.Integer(), nullable=False, server_default="1"),
        )
    if "diner_index" not in columns:
        op.add_column(
            "meal_tickets",
            sa.Column("diner_index", sa.Integer(), nullable=False, server_default="1"),
        )
    op.execute("ALTER TABLE meal_tickets DROP CONSTRAINT IF EXISTS meal_tickets_approval_sp_no_key")


def downgrade() -> None:
    op.create_unique_constraint(
        "meal_tickets_approval_sp_no_key",
        "meal_tickets",
        ["approval_sp_no"],
    )
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("meal_tickets")}
    if "diner_index" in columns:
        op.drop_column("meal_tickets", "diner_index")
    if "diner_count" in columns:
        op.drop_column("meal_tickets", "diner_count")
