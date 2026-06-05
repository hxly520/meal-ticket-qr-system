from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MealTicket(Base):
    __tablename__ = "meal_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    employee_userid: Mapped[str | None] = mapped_column(String(120))
    employee_name: Mapped[str] = mapped_column(String(120), nullable=False)
    department: Mapped[str | None] = mapped_column(String(120))
    meal_date: Mapped[date] = mapped_column(Date, nullable=False)
    meal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    diner_count: Mapped[int] = mapped_column(Integer, default=1)
    diner_index: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="unused")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approval_sp_no: Mapped[str | None] = mapped_column(String(120))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VerificationLog(Base):
    __tablename__ = "verification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("meal_tickets.id"))
    verifier_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(80))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
