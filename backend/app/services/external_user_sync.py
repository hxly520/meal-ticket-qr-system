import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.external_user import CardUserBinding, ExternalSyncRun, ExternalUserCandidate
from app.services.system_settings import get_runtime_settings
from app.services.wanoa import WanoaClient, sync_wanoa_candidates, upsert_candidate
from app.services.wecom import WeComClient


async def run_user_sync(
    db: Session,
    source: str,
    *,
    name: str | None = None,
    page_size: int | None = None,
) -> ExternalSyncRun:
    run = ExternalSyncRun(source=source, status="running")
    db.add(run)
    db.commit()
    try:
        if source == "wanoa":
            total = await sync_wanoa_candidates(db, name=name, page_size=page_size)
        elif source == "wecom":
            total = await sync_wecom_candidates(db)
        elif source == "all":
            total = await sync_all_sources(db)
        else:
            raise HTTPException(status_code=400, detail="不支持的同步来源")
        bound = auto_bind_candidates(db) if source in {"all", "wanoa", "wecom"} else 0
        balance_synced, balance_failed = await refresh_bound_card_balances(db)
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.message = str(getattr(exc, "detail", exc))
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise
    run.status = "success"
    run.total = total
    run.message = (
        f"已同步 {total} 个用户，自动绑定 {bound} 个，"
        f"刷新余额 {balance_synced} 个"
        + (f"，余额失败 {balance_failed} 个" if balance_failed else "")
    )
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    return run


async def sync_all_sources(db: Session) -> int:
    total = await sync_wecom_candidates(db)
    total += await sync_wanoa_candidates(db)
    return total


async def sync_wecom_candidates(db: Session) -> int:
    runtime = get_runtime_settings(db)
    client = WeComClient(runtime)
    token = await client.get_access_token()
    departments = await fetch_wecom_departments(token)
    synced: set[str] = set()
    total = 0
    async with httpx.AsyncClient(timeout=15) as http:
        for department in departments:
            department_id = department.get("id")
            if not department_id:
                continue
            resp = await http.get(
                "https://qyapi.weixin.qq.com/cgi-bin/user/list",
                params={
                    "access_token": token,
                    "department_id": department_id,
                    "fetch_child": 0,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") != 0:
                raise HTTPException(status_code=502, detail=f"企业微信用户同步失败: {data}")
            for item in data.get("userlist", []):
                userid = str(item.get("userid") or "").strip()
                name = str(item.get("name") or "").strip()
                if not userid or not name or userid in synced:
                    continue
                synced.add(userid)
                department_ids = set(item.get("department") or [])
                department_names = [
                    dept.get("name")
                    for dept in departments
                    if dept.get("id") in department_ids
                ]
                upsert_candidate(
                    db,
                    source="wecom",
                    external_id=userid,
                    name=name,
                    department_code=",".join(str(v) for v in item.get("department") or []) or None,
                    department_name=" / ".join(filter(None, department_names)) or None,
                    employee_no=str(item.get("biz_mail") or item.get("email") or "").strip() or None,
                    raw_payload=sanitize_wecom_payload(item),
                )
                total += 1
        db.commit()
    return total


async def fetch_wecom_departments(token: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://qyapi.weixin.qq.com/cgi-bin/department/list",
            params={"access_token": token},
        )
        resp.raise_for_status()
        data = resp.json()
    if data.get("errcode") != 0:
        raise HTTPException(status_code=502, detail=f"企业微信部门同步失败: {data}")
    return data.get("department", [])


def sanitize_wecom_payload(item: dict[str, Any]) -> dict[str, Any]:
    blocked_keys = {"avatar", "qr_code", "thumb_avatar"}
    return {key: value for key, value in item.items() if key not in blocked_keys}


def auto_bind_candidates(db: Session) -> int:
    runtime = get_runtime_settings(db)
    if not runtime.external_user_auto_bind_enabled:
        return 0

    names = list(
        db.scalars(
            select(ExternalUserCandidate.name)
            .group_by(ExternalUserCandidate.name)
            .having(func.count(func.distinct(ExternalUserCandidate.source)) == 2)
        ).all()
    )
    bound = 0
    for name in names:
        wecom_rows = list(
            db.scalars(
                select(ExternalUserCandidate).where(
                    ExternalUserCandidate.source == "wecom",
                    ExternalUserCandidate.name == name,
                )
            ).all()
        )
        wanoa_rows = list(
            db.scalars(
                select(ExternalUserCandidate).where(
                    ExternalUserCandidate.source == "wanoa",
                    ExternalUserCandidate.name == name,
                )
            ).all()
        )
        if len(wecom_rows) != 1 or len(wanoa_rows) != 1:
            continue
        wecom = wecom_rows[0]
        wanoa = wanoa_rows[0]
        existing = db.scalar(
            select(CardUserBinding).where(
                or_(
                    CardUserBinding.wecom_userid == wecom.external_id,
                    CardUserBinding.wanoa_pin == wanoa.external_id,
                )
            )
        )
        if existing:
            continue
        db.add(
            CardUserBinding(
                wecom_userid=wecom.external_id,
                wanoa_pin=wanoa.external_id,
                wecom_name=wecom.name,
                wanoa_name=wanoa.name,
                wecom_department=wecom.department_name,
                wanoa_department=wanoa.department_name,
                wanoa_card_no=wanoa.card_no,
                status="active",
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        bound += 1
    return bound


async def refresh_bound_card_balances(db: Session) -> tuple[int, int]:
    runtime = get_runtime_settings(db)
    if not runtime.wanoa_balance_path:
        return 0, 0
    try:
        client = WanoaClient(runtime)
    except HTTPException:
        return 0, 0

    rows = list(
        db.scalars(
            select(CardUserBinding).where(
                CardUserBinding.status == "active",
                CardUserBinding.wanoa_pin.is_not(None),
            )
        ).all()
    )
    synced = 0
    failed = 0
    now = datetime.now(timezone.utc)
    for binding in rows:
        try:
            account_info = await client.account_info(
                pin=binding.wanoa_pin,
                card_no=binding.wanoa_card_no,
            )
        except Exception as exc:  # noqa: BLE001
            failed += 1
            binding.balance_status = "failed"
            binding.balance_message = str(getattr(exc, "detail", exc))[:255]
            binding.last_balance_at = now
            continue
        binding.last_balance = account_info["balance"]
        binding.balance_status = "success"
        binding.balance_message = "同步用户时刷新余额"
        binding.last_balance_at = now
        synced += 1
    db.commit()
    return synced, failed


class ExternalUserSyncScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        while not self._stopping.is_set():
            interval_minutes = 60
            try:
                with SessionLocal() as db:
                    runtime = get_runtime_settings(db)
                    interval_minutes = runtime.external_user_sync_interval_minutes
                    if runtime.external_user_sync_enabled:
                        await run_user_sync(db, "all")
            except Exception:  # noqa: BLE001
                pass
            try:
                await asyncio.wait_for(
                    self._stopping.wait(),
                    timeout=max(interval_minutes, 5) * 60,
                )
            except TimeoutError:
                continue


external_user_sync_scheduler = ExternalUserSyncScheduler()
