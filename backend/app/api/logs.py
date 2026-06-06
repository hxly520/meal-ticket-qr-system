from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.external_user import ExternalSyncRun
from app.models.meal_ticket import MealTicket, VerificationLog
from app.models.user import User
from app.schemas.logs import AccessLogOut, AuditLogOut, LogPage, SyncLogOut

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/sync", response_model=LogPage)
def list_sync_logs(
    source: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "hr", "auditor")),
) -> LogPage:
    page, page_size = normalize_page(page, page_size)
    filters = []
    if source:
        filters.append(ExternalSyncRun.source == source)
    if status:
        filters.append(ExternalSyncRun.status == status)
    total_stmt = select(func.count()).select_from(ExternalSyncRun)
    list_stmt = select(ExternalSyncRun).order_by(ExternalSyncRun.id.desc())
    if filters:
        total_stmt = total_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)
    total = db.scalar(total_stmt) or 0
    rows = db.scalars(list_stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return LogPage(
        items=[SyncLogOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/access", response_model=LogPage)
def list_access_logs(
    result: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "hr", "auditor")),
) -> LogPage:
    page, page_size = normalize_page(page, page_size)
    filters = []
    if result:
        filters.append(VerificationLog.result == result)
    if keyword:
        like = f"%{keyword}%"
        filters.append(
            or_(
                MealTicket.ticket_no.ilike(like),
                MealTicket.employee_name.ilike(like),
                VerificationLog.reason.ilike(like),
                VerificationLog.ip.ilike(like),
            )
        )
    total_stmt = (
        select(func.count())
        .select_from(VerificationLog)
        .outerjoin(MealTicket, VerificationLog.ticket_id == MealTicket.id)
    )
    list_stmt = (
        select(VerificationLog, MealTicket, User)
        .outerjoin(MealTicket, VerificationLog.ticket_id == MealTicket.id)
        .outerjoin(User, VerificationLog.verifier_id == User.id)
        .order_by(VerificationLog.id.desc())
    )
    if filters:
        total_stmt = total_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)
    total = db.scalar(total_stmt) or 0
    rows = db.execute(list_stmt.offset((page - 1) * page_size).limit(page_size)).all()
    items = [
        AccessLogOut(
            id=log.id,
            ticket_id=log.ticket_id,
            ticket_no=ticket.ticket_no if ticket else None,
            verifier_id=log.verifier_id,
            verifier_name=user.name if user else None,
            result=log.result,
            reason=log.reason,
            ip=log.ip,
            user_agent=log.user_agent,
            created_at=log.created_at,
        )
        for log, ticket, user in rows
    ]
    return LogPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/audit", response_model=LogPage)
def list_audit_logs(
    action: str | None = None,
    target_type: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "hr", "auditor")),
) -> LogPage:
    page, page_size = normalize_page(page, page_size)
    filters = []
    if action:
        filters.append(AuditLog.action.ilike(f"%{action}%"))
    if target_type:
        filters.append(AuditLog.target_type == target_type)
    if keyword:
        like = f"%{keyword}%"
        filters.append(or_(AuditLog.action.ilike(like), AuditLog.target_id.ilike(like)))
    total_stmt = select(func.count()).select_from(AuditLog)
    list_stmt = (
        select(AuditLog, User)
        .outerjoin(User, AuditLog.actor_id == User.id)
        .order_by(AuditLog.id.desc())
    )
    if filters:
        total_stmt = total_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)
    total = db.scalar(total_stmt) or 0
    rows = db.execute(list_stmt.offset((page - 1) * page_size).limit(page_size)).all()
    items = [
        AuditLogOut(
            id=log.id,
            actor_id=log.actor_id,
            actor_name=user.name if user else None,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            detail=log.detail or {},
            created_at=log.created_at,
        )
        for log, user in rows
    ]
    return LogPage(items=items, total=total, page=page, page_size=page_size)


def normalize_page(page: int, page_size: int) -> tuple[int, int]:
    return max(page, 1), min(max(page_size, 1), 100)
