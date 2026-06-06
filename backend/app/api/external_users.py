from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.external_user import CardUserBinding, ExternalUserCandidate
from app.models.user import User
from app.schemas.external_user import (
    BalanceLookup,
    BalanceResult,
    BindingPage,
    CandidatePage,
    CardUserBindingCreate,
    CardUserBindingOut,
    CardUserBindingUpdate,
    ExternalUserCandidateOut,
    SyncResult,
    WecomUserBindingOut,
    WecomUserBindingPage,
)
from app.services.external_user_sync import run_user_sync
from app.services.system_settings import get_runtime_settings
from app.services.wanoa import WanoaClient, sync_wanoa_candidates

router = APIRouter(prefix="/integrations/users", tags=["external-users"])


@router.get("/candidates", response_model=CandidatePage)
def list_candidates(
    source: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "hr", "auditor")),
) -> CandidatePage:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    filters = []
    if source:
        filters.append(ExternalUserCandidate.source == source)
    if keyword:
        like = f"%{keyword}%"
        filters.append(
            or_(
                ExternalUserCandidate.name.ilike(like),
                ExternalUserCandidate.external_id.ilike(like),
                ExternalUserCandidate.department_name.ilike(like),
                ExternalUserCandidate.card_no.ilike(like),
            )
        )
    total_stmt = select(func.count()).select_from(ExternalUserCandidate)
    list_stmt = select(ExternalUserCandidate).order_by(
        ExternalUserCandidate.synced_at.desc(),
        ExternalUserCandidate.id.desc(),
    )
    if filters:
        total_stmt = total_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)
    total = db.scalar(total_stmt) or 0
    items = db.scalars(list_stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return CandidatePage(
        items=[ExternalUserCandidateOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/sync/all", response_model=SyncResult)
async def sync_all_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> SyncResult:
    run = await run_user_sync(db, "all")
    return SyncResult(source="all", total=run.total, message=run.message)


@router.get("/bindings", response_model=BindingPage)
def list_bindings(
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "hr", "auditor")),
) -> BindingPage:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    filters = []
    if keyword:
        like = f"%{keyword}%"
        filters.append(
            or_(
                CardUserBinding.wecom_userid.ilike(like),
                CardUserBinding.wanoa_pin.ilike(like),
                CardUserBinding.wecom_name.ilike(like),
                CardUserBinding.wanoa_name.ilike(like),
                CardUserBinding.wanoa_card_no.ilike(like),
            )
        )
    total_stmt = select(func.count()).select_from(CardUserBinding)
    list_stmt = select(CardUserBinding).order_by(CardUserBinding.id.desc())
    if filters:
        total_stmt = total_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)
    total = db.scalar(total_stmt) or 0
    rows = db.scalars(list_stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return BindingPage(
        items=[CardUserBindingOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/wecom-bindings", response_model=WecomUserBindingPage)
def list_wecom_user_bindings(
    keyword: str | None = None,
    binding_status: str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "hr", "auditor")),
) -> WecomUserBindingPage:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    filters = [ExternalUserCandidate.source == "wecom"]
    join_condition = CardUserBinding.wecom_userid == ExternalUserCandidate.external_id
    if keyword:
        like = f"%{keyword}%"
        filters.append(
            or_(
                ExternalUserCandidate.name.ilike(like),
                ExternalUserCandidate.external_id.ilike(like),
                ExternalUserCandidate.department_name.ilike(like),
            )
        )
    if binding_status == "bound":
        filters.append(CardUserBinding.id.is_not(None))
    elif binding_status == "unbound":
        filters.append(CardUserBinding.id.is_(None))
    sortable_columns = {
        "wecom_name": ExternalUserCandidate.name,
        "wecom_userid": ExternalUserCandidate.external_id,
        "wecom_department": ExternalUserCandidate.department_name,
        "wanoa_name": CardUserBinding.wanoa_name,
        "wanoa_department": CardUserBinding.wanoa_department,
        "wanoa_card_no": CardUserBinding.wanoa_card_no,
        "last_balance": CardUserBinding.last_balance,
        "last_balance_at": CardUserBinding.last_balance_at,
        "binding_status": CardUserBinding.status,
    }
    order_column = sortable_columns.get(sort_by or "")
    order_desc = sort_order in {"descending", "desc"}
    if order_column is not None:
        primary_order = order_column.desc() if order_desc else order_column.asc()
        order_by = [
            primary_order.nullslast(),
            ExternalUserCandidate.name.asc(),
            ExternalUserCandidate.id.asc(),
        ]
    else:
        order_by = [ExternalUserCandidate.name.asc(), ExternalUserCandidate.id.asc()]
    total_stmt = (
        select(func.count())
        .select_from(ExternalUserCandidate)
        .outerjoin(CardUserBinding, join_condition)
        .where(*filters)
    )
    list_stmt = (
        select(ExternalUserCandidate, CardUserBinding)
        .outerjoin(CardUserBinding, join_condition)
        .where(*filters)
        .order_by(*order_by)
    )
    total = db.scalar(total_stmt) or 0
    rows = db.execute(list_stmt.offset((page - 1) * page_size).limit(page_size)).all()
    items = []
    for row, binding in rows:
        items.append(
            WecomUserBindingOut(
                wecom_userid=row.external_id,
                wecom_name=row.name,
                wecom_department=row.department_name,
                wanoa_pin=binding.wanoa_pin if binding else None,
                wanoa_name=binding.wanoa_name if binding else None,
                wanoa_department=binding.wanoa_department if binding else None,
                wanoa_card_no=binding.wanoa_card_no if binding else None,
                binding_status=binding.status if binding else None,
                last_balance=binding.last_balance if binding else None,
                last_balance_at=binding.last_balance_at if binding else None,
            )
        )
    return WecomUserBindingPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/bindings", response_model=CardUserBindingOut)
def create_binding(
    payload: CardUserBindingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> CardUserBinding:
    wecom = get_candidate(db, "wecom", payload.wecom_userid)
    wanoa = get_candidate(db, "wanoa", payload.wanoa_pin)
    binding = db.scalar(
        select(CardUserBinding).where(CardUserBinding.wecom_userid == payload.wecom_userid)
    )
    wanoa_binding = db.scalar(
        select(CardUserBinding).where(CardUserBinding.wanoa_pin == payload.wanoa_pin)
    )
    if wanoa_binding and (not binding or wanoa_binding.id != binding.id):
        raise HTTPException(status_code=409, detail="该万傲用户已绑定其他企业微信用户")
    if not binding:
        binding = CardUserBinding(wecom_userid=payload.wecom_userid, wanoa_pin=payload.wanoa_pin)
        db.add(binding)
    binding.wanoa_pin = payload.wanoa_pin
    fill_binding(binding, wecom, wanoa, user.id)
    db.commit()
    db.refresh(binding)
    return binding


@router.put("/bindings/{binding_id}", response_model=CardUserBindingOut)
def update_binding(
    binding_id: int,
    payload: CardUserBindingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> CardUserBinding:
    binding = db.get(CardUserBinding, binding_id)
    if not binding:
        raise HTTPException(status_code=404, detail="绑定记录不存在")
    wecom_userid = payload.wecom_userid or binding.wecom_userid
    wanoa_pin = payload.wanoa_pin or binding.wanoa_pin
    wecom = get_candidate(db, "wecom", wecom_userid)
    wanoa = get_candidate(db, "wanoa", wanoa_pin)
    wanoa_binding = db.scalar(
        select(CardUserBinding).where(
            CardUserBinding.wanoa_pin == wanoa_pin,
            CardUserBinding.id != binding.id,
        )
    )
    if wanoa_binding:
        raise HTTPException(status_code=409, detail="该万傲用户已绑定其他企业微信用户")
    binding.wecom_userid = wecom_userid
    binding.wanoa_pin = wanoa_pin
    if payload.status:
        binding.status = payload.status
    fill_binding(binding, wecom, wanoa, user.id)
    db.commit()
    db.refresh(binding)
    return binding


@router.post("/balance", response_model=BalanceResult)
async def lookup_balance(
    payload: BalanceLookup,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "hr", "auditor")),
) -> BalanceResult:
    target = await resolve_balance_target(db, payload)
    runtime = get_runtime_settings(db)
    binding = target.get("binding")
    candidate = target["candidate"]
    pin = candidate.external_id
    card_no = candidate.card_no
    if not runtime.wanoa_balance_path:
        return BalanceResult(
            status="unconfigured",
            message="已查到万傲人员和饭卡，但离线消费余额接口未配置",
            name=candidate.name,
            department=candidate.department_name,
            wecom_userid=binding.wecom_userid if binding else None,
            wanoa_pin=pin,
            card_no=card_no,
        )

    client = WanoaClient(runtime)
    account_info = await client.account_info(pin=pin, card_no=card_no)
    account = account_info["account"]
    balance = account_info["balance"]
    now = datetime.now(timezone.utc)
    if binding:
        binding.last_balance = balance
        binding.balance_status = "success"
        binding.balance_message = "余额查询成功"
        binding.last_balance_at = now
        db.commit()
    return BalanceResult(
        status="success",
        message="余额查询成功",
        name=candidate.name,
        department=candidate.department_name,
        wecom_userid=binding.wecom_userid if binding else None,
        wanoa_pin=pin,
        card_no=card_no,
        account_no=str(account.get("accountNo") or "") or None,
        balance=balance,
        money_wallet=account_info["money_wallet"],
        allowance_wallet=account_info["allowance_wallet"],
        available=parse_wanoa_available(account.get("available")),
        account_kind_name=str(account.get("accountKindName") or "") or None,
        balance_at=now,
    )


def parse_wanoa_available(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    try:
        return int(value) == 0
    except (TypeError, ValueError):
        return None


def get_candidate(db: Session, source: str, external_id: str) -> ExternalUserCandidate:
    row = db.scalar(
        select(ExternalUserCandidate).where(
            ExternalUserCandidate.source == source,
            ExternalUserCandidate.external_id == external_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"未找到 {source} 用户候选: {external_id}")
    return row


def fill_binding(
    binding: CardUserBinding,
    wecom: ExternalUserCandidate,
    wanoa: ExternalUserCandidate,
    confirmed_by: int,
) -> None:
    binding.wecom_userid = wecom.external_id
    binding.wanoa_pin = wanoa.external_id
    binding.wecom_name = wecom.name
    binding.wanoa_name = wanoa.name
    binding.wecom_department = wecom.department_name
    binding.wanoa_department = wanoa.department_name
    binding.wanoa_card_no = wanoa.card_no
    binding.confirmed_by = confirmed_by


async def resolve_balance_target(db: Session, payload: BalanceLookup) -> dict[str, Any]:
    binding = None
    candidate = None
    if payload.wanoa_pin:
        candidate = get_candidate(db, "wanoa", payload.wanoa_pin)
        binding = db.scalar(select(CardUserBinding).where(CardUserBinding.wanoa_pin == payload.wanoa_pin))
    elif payload.wecom_userid:
        binding = db.scalar(select(CardUserBinding).where(CardUserBinding.wecom_userid == payload.wecom_userid))
        if not binding:
            raise HTTPException(status_code=404, detail="该企业微信用户尚未绑定万傲人员")
        candidate = get_candidate(db, "wanoa", binding.wanoa_pin)
    elif payload.name:
        binding = db.scalar(
            select(CardUserBinding).where(
                or_(
                    CardUserBinding.wecom_name == payload.name,
                    CardUserBinding.wanoa_name == payload.name,
                )
            )
        )
        if binding:
            candidate = get_candidate(db, "wanoa", binding.wanoa_pin)
        else:
            candidate = db.scalar(
                select(ExternalUserCandidate).where(
                    ExternalUserCandidate.source == "wanoa",
                    ExternalUserCandidate.name == payload.name,
                )
            )
            if not candidate:
                await sync_wanoa_candidates(db, name=payload.name, page_size=20)
                candidate = db.scalar(
                    select(ExternalUserCandidate).where(
                        ExternalUserCandidate.source == "wanoa",
                        ExternalUserCandidate.name == payload.name,
                    )
                )
    if not candidate:
        raise HTTPException(status_code=404, detail="未找到可查询余额的万傲人员")
    return {"binding": binding, "candidate": candidate}
