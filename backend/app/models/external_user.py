from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExternalUserCandidate(Base):
    __tablename__ = "external_user_candidates"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_external_user_source_external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    department_code: Mapped[str | None] = mapped_column(String(120))
    department_name: Mapped[str | None] = mapped_column(String(120))
    employee_no: Mapped[str | None] = mapped_column(String(120))
    card_no: Mapped[str | None] = mapped_column(String(120))
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CardUserBinding(Base):
    __tablename__ = "card_user_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wecom_userid: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    wanoa_pin: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    wecom_name: Mapped[str | None] = mapped_column(String(120))
    wanoa_name: Mapped[str | None] = mapped_column(String(120))
    wecom_department: Mapped[str | None] = mapped_column(String(120))
    wanoa_department: Mapped[str | None] = mapped_column(String(120))
    wanoa_card_no: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    last_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    balance_status: Mapped[str | None] = mapped_column(String(30))
    balance_message: Mapped[str | None] = mapped_column(String(255))
    last_balance_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ExternalSyncRun(Base):
    __tablename__ = "external_sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
