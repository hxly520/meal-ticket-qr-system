from io import BytesIO

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.meal_ticket import MealTicket
from app.models.user import User
from app.schemas.ticket import (
    TicketBatchCreate,
    TicketBatchVoid,
    TicketBatchVoidResult,
    TicketCreate,
    TicketGenerate,
    TicketOut,
    TicketPage,
    VerifyConsume,
    VerifyPreview,
)
from app.services.tickets import (
    build_ticket_page_url,
    build_verify_url,
    consume_ticket,
    create_tickets_from_generate,
    create_ticket,
    find_ticket_by_token,
)
from app.services.system_settings import get_runtime_settings, normalize_department_display

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketOut)
def create_one(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hr")),
) -> TicketOut:
    ticket, token = create_ticket(db, payload, source="manual", created_by=user.id)
    out = TicketOut.model_validate(ticket)
    out.qr_url = build_ticket_page_url(token, get_runtime_settings(db).app_base_url)
    return out


@router.post("/generate", response_model=list[TicketOut])
def generate_tickets(
    payload: TicketGenerate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hr")),
) -> list[TicketOut]:
    rows: list[TicketOut] = []
    runtime = get_runtime_settings(db)
    for ticket, token in create_tickets_from_generate(
        db,
        payload,
        source="manual",
        created_by=user.id,
    ):
        out = TicketOut.model_validate(ticket)
        out.qr_url = build_ticket_page_url(token, runtime.app_base_url)
        rows.append(out)
    return rows


@router.post("/batch", response_model=list[TicketOut])
def create_batch(
    payload: TicketBatchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "hr")),
) -> list[TicketOut]:
    rows: list[TicketOut] = []
    for item in payload.tickets:
        ticket, token = create_ticket(db, item, source="batch", created_by=user.id)
        out = TicketOut.model_validate(ticket)
        out.qr_url = build_ticket_page_url(token, get_runtime_settings(db).app_base_url)
        rows.append(out)
    return rows


@router.get("", response_model=TicketPage)
def list_tickets(
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "hr", "auditor")),
) -> TicketPage:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    filters = []
    if status:
        filters.append(MealTicket.status == status)
    if keyword:
        like = f"%{keyword}%"
        filters.append(
            or_(
                MealTicket.employee_name.ilike(like),
                MealTicket.employee_userid.ilike(like),
                MealTicket.department.ilike(like),
                MealTicket.ticket_no.ilike(like),
                MealTicket.approval_sp_no.ilike(like),
            )
        )

    total_stmt = select(func.count()).select_from(MealTicket)
    list_stmt = select(MealTicket).order_by(MealTicket.id.desc())
    if filters:
        total_stmt = total_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)

    total = db.scalar(total_stmt) or 0
    items = db.scalars(list_stmt.offset((page - 1) * page_size).limit(page_size)).all()
    departments = load_user_department_map(db, items)
    runtime = get_runtime_settings(db)
    return TicketPage(
        items=[
            ticket_out(item, departments, runtime.wecom_department_mapping)
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{ticket_id}/void", response_model=TicketOut)
def void_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "hr")),
) -> MealTicket:
    ticket = db.get(MealTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="饭票不存在")
    if ticket.status == "used":
        raise HTTPException(status_code=409, detail="已核销饭票不能作废")
    ticket.status = "void"
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/void-batch", response_model=TicketBatchVoidResult)
def void_tickets_batch(
    payload: TicketBatchVoid,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "hr")),
) -> TicketBatchVoidResult:
    ids = list(dict.fromkeys(payload.ids))
    tickets = list(db.scalars(select(MealTicket).where(MealTicket.id.in_(ids))).all())
    by_id = {ticket.id: ticket for ticket in tickets}
    missing = len([item for item in ids if item not in by_id])
    updated = 0
    skipped_used = 0
    for ticket in tickets:
        if ticket.status == "used":
            skipped_used += 1
            continue
        if ticket.status != "void":
            ticket.status = "void"
            updated += 1
    db.commit()
    return TicketBatchVoidResult(updated=updated, skipped_used=skipped_used, missing=missing)


@router.get("/qr")
def qr_png(token: str, db: Session = Depends(get_db)) -> StreamingResponse:
    image = qrcode.make(build_verify_url(token, get_runtime_settings(db).app_base_url))
    buf = BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@router.get("/verify/preview", response_model=VerifyPreview)
def preview(token: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    ticket = find_ticket_by_token(db, token)
    if not ticket:
        raise HTTPException(status_code=404, detail="二维码不存在")
    runtime = get_runtime_settings(db)
    out = VerifyPreview.model_validate(ticket)
    out.department = normalize_department_display(out.department, runtime.wecom_department_mapping)
    if not out.department and ticket.employee_userid:
        user = db.scalar(select(User).where(User.wecom_userid == ticket.employee_userid))
        if user and user.department:
            out.department = user.department
    return out


@router.post("/verify/consume", response_model=TicketOut)
def consume(
    payload: VerifyConsume,
    request: Request,
    db: Session = Depends(get_db),
    verifier: User = Depends(require_roles("verifier")),
) -> TicketOut:
    ticket = consume_ticket(db, payload.token, verifier, request)
    runtime = get_runtime_settings(db)
    out = TicketOut.model_validate(ticket)
    out.department = normalize_department_display(out.department, runtime.wecom_department_mapping)
    return out


def load_user_department_map(db: Session, tickets: list[MealTicket]) -> dict[str, str]:
    userids = {
        item.employee_userid
        for item in tickets
        if item.employee_userid and not item.department
    }
    if not userids:
        return {}
    users = db.scalars(select(User).where(User.wecom_userid.in_(userids))).all()
    return {user.wecom_userid: user.department for user in users if user.wecom_userid and user.department}


def ticket_out(
    ticket: MealTicket,
    departments: dict[str, str],
    department_mapping: str | None,
) -> TicketOut:
    out = TicketOut.model_validate(ticket)
    out.department = normalize_department_display(out.department, department_mapping)
    if not out.department and ticket.employee_userid:
        out.department = departments.get(ticket.employee_userid)
    return out
