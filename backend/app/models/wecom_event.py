from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WeComApprovalEvent(Base):
    __tablename__ = "wecom_approval_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sp_no: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    template_id: Mapped[str | None] = mapped_column(String(120))
    applicant_userid: Mapped[str | None] = mapped_column(String(120))
    sp_status: Mapped[int | None] = mapped_column(Integer)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    process_result: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
