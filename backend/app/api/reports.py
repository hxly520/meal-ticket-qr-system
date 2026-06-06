from io import BytesIO
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.meal_ticket import MealTicket
from app.models.user import User
from app.services.system_settings import get_runtime_settings

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/tickets.xlsx")
def export_tickets(
    status: str | None = None,
    keyword: str | None = None,
    meal_date_from: date | None = None,
    meal_date_to: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "hr", "auditor")),
) -> StreamingResponse:
    runtime = get_runtime_settings(db)
    timezone_name = runtime.app_timezone or "Asia/Shanghai"
    wb = Workbook()
    ws = wb.active
    ws.title = "饭票记录"
    ws.append(
        [
            "饭票编号",
            "审批单号",
            "员工姓名",
            "部门",
            "用餐日期",
            "餐别",
            "用餐人数",
            "第几人",
            "来源",
            "状态",
            "生成时间",
            "核销时间",
        ]
    )
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
    if meal_date_from:
        filters.append(MealTicket.meal_date >= meal_date_from)
    if meal_date_to:
        filters.append(MealTicket.meal_date <= meal_date_to)

    stmt = select(MealTicket).order_by(MealTicket.id.desc())
    if filters:
        stmt = stmt.where(*filters)
    rows = db.scalars(stmt.limit(5000)).all()
    for item in rows:
        ws.append(
            [
                item.ticket_no,
                item.approval_sp_no,
                item.employee_name,
                item.department,
                item.meal_date.isoformat(),
                item.meal_type,
                item.diner_count,
                item.diner_index,
                item.source,
                item.status,
                format_local_datetime(item.created_at, timezone_name),
                format_local_datetime(item.used_at, timezone_name),
            ]
        )
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="meal-tickets.xlsx"'},
    )


def format_local_datetime(value: datetime | None, timezone_name: str) -> str:
    if not value:
        return ""
    return value.astimezone(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M:%S")
