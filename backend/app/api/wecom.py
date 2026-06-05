from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.system_settings import get_runtime_settings
from app.services.wecom import (
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
