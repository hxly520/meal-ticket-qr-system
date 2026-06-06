from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SyncLogOut(BaseModel):
    id: int
    source: str
    status: str
    total: int
    message: str | None
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class AccessLogOut(BaseModel):
    id: int
    ticket_id: int | None
    ticket_no: str | None = None
    verifier_id: int | None
    verifier_name: str | None = None
    result: str
    reason: str | None
    ip: str | None
    user_agent: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: int
    actor_id: int | None
    actor_name: str | None = None
    action: str
    target_type: str
    target_id: str | None
    detail: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class LogPage(BaseModel):
    items: list[SyncLogOut] | list[AccessLogOut] | list[AuditLogOut]
    total: int
    page: int
    page_size: int
