from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.external_user import CardUserBinding, ExternalUserCandidate
from app.schemas.external_user import PublicCardBalanceResult
from app.services.system_settings import get_runtime_settings
from app.services.wanoa import WanoaClient
from app.services.wecom import (
    WeComClient,
    parse_encrypted_approval_event,
    parse_plain_approval_event,
    record_and_process_approval_event,
    verify_callback_echo,
)

router = APIRouter(prefix="/wecom", tags=["wecom"])


@router.get("/callback/approval", response_class=PlainTextResponse)
def verify_approval_callback(
    msg_signature: str | None = Query(default=None),
    timestamp: str | None = Query(default=None),
    nonce: str | None = Query(default=None),
    echostr: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> str:
    runtime = get_runtime_settings(db)
    return verify_callback_echo(runtime, msg_signature, timestamp, nonce, echostr)


@router.post("/callback/approval")
async def approval_callback(request: Request, db: Session = Depends(get_db)):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
        event = parse_plain_approval_event(payload)
        row = await record_and_process_approval_event(db, event)
        return JSONResponse({"ok": True, "sp_no": row.sp_no, "processed": row.processed})
    else:
        runtime = get_runtime_settings(db)
        body = (await request.body()).decode("utf-8")
        event = parse_encrypted_approval_event(
            runtime,
            body,
            request.query_params.get("msg_signature"),
            request.query_params.get("timestamp"),
            request.query_params.get("nonce"),
        )
    row = await record_and_process_approval_event(db, event)
    _ = row
    return PlainTextResponse("success")


@router.get("/oauth-url")
def oauth_url(
    redirect_uri: str | None = None,
    state: str = "meal-card",
    db: Session = Depends(get_db),
) -> dict[str, str]:
    runtime = get_runtime_settings(db)
    if not runtime.wecom_corp_id or not runtime.wecom_agent_id:
        raise HTTPException(status_code=400, detail="企业微信 CorpID 或 AgentID 未配置")
    entry_url = f"{runtime.app_base_url.rstrip('/')}/my-card"
    redirect_target = normalize_redirect_uri(redirect_uri, entry_url)
    params = urlencode(
        {
            "appid": runtime.wecom_corp_id,
            "redirect_uri": redirect_target,
            "response_type": "code",
            "scope": "snsapi_base",
            "agentid": runtime.wecom_agent_id,
            "state": state or "meal-card",
        }
    )
    return {
        "entry_url": entry_url,
        "redirect_uri": redirect_target,
        "url": f"https://open.weixin.qq.com/connect/oauth2/authorize?{params}#wechat_redirect",
    }


@router.get("/card-balance", response_model=PublicCardBalanceResult)
async def card_balance(
    code: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> PublicCardBalanceResult:
    runtime = get_runtime_settings(db)
    try:
        userid = await WeComClient(runtime).get_userid_by_oauth_code(code)
    except Exception:  # noqa: BLE001
        return PublicCardBalanceResult(
            status="oauth_failed",
            message="企业微信授权已失效，请从企业微信自建应用重新打开",
        )
    return await build_card_balance(db, userid)


def normalize_redirect_uri(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    parsed_value = urlparse(value)
    parsed_fallback = urlparse(fallback)
    if parsed_value.scheme not in {"http", "https"}:
        return fallback
    if parsed_value.netloc != parsed_fallback.netloc:
        return fallback
    return value


async def build_card_balance(db: Session, userid: str) -> PublicCardBalanceResult:
    wecom = db.scalar(
        select(ExternalUserCandidate).where(
            ExternalUserCandidate.source == "wecom",
            ExternalUserCandidate.external_id == userid,
        )
    )
    binding = db.scalar(select(CardUserBinding).where(CardUserBinding.wecom_userid == userid))
    if not binding:
        return PublicCardBalanceResult(
            status="unbound",
            message="当前企业微信用户尚未绑定万傲饭卡，请联系行政或IT处理",
            wecom_userid=userid,
            wecom_name=wecom.name if wecom else None,
            wecom_department=wecom.department_name if wecom else None,
        )

    runtime = get_runtime_settings(db)
    now = datetime.now(timezone.utc)
    refreshed_at = None
    message = "已读取最近一次同步余额"
    try:
        account_info = await WanoaClient(runtime).account_info(
            pin=binding.wanoa_pin,
            card_no=binding.wanoa_card_no,
        )
    except Exception as exc:  # noqa: BLE001
        binding.balance_status = "failed"
        binding.balance_message = str(getattr(exc, "detail", exc))[:255]
        binding.last_balance_at = binding.last_balance_at or now
        message = "实时刷新失败，已显示最近一次同步余额"
    else:
        binding.last_balance = account_info["balance"]
        binding.balance_status = "success"
        binding.balance_message = "自建应用打开时刷新余额"
        binding.last_balance_at = now
        refreshed_at = now
        message = "余额刷新成功"
    db.commit()
    db.refresh(binding)
    return PublicCardBalanceResult(
        status="success" if binding.last_balance is not None else "no_balance",
        message=message,
        wecom_userid=binding.wecom_userid,
        wecom_name=binding.wecom_name or (wecom.name if wecom else None),
        wecom_department=binding.wecom_department or (wecom.department_name if wecom else None),
        wanoa_pin=binding.wanoa_pin,
        wanoa_name=binding.wanoa_name,
        wanoa_department=binding.wanoa_department,
        wanoa_card_no=binding.wanoa_card_no,
        balance=binding.last_balance,
        balance_status=binding.balance_status,
        balance_message=binding.balance_message,
        last_balance_at=binding.last_balance_at,
        refreshed_at=refreshed_at,
    )
