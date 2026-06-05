import re
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.meal_ticket import MealTicket, VerificationLog
from app.models.user import User
from app.schemas.ticket import TicketCreate, TicketGenerate
from app.services.system_settings import get_runtime_settings
from app.utils.tokens import end_of_day, hash_token, new_token


def build_verify_url(token: str, base_url: str | None = None) -> str:
    return f"{(base_url or settings.app_base_url).rstrip('/')}/verify?token={token}"


def build_ticket_page_url(token: str, base_url: str | None = None) -> str:
    return f"{(base_url or settings.app_base_url).rstrip('/')}/ticket?token={token}"


def create_ticket(
    db: Session,
    payload: TicketCreate,
    *,
    source: str,
    created_by: int | None = None,
    approval_sp_no: str | None = None,
) -> tuple[MealTicket, str]:
    runtime = get_runtime_settings(db)
    token = new_token()
    ticket = MealTicket(
        ticket_no=f"MT{datetime.now(timezone.utc).strftime('%Y%m%d')}{uuid4().hex[:10].upper()}",
        employee_userid=payload.employee_userid,
        employee_name=payload.employee_name,
        department=payload.department,
        meal_date=payload.meal_date,
        meal_type=payload.meal_type,
        diner_count=payload.diner_count,
        diner_index=payload.diner_index,
        source=source,
        status="unused",
        token_hash=hash_token(token),
        expire_at=payload.expire_at or end_of_day(payload.meal_date, runtime.app_timezone),
        created_by=created_by,
        approval_sp_no=approval_sp_no,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket, token


def create_tickets_from_generate(
    db: Session,
    payload: TicketGenerate,
    *,
    source: str,
    created_by: int | None = None,
    approval_sp_no: str | None = None,
) -> list[tuple[MealTicket, str]]:
    rows: list[tuple[MealTicket, str]] = []
    for diner_index in range(1, payload.diner_count + 1):
        for meal_type in payload.meal_types:
            ticket_payload = TicketCreate(
                employee_userid=payload.employee_userid,
                employee_name=payload.employee_name,
                department=payload.department,
                meal_date=payload.meal_date,
                meal_type=meal_type,
                diner_count=payload.diner_count,
                diner_index=diner_index,
                expire_at=payload.expire_at,
            )
            rows.append(
                create_ticket(
                    db,
                    ticket_payload,
                    source=source,
                    created_by=created_by,
                    approval_sp_no=approval_sp_no,
                )
            )
    return rows


def find_ticket_by_token(db: Session, token: str) -> MealTicket | None:
    return db.scalar(select(MealTicket).where(MealTicket.token_hash == hash_token(token)))


def consume_ticket(db: Session, token: str, verifier: User, request: Request) -> MealTicket:
    token_hash = hash_token(token)
    runtime = get_runtime_settings(db)
    now = datetime.now(timezone.utc)
    ticket = db.scalar(select(MealTicket).where(MealTicket.token_hash == token_hash))
    if not ticket:
        _log(db, None, verifier.id, "failed", "二维码不存在", request)
        raise HTTPException(status_code=404, detail="二维码不存在")
    if ticket.status != "unused":
        status_error = ticket_status_error(ticket, runtime)
        _log(db, ticket.id, verifier.id, "failed", status_error, request)
        db.commit()
        raise HTTPException(status_code=409, detail=status_error)
    date_error = validate_meal_date(ticket, now, runtime)
    if date_error:
        if ticket.meal_date < local_today(now, runtime):
            ticket.status = "expired"
        _log(db, ticket.id, verifier.id, "failed", date_error, request)
        db.commit()
        raise HTTPException(status_code=409, detail=date_error)
    if ticket.expire_at < now:
        ticket.status = "expired"
        _log(db, ticket.id, verifier.id, "failed", "饭票已过期", request)
        db.commit()
        raise HTTPException(status_code=409, detail="饭票已过期")
    window_error = validate_meal_window(ticket, now, runtime)
    if window_error:
        _log(db, ticket.id, verifier.id, "failed", window_error, request)
        db.commit()
        raise HTTPException(status_code=409, detail=window_error)

    result = db.execute(
        update(MealTicket)
        .where(MealTicket.id == ticket.id, MealTicket.status == "unused")
        .values(status="used", used_at=now, used_by=verifier.id)
    )
    if result.rowcount != 1:
        _log(db, ticket.id, verifier.id, "failed", "饭票已被其他人员核销", request)
        db.commit()
        raise HTTPException(status_code=409, detail="饭票已被核销")
    _log(db, ticket.id, verifier.id, "success", None, request)
    db.commit()
    db.refresh(ticket)
    return ticket


def validate_meal_date(ticket: MealTicket, now: datetime, runtime) -> str | None:
    today = local_today(now, runtime)
    if ticket.meal_date == today:
        return None
    meal_date = ticket.meal_date.isoformat()
    today_text = today.isoformat()
    if ticket.meal_date < today:
        return f"饭票用餐日期为 {meal_date}，不是当天饭票，已变更为过期状态"
    return f"饭票用餐日期为 {meal_date}，当前日期为 {today_text}，未到用餐日期"


def ticket_status_error(ticket: MealTicket, runtime) -> str:
    if ticket.status == "used":
        used_at = format_local_datetime(ticket.used_at, runtime)
        suffix = f"（核销时间：{used_at}）" if used_at else ""
        return f"饭票已核销，不能重复核销{suffix}"
    if ticket.status == "expired":
        return "饭票已过期，不能核销"
    if ticket.status == "void":
        return "饭票已作废，不能核销"
    label = {"unused": "未使用", "used": "已核销", "expired": "已过期", "void": "已作废"}.get(
        ticket.status,
        ticket.status,
    )
    return f"饭票状态为 {label}，不能核销"


def format_local_datetime(value: datetime | None, runtime) -> str | None:
    if not value:
        return None
    timezone_name = runtime.app_timezone or settings.app_timezone
    return value.astimezone(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M:%S 北京时间")


def local_today(now: datetime, runtime) -> date:
    timezone_name = runtime.app_timezone or settings.app_timezone
    return now.astimezone(ZoneInfo(timezone_name)).date()


def validate_meal_window(ticket: MealTicket, now: datetime, runtime) -> str | None:
    window = {
        "breakfast": runtime.meal_window_breakfast,
        "lunch": runtime.meal_window_lunch,
        "dinner": runtime.meal_window_dinner,
    }.get(ticket.meal_type)
    parsed = parse_meal_window(window)
    if not parsed:
        return None

    start_time, end_time = parsed
    timezone_name = runtime.app_timezone or settings.app_timezone
    local_now = now.astimezone(ZoneInfo(timezone_name))
    start_at = datetime.combine(ticket.meal_date, start_time, tzinfo=ZoneInfo(timezone_name))
    end_at = datetime.combine(ticket.meal_date, end_time, tzinfo=ZoneInfo(timezone_name))
    if end_at < start_at:
        end_at = end_at + timedelta(days=1)

    if start_at <= local_now <= end_at:
        return None

    meal_label = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐"}.get(
        ticket.meal_type,
        ticket.meal_type,
    )
    return (
        f"当前时间不在{meal_label}核销时间段内"
        f"（{start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}，北京时间）"
    )


def parse_meal_window(value: str | None) -> tuple[time, time] | None:
    text = (value or "").strip()
    if not text:
        return None
    parts = re.split(r"\s*(?:-|~|至|到)\s*", text, maxsplit=1)
    if len(parts) != 2:
        return None
    try:
        return parse_clock(parts[0]), parse_clock(parts[1])
    except ValueError:
        return None


def parse_clock(value: str) -> time:
    hour, minute = value.strip().split(":", 1)
    return time(hour=int(hour), minute=int(minute))


def _log(
    db: Session,
    ticket_id: int | None,
    verifier_id: int | None,
    result: str,
    reason: str | None,
    request: Request,
) -> None:
    db.add(
        VerificationLog(
            ticket_id=ticket_id,
            verifier_id=verifier_id,
            result=result,
            reason=reason,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
