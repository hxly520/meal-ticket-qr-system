from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from urllib.parse import parse_qsl

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.external_user import ExternalUserCandidate
from app.services.system_settings import RuntimeSettings, get_runtime_settings


class WanoaClient:
    def __init__(self, runtime: RuntimeSettings) -> None:
        if not runtime.wanoa_base_url:
            raise HTTPException(status_code=400, detail="未配置万傲平台地址")
        self.runtime = runtime
        self.base_url = runtime.wanoa_base_url.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def _access_token(self) -> str | None:
        return self.runtime.wanoa_access_token or self.runtime.wanoa_client_secret

    def _auth_params(self, params: dict[str, Any]) -> dict[str, Any]:
        values = dict(params)
        token = self._access_token()
        if token:
            values["access_token"] = token
        return values

    async def person_list(
        self,
        *,
        name: str | None = None,
        pins: str | None = None,
        dept_codes: str | None = None,
        page_no: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        params = {
            "pageNo": page_no,
            "pageSize": page_size,
        }
        if name:
            params["name"] = name
        if pins:
            params["pins"] = pins
        if dept_codes:
            params["deptCodes"] = dept_codes
        data = await self._request("POST", self.runtime.wanoa_person_list_path, params=params)
        if not is_success_response(data):
            raise HTTPException(status_code=502, detail=f"万傲人员查询失败: {data.get('message') or data}")
        return data

    async def card_list(self, pin: str) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            self.runtime.wanoa_card_list_path,
            params={"pin": pin},
        )
        if not is_success_response(data):
            raise HTTPException(status_code=502, detail=f"万傲饭卡查询失败: {data.get('message') or data}")
        cards = data.get("data") or []
        return cards if isinstance(cards, list) else []

    async def account_info(self, *, pin: str, card_no: str | None = None) -> dict[str, Any]:
        if not self.runtime.wanoa_balance_path:
            raise HTTPException(
                status_code=400,
                detail="万傲离线消费余额接口未配置",
            )
        params = {
            **parse_extra_params(self.runtime.wanoa_balance_extra_params),
            self.runtime.wanoa_balance_pin_param: pin,
        }
        if card_no and self.runtime.wanoa_balance_card_param:
            params[self.runtime.wanoa_balance_card_param] = card_no
        data = await self._request(
            self.runtime.wanoa_balance_method,
            self.runtime.wanoa_balance_path,
            params=params,
        )
        if not is_success_response(data):
            raise HTTPException(status_code=502, detail=f"万傲余额查询失败: {data.get('message') or data}")
        account = normalize_account_payload(data.get("data"))
        value = read_json_path(data, self.runtime.wanoa_balance_json_path)
        return {
            "raw": data,
            "account": account,
            "balance": normalize_money(value, unit=self.runtime.wanoa_balance_amount_unit),
            "money_wallet": normalize_money(
                first_present(account, "posMoneyWallet", "moneyWallet", "balance"),
                unit=self.runtime.wanoa_balance_amount_unit,
            ),
            "allowance_wallet": normalize_money(
                first_present(account, "posAllowanceWallet", "allowanceWallet", "subBalance"),
                unit=self.runtime.wanoa_balance_amount_unit,
            ),
        }

    async def balance(self, *, pin: str, card_no: str | None = None) -> Decimal:
        return (await self.account_info(pin=pin, card_no=card_no))["balance"]

    async def _request(self, method: str, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        request_params = self._auth_params(params)
        async with httpx.AsyncClient(timeout=15, follow_redirects=False, headers=self._headers()) as client:
            if method.upper() == "POST":
                response = await client.post(self._url(path), params=request_params)
            else:
                response = await client.get(self._url(path), params=request_params)
        if response.status_code in (301, 302, 303, 307, 308) or "bioLogin" in response.headers.get("location", ""):
            raise HTTPException(status_code=401, detail="万傲接口需要有效 access_token，请在系统设置中配置客户端密钥或 access_token")
        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"万傲接口不存在或当前模块未启用: {path}",
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"万傲接口请求失败: HTTP {response.status_code}",
            ) from exc
        try:
            return response.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="万傲接口未返回 JSON 数据") from exc


def is_success_response(data: dict[str, Any]) -> bool:
    code = data.get("code")
    if code is None:
        return True
    try:
        return int(code) >= 0
    except (TypeError, ValueError):
        return str(code).lower() in {"success", "ok"}


def normalize_money(value: Any, *, unit: str) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise HTTPException(status_code=502, detail=f"万傲金额字段解析失败: {value}") from exc
    if unit in {"yuan", "元", "rmb"}:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return (amount / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_extra_params(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    params: dict[str, str] = {}
    for key, item in parse_qsl(value, keep_blank_values=True):
        if key:
            params[key] = item
    return params


def normalize_account_payload(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    return {}


def first_present(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def read_json_path(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if not part:
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return None
            current = current[index]
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def sanitize_person_payload(item: dict[str, Any]) -> dict[str, Any]:
    blocked_keys = {
        "personPhoto",
        "vislightPhoto",
        "photoBase64",
        "capturePhotoBase64",
    }
    return {key: value for key, value in item.items() if key not in blocked_keys}


def upsert_candidate(
    db: Session,
    *,
    source: str,
    external_id: str,
    name: str,
    department_code: str | None = None,
    department_name: str | None = None,
    employee_no: str | None = None,
    card_no: str | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> ExternalUserCandidate:
    row = db.scalar(
        select(ExternalUserCandidate).where(
            ExternalUserCandidate.source == source,
            ExternalUserCandidate.external_id == external_id,
        )
    )
    if not row:
        row = ExternalUserCandidate(source=source, external_id=external_id, name=name)
        db.add(row)
    row.name = name
    row.department_code = department_code
    row.department_name = department_name
    row.employee_no = employee_no
    row.card_no = card_no
    row.raw_payload = raw_payload or {}
    row.synced_at = datetime.now(timezone.utc)
    return row


async def sync_wanoa_candidates(
    db: Session,
    *,
    name: str | None = None,
    page_size: int | None = None,
) -> int:
    runtime = get_runtime_settings(db)
    client = WanoaClient(runtime)
    size = min(max(page_size or runtime.wanoa_sync_page_size, 1), 200)
    page_no = 1
    total_synced = 0
    while True:
        payload = await client.person_list(name=name, page_no=page_no, page_size=size)
        body = payload.get("data") or {}
        rows = body.get("data") if isinstance(body, dict) else []
        rows = rows if isinstance(rows, list) else []
        for item in rows:
            pin = str(item.get("pin") or "").strip()
            person_name = str(item.get("name") or "").strip()
            if not pin or not person_name:
                continue
            cards = await client.card_list(pin)
            card_no = str((cards[0] if cards else {}).get("cardNo") or item.get("cardNo") or "").strip() or None
            upsert_candidate(
                db,
                source="wanoa",
                external_id=pin,
                name=person_name,
                department_code=str(item.get("deptCode") or "").strip() or None,
                department_name=str(item.get("deptName") or "").strip() or None,
                employee_no=pin,
                card_no=card_no,
                raw_payload={**sanitize_person_payload(item), "cards": cards},
            )
            total_synced += 1
        db.commit()
        total = int(body.get("total") or total_synced) if isinstance(body, dict) else total_synced
        if name or not rows or page_no * size >= total:
            break
        page_no += 1
    return total_synced
