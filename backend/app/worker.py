"""审批事件后台处理进程。

企业微信要求回调秒级返回，回调接口只负责落库；出票、推送图片在这个进程里做。
失败会自动重试（最多 MAX_PROCESSING_ATTEMPTS 次），超过后标记为需人工处理。
"""

import asyncio
import logging
import os
import signal
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.wecom_event import WeComApprovalEvent
from app.services.wecom import MAX_PROCESSING_ATTEMPTS, ApprovalError, process_approval_event

logger = logging.getLogger("meal_ticket.worker")

POLL_SECONDS = float(os.getenv("WORKER_POLL_SECONDS", "3"))
STALE_MINUTES = int(os.getenv("WORKER_STALE_MINUTES", "10"))


def reset_stale_claims(db: Session) -> int:
    """回收崩溃/重启导致卡住的处理中标记。"""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_MINUTES)
    result = db.execute(
        update(WeComApprovalEvent)
        .where(WeComApprovalEvent.processing.is_(True))
        .where(WeComApprovalEvent.processing_at < cutoff)
        .values(processing=False, processing_at=None)
    )
    db.commit()
    return int(result.rowcount or 0)


def claim_event(db: Session) -> WeComApprovalEvent | None:
    """原子领取一条待处理事件，多进程同时跑也不会重复领取。"""
    candidate_id = db.scalar(
        select(WeComApprovalEvent.id)
        .where(WeComApprovalEvent.processed.is_(False))
        .where(WeComApprovalEvent.processing.is_(False))
        .where(WeComApprovalEvent.attempts < MAX_PROCESSING_ATTEMPTS)
        .order_by(WeComApprovalEvent.id.asc())
        .limit(1)
    )
    if candidate_id is None:
        return None
    claimed = db.execute(
        update(WeComApprovalEvent)
        .where(WeComApprovalEvent.id == candidate_id)
        .where(WeComApprovalEvent.processing.is_(False))
        .where(WeComApprovalEvent.processed.is_(False))
        .values(processing=True, processing_at=datetime.now(timezone.utc))
    )
    db.commit()
    if claimed.rowcount != 1:
        return None
    return db.get(WeComApprovalEvent, candidate_id)


def mark_failed(db: Session, event_id: int, message: str, retryable: bool) -> None:
    event = db.get(WeComApprovalEvent, event_id)
    if not event:
        return
    event.processing = False
    event.processing_at = None
    event.attempts = (event.attempts or 0) + 1
    event.last_error = message[:255]
    if not retryable or event.attempts >= MAX_PROCESSING_ATTEMPTS:
        event.processed = True
        event.process_result = (
            f"处理失败（第 {event.attempts} 次，需人工处理）：{message}"
        )[:255]
    else:
        event.process_result = f"待重试（第 {event.attempts} 次）：{message}"[:255]
    db.commit()
    logger.warning("审批事件处理失败 sp_no=%s attempts=%s: %s", event.sp_no, event.attempts, message)


def clear_claim(db: Session, event_id: int) -> None:
    event = db.get(WeComApprovalEvent, event_id)
    if event and event.processing:
        event.processing = False
        event.processing_at = None
        db.commit()


async def run_once() -> bool:
    db = SessionLocal()
    try:
        event = claim_event(db)
        if event is None:
            return False
        event_id = event.id
        sp_no = event.sp_no
        try:
            await process_approval_event(db, event)
        except ApprovalError as exc:
            db.rollback()
            mark_failed(db, event_id, str(exc), exc.retryable)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("审批事件处理异常 sp_no=%s", sp_no)
            mark_failed(db, event_id, f"{type(exc).__name__}: {exc}", True)
        else:
            clear_claim(db, event_id)
            logger.info("审批事件处理完成 sp_no=%s", sp_no)
        return True
    finally:
        db.close()


async def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info(
        "审批事件 worker 启动 poll=%ss attempts=%s",
        POLL_SECONDS,
        MAX_PROCESSING_ATTEMPTS,
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # pragma: no cover - Windows
            pass

    while not stop.is_set():
        try:
            worked = await run_once()
        except Exception:  # noqa: BLE001
            logger.exception("worker 主循环异常")
            worked = False
        if worked:
            continue
        try:
            await asyncio.wait_for(stop.wait(), timeout=POLL_SECONDS)
        except asyncio.TimeoutError:
            pass
        finally:
            db = SessionLocal()
            try:
                reset_stale_claims(db)
            except Exception:  # noqa: BLE001
                db.rollback()
            finally:
                db.close()
    logger.info("审批事件 worker 退出")


if __name__ == "__main__":
    asyncio.run(main())
