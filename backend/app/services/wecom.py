from io import BytesIO
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import qrcode
from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.meal_ticket import MealTicket
from app.models.wecom_event import WeComApprovalEvent
from app.schemas.ticket import TicketGenerate
from app.services.system_settings import (
    RuntimeSettings,
    department_names_from_mapping,
    get_runtime_settings,
    normalize_department_display,
)
from app.services.tickets import build_verify_url, create_tickets_from_generate
from app.utils.wecom_crypto import decrypt_message, parse_encrypted_xml, verify_signature, xml_to_dict


class WeComClient:
    def __init__(self, runtime: RuntimeSettings) -> None:
        self.base_url = "https://qyapi.weixin.qq.com/cgi-bin"
        self.runtime = runtime

    async def get_access_token(self) -> str:
        if not self.runtime.wecom_corp_id or not self.runtime.wecom_secret:
            raise RuntimeError("企业微信 CorpID 或 Secret 未配置")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/gettoken",
                params={
                    "corpid": self.runtime.wecom_corp_id,
                    "corpsecret": self.runtime.wecom_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"获取企业微信 access_token 失败: {data}")
        return data["access_token"]

    async def get_approval_detail(self, sp_no: str) -> dict[str, Any]:
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.base_url}/oa/getapprovaldetail",
                params={"access_token": token},
                json={"sp_no": sp_no},
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"获取审批详情失败: {data}")
        return data

    async def send_textcard(self, touser: str, title: str, description: str, url: str) -> None:
        if not self.runtime.wecom_agent_id:
            raise RuntimeError("企业微信 AgentID 未配置")
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.base_url}/message/send",
                params={"access_token": token},
                json={
                    "touser": touser,
                    "msgtype": "textcard",
                    "agentid": int(self.runtime.wecom_agent_id),
                    "textcard": {
                        "title": title,
                        "description": description,
                        "url": url,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"发送企业微信消息失败: {data}")

    async def upload_image(self, image_bytes: bytes, filename: str) -> str:
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.base_url}/media/upload",
                params={"access_token": token, "type": "image"},
                files={"media": (filename, image_bytes, "image/png")},
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"上传企业微信图片失败: {data}")
        return data["media_id"]

    async def send_image(self, touser: str, media_id: str) -> None:
        if not self.runtime.wecom_agent_id:
            raise RuntimeError("企业微信 AgentID 未配置")
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.base_url}/message/send",
                params={"access_token": token},
                json={
                    "touser": touser,
                    "msgtype": "image",
                    "agentid": int(self.runtime.wecom_agent_id),
                    "image": {"media_id": media_id},
                },
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"发送企业微信图片失败: {data}")

    async def get_user_profile(self, userid: str) -> dict[str, Any]:
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/user/get",
                params={"access_token": token, "userid": userid},
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"获取企业微信用户信息失败: {data}")
        return data

    async def get_userid_by_oauth_code(self, code: str) -> str:
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/auth/getuserinfo",
                params={"access_token": token, "code": code},
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"企业微信网页授权失败: {data}")
        userid = (
            data.get("UserId")
            or data.get("userid")
            or data.get("user_id")
            or data.get("USERID")
        )
        if not userid:
            raise RuntimeError("企业微信未返回成员 UserID，请确认从企业微信自建应用内打开")
        return str(userid)

    async def get_department_names(self, department_ids: list[int]) -> list[str]:
        if not department_ids:
            return []
        token = await self.get_access_token()
        names: list[str] = []
        async with httpx.AsyncClient(timeout=10) as client:
            for department_id in department_ids:
                resp = await client.get(
                    f"{self.base_url}/department/get",
                    params={"access_token": token, "id": department_id},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("errcode") == 0 and data.get("department", {}).get("name"):
                    names.append(data["department"]["name"])
                    continue
                fallback_name = await self._get_department_name_from_list(client, token, department_id)
                if fallback_name:
                    names.append(fallback_name)
                    continue
                raise RuntimeError(f"获取企业微信部门信息失败: {data}")
        return names

    async def _get_department_name_from_list(
        self,
        client: httpx.AsyncClient,
        token: str,
        department_id: int,
    ) -> str | None:
        resp = await client.get(
            f"{self.base_url}/department/list",
            params={"access_token": token, "id": department_id},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") != 0:
            return None
        for item in data.get("department", []):
            if int(item.get("id", 0)) == department_id:
                return item.get("name")
        return None


def verify_callback_echo(
    runtime: RuntimeSettings,
    msg_signature: str | None,
    timestamp: str | None,
    nonce: str | None,
    echostr: str | None,
) -> str:
    if not echostr:
        return "ok"
    if not all(
        [
            msg_signature,
            timestamp,
            nonce,
            runtime.wecom_approval_token,
            runtime.wecom_approval_aes_key,
            runtime.wecom_corp_id,
        ]
    ):
        return echostr
    verify_signature(runtime.wecom_approval_token, msg_signature, timestamp, nonce, echostr)
    return decrypt_message(runtime.wecom_approval_aes_key, runtime.wecom_corp_id, echostr)


def parse_encrypted_approval_event(
    runtime: RuntimeSettings,
    body: str,
    msg_signature: str | None,
    timestamp: str | None,
    nonce: str | None,
) -> dict[str, Any]:
    if not all(
        [
            msg_signature,
            timestamp,
            nonce,
            runtime.wecom_approval_token,
            runtime.wecom_approval_aes_key,
            runtime.wecom_corp_id,
        ]
    ):
        raise HTTPException(status_code=500, detail="企业微信回调加密参数未配置完整")
    encrypted = parse_encrypted_xml(body)
    verify_signature(
        runtime.wecom_approval_token,
        msg_signature,
        timestamp,
        nonce,
        encrypted.encrypt,
    )
    xml = decrypt_message(runtime.wecom_approval_aes_key, runtime.wecom_corp_id, encrypted.encrypt)
    data = xml_to_dict(xml).get("xml", {})
    approval_info = data.get("ApprovalInfo") or {}
    applyer = approval_info.get("Applyer") or {}
    return {
        "sp_no": approval_info.get("SpNo") or data.get("SpNo"),
        "template_id": approval_info.get("TemplateId") or data.get("TemplateId"),
        "applicant_userid": (
            approval_info.get("ApplyUserId")
            or data.get("ApplyUserId")
            or applyer.get("UserId")
            or applyer.get("userid")
        ),
        "sp_status": _int_or_none(approval_info.get("SpStatus") or data.get("SpStatus")),
        "raw_payload": data,
    }


def parse_plain_approval_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse plain JSON used by integration tests or temporary production dry-runs."""
    return {
        "sp_no": payload.get("sp_no") or payload.get("SpNo"),
        "template_id": payload.get("template_id") or payload.get("TemplateId"),
        "applicant_userid": payload.get("applicant_userid") or payload.get("ApplyUserId"),
        "sp_status": _int_or_none(payload.get("sp_status") or payload.get("SpStatus")),
        "raw_payload": payload,
    }


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


async def record_and_process_approval_event(db: Session, event: dict[str, Any]) -> WeComApprovalEvent:
    sp_no = event.get("sp_no")
    if not sp_no:
        raise ValueError("审批事件缺少 sp_no")

    existing = db.scalar(select(WeComApprovalEvent).where(WeComApprovalEvent.sp_no == sp_no))
    if existing:
        incoming_status = event.get("sp_status")
        status_changed = incoming_status is not None and incoming_status != existing.sp_status
        existing.template_id = event.get("template_id") or existing.template_id
        existing.applicant_userid = event.get("applicant_userid") or existing.applicant_userid
        existing.sp_status = incoming_status if incoming_status is not None else existing.sp_status
        existing.raw_payload = event.get("raw_payload") or event or existing.raw_payload
        if status_changed and incoming_status == 2:
            existing.processed = False
        db.commit()
        db.refresh(existing)
        if not existing.processed:
            await process_approval_event(db, existing)
        return existing

    row = WeComApprovalEvent(
        sp_no=sp_no,
        template_id=event.get("template_id"),
        applicant_userid=event.get("applicant_userid"),
        sp_status=event.get("sp_status"),
        raw_payload=event.get("raw_payload") or event,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(WeComApprovalEvent).where(WeComApprovalEvent.sp_no == sp_no))
        if existing and not existing.processed:
            await process_approval_event(db, existing)
        return existing
    db.refresh(row)

    await process_approval_event(db, row)
    return row


async def process_approval_event(db: Session, event: WeComApprovalEvent) -> None:
    if event.processed:
        return

    if event.sp_status != 2:
        if event.sp_status in (None, 1):
            event.processed = False
            event.process_result = f"等待审批通过，当前状态: {event.sp_status or '未知'}"
        else:
            event.processed = True
            event.process_result = f"审批未通过或已撤销，状态: {event.sp_status}，不生成饭票"
        db.commit()
        return

    payload = event.raw_payload or {}
    detail_fields: dict[str, Any] = {}
    runtime = get_runtime_settings(db)
    client = WeComClient(runtime)
    if runtime.wecom_corp_id and runtime.wecom_secret:
        try:
            detail = await client.get_approval_detail(event.sp_no)
            detail_fields = extract_approval_fields(detail)
            payload = {**payload, **detail_fields, "approval_detail": detail}
            event.raw_payload = payload
        except Exception as exc:  # noqa: BLE001
            event.process_result = f"审批详情获取失败，使用回调字段生成: {exc}"

    applicant = event.applicant_userid or payload.get("employee_userid") or payload.get("userid")
    employee_name = payload.get("employee_name") or payload.get("employeeName")
    raw_department = payload.get("department") or payload.get(runtime.wecom_field_department)
    department = normalize_department_display(raw_department, runtime.wecom_department_mapping)
    field_department_ids = extract_department_ids_from_value(raw_department)
    if field_department_ids and is_unresolved_department_id_text(department, field_department_ids):
        department = None
    applyer_department_ids = extract_applyer_department_ids(payload)
    profile_department_ids: list[int] = []
    if applicant and runtime.wecom_corp_id and runtime.wecom_secret:
        try:
            profile = await client.get_user_profile(applicant)
            employee_name = employee_name or profile.get("name") or applicant
            profile_department_ids = [
                int(item) for item in profile.get("department", []) if str(item).isdigit()
            ]
        except Exception as exc:  # noqa: BLE001
            payload["user_profile_error"] = str(exc)

    for department_ids, error_key in (
        (field_department_ids, "field_department_lookup_error"),
        (profile_department_ids, "profile_department_lookup_error"),
        (applyer_department_ids, "department_lookup_error"),
    ):
        if department or not department_ids:
            continue
        if runtime.wecom_corp_id and runtime.wecom_secret:
            try:
                department_names = await client.get_department_names(department_ids)
                department = " / ".join(department_names) or None
            except Exception as exc:  # noqa: BLE001
                payload[error_key] = str(exc)
        if not department:
            mapping_names = department_names_from_mapping(
                department_ids,
                runtime.wecom_department_mapping,
            )
            department = " / ".join(mapping_names) or None

    if not department and applyer_department_ids:
        department = " / ".join(f"部门ID {item}" for item in applyer_department_ids)
    employee_name = employee_name or applicant or "企业微信员工"
    meal_date_value = (
        payload.get("meal_date")
        or payload.get("mealDate")
        or payload.get(runtime.wecom_field_meal_date)
    )
    meal_date = date.fromisoformat(meal_date_value) if meal_date_value else date.today()
    meal_type_value = (
        payload.get("meal_type")
        or payload.get("mealType")
        or payload.get(runtime.wecom_field_meal_type)
        or "lunch"
    )
    meal_types = normalize_meal_types(meal_type_value)
    diner_count = parse_positive_int(
        payload.get("diner_count")
        or payload.get("dinerCount")
        or payload.get(runtime.wecom_field_diner_count)
        or 1,
        default=1,
    )

    existing_tickets = list(
        db.scalars(select(MealTicket).where(MealTicket.approval_sp_no == event.sp_no)).all()
    )
    if existing_tickets:
        event.processed = True
        event.process_result = f"审批单已生成过 {len(existing_tickets)} 张饭票"
        db.commit()
        return

    ticket_payload = TicketGenerate(
        employee_userid=applicant,
        employee_name=employee_name,
        department=department,
        meal_date=meal_date,
        meal_types=meal_types,
        diner_count=diner_count,
    )
    try:
        rows = create_tickets_from_generate(
            db,
            ticket_payload,
            source="wecom_approval",
            approval_sp_no=event.sp_no,
        )
        if applicant:
            sent_count = 0
            try:
                for ticket, token in rows:
                    image_bytes = build_ticket_card_png_bytes(
                        ticket,
                        build_verify_url(token, runtime.app_base_url),
                        runtime.ticket_company_name,
                        runtime.ticket_footer_text,
                    )
                    media_id = await client.upload_image(
                        image_bytes,
                        f"{ticket.ticket_no}.png",
                    )
                    await client.send_image(applicant, media_id)
                    sent_count += 1
            except Exception as exc:  # noqa: BLE001
                event.process_result = (
                    f"已生成 {len(rows)} 张饭票，已发送 {sent_count} 张，"
                    f"企业微信图片发送失败: {exc}"
                )
            else:
                event.process_result = f"已生成并发送 {len(rows)} 张饭票二维码图片"
        else:
            event.process_result = f"已生成 {len(rows)} 张饭票，未找到企业微信用户"
        event.processed = True
        db.commit()
    except IntegrityError:
        db.rollback()
        event = db.get(WeComApprovalEvent, event.id)
        if event:
            event.processed = True
            event.process_result = "审批单已生成过饭票"
            db.commit()


def normalize_meal_type(value: str) -> str:
    mapping = {
        "早餐": "breakfast",
        "早饭": "breakfast",
        "breakfast": "breakfast",
        "午餐": "lunch",
        "午饭": "lunch",
        "中餐": "lunch",
        "lunch": "lunch",
        "晚餐": "dinner",
        "晚饭": "dinner",
        "dinner": "dinner",
    }
    return mapping.get(value.strip().lower(), mapping.get(value.strip(), "lunch"))


def normalize_meal_types(value: Any) -> list[str]:
    if isinstance(value, list):
        values = value
    else:
        text = str(value)
        for sep in ("，", "、", "/", "|", ";", "；"):
            text = text.replace(sep, ",")
        values = [item.strip() for item in text.split(",") if item.strip()]
    meal_types: list[str] = []
    for item in values:
        normalized = normalize_meal_type(str(item))
        if normalized not in meal_types:
            meal_types.append(normalized)
    return meal_types or ["lunch"]


def parse_positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default
    return max(number, 1)


def extract_applyer_department_ids(payload: dict[str, Any]) -> list[int]:
    values: list[Any] = []
    approval_info = payload.get("ApprovalInfo") or {}
    applyer = approval_info.get("Applyer") or {}
    values.extend([applyer.get("Party"), applyer.get("partyid")])
    detail_applyer = (payload.get("approval_detail") or {}).get("info", {}).get("applyer", {})
    values.extend([detail_applyer.get("partyid"), detail_applyer.get("party")])
    result: list[int] = []
    for value in values:
        if isinstance(value, list):
            candidates = value
        else:
            candidates = str(value or "").replace(";", ",").replace("|", ",").split(",")
        for item in candidates:
            text = str(item).strip()
            if text.isdigit() and int(text) not in result:
                result.append(int(text))
    return result


def extract_department_ids_from_value(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, list):
        candidates = value
    else:
        text = str(value)
        for separator in ("部门ID", "，", "、", "/", "|", ";", "；", "\n", "\t"):
            text = text.replace(separator, ",")
        candidates = text.split(",")
    result: list[int] = []
    for item in candidates:
        text = str(item).strip()
        if text.isdigit() and int(text) not in result:
            result.append(int(text))
    return result


def is_unresolved_department_id_text(value: str | None, department_ids: list[int]) -> bool:
    if not value or not department_ids:
        return False
    text = str(value)
    for separator in ("部门ID", "，", "、", "/", "|", ";", "；", "\n", "\t"):
        text = text.replace(separator, ",")
    ids = [item.strip() for item in text.split(",") if item.strip()]
    return bool(ids) and all(item.isdigit() and int(item) in department_ids for item in ids)


def build_qr_png_bytes(url: str) -> bytes:
    image = qrcode.make(url)
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def build_ticket_card_png_bytes(
    ticket: MealTicket,
    verify_url: str,
    company_name: str = "公司名称",
    footer_text: str = "版权归IT部门所有",
) -> bytes:
    width, height = 720, 1320
    background = Image.new("RGB", (width, height), "#eef5f4")
    draw = ImageDraw.Draw(background)
    font_regular = load_cjk_font(30)
    font_medium = load_cjk_font(34)
    font_title = load_cjk_font(46)
    font_small = load_cjk_font(24)
    font_tiny = load_cjk_font(22)

    card_x, card_y = 36, 34
    card_right, card_bottom = width - 36, height - 34
    draw.rounded_rectangle((card_x, card_y, card_right, card_bottom), radius=28, fill="#ffffff")
    draw.rounded_rectangle((card_x, card_y, card_right, 230), radius=28, fill="#126a6e")
    draw.rectangle((card_x, 132, card_right, 230), fill="#126a6e")
    center_text(draw, truncate_text(company_name, 22), width, 62, font_small, "#ccefee")
    center_text(draw, "饭票核销二维码", width, 100, font_title, "#ffffff")
    center_text(draw, "请在对应餐次向饭堂工作人员出示", width, 166, font_small, "#d8f2ef")

    details = [
        ("用餐时间", ticket.meal_date.isoformat()),
        ("餐别", format_meal_label(ticket.meal_type)),
        ("申请人", ticket.employee_name),
        ("申请部门", ticket.department or "-"),
        ("用餐人", f"第 {ticket.diner_index} 人 / 共 {ticket.diner_count} 人"),
    ]
    info_x, info_y = 72, 264
    info_right = width - 72
    draw.rounded_rectangle((info_x, info_y, info_right, 548), radius=18, fill="#f7fbfb")
    y = info_y + 28
    for label, value in details:
        draw.text((info_x + 28, y + 4), label, fill="#667a83", font=font_tiny)
        draw.text((info_x + 160, y), truncate_text(str(value), 16), fill="#17232e", font=font_medium)
        if y < info_y + 244:
            draw.line((info_x + 24, y + 42, info_right - 24, y + 42), fill="#e3ecee", width=1)
        y += 52

    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="#13272c", back_color="white").convert("RGB")
    qr_image = qr_image.resize((430, 430))
    qr_x = (width - 430) // 2
    qr_y = 660
    center_text(draw, "核销二维码", width, 592, font_medium, "#126a6e")
    draw.rounded_rectangle((qr_x - 24, qr_y - 24, qr_x + 454, qr_y + 454), radius=26, fill="#f7fbfb")
    draw.rounded_rectangle((qr_x - 12, qr_y - 12, qr_x + 442, qr_y + 442), radius=18, outline="#dbe7e8", width=2)
    background.paste(qr_image, (qr_x, qr_y))

    center_text(draw, "扫码后自动进入核销页面", width, 1120, font_regular, "#126a6e")
    center_text(draw, f"饭票编号：{ticket.ticket_no}", width, 1172, font_small, "#637381")
    draw.line((84, 1226, width - 84, 1226), fill="#e1e8eb", width=2)
    center_text(draw, truncate_text(footer_text, 24), width, 1254, font_small, "#637381")

    buf = BytesIO()
    background.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def load_cjk_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def format_meal_label(meal_type: str) -> str:
    return {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐"}.get(meal_type, meal_type)


def truncate_text(value: str, limit: int) -> str:
    return value if len(value) <= limit else f"{value[:limit - 1]}..."


def center_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    width: int,
    y: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    color: str,
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text(((width - (bbox[2] - bbox[0])) / 2, y), text, fill=color, font=font)


def extract_approval_fields(detail: dict[str, Any]) -> dict[str, Any]:
    info = detail.get("info", detail)
    result: dict[str, Any] = {}
    apply_user = info.get("applyer", {}).get("userid") or info.get("applyer_userid")
    if apply_user:
        result["employee_userid"] = apply_user
    contents = (
        info.get("apply_data", {}).get("contents")
        or info.get("apply_data", {}).get("content")
        or []
    )
    for item in contents:
        title = _extract_title(item.get("title"))
        if not title:
            continue
        result[title] = _extract_control_value(item)
    return result


def _extract_title(title: Any) -> str | None:
    if isinstance(title, list):
        for entry in title:
            if isinstance(entry, dict) and entry.get("text"):
                return entry["text"]
    if isinstance(title, dict):
        return title.get("text")
    if isinstance(title, str):
        return title
    return None


def _extract_control_value(item: dict[str, Any]) -> str | None:
    value = item.get("value")
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return None
    date_value = value.get("date")
    if isinstance(date_value, dict):
        timestamp = date_value.get("s_timestamp") or date_value.get("timestamp")
        if timestamp:
            return datetime.fromtimestamp(int(timestamp), ZoneInfo("Asia/Shanghai")).date().isoformat()
    if isinstance(date_value, str):
        return date_value
    for key in ("text", "new_number", "new_money", "tips"):
        if value.get(key):
            return str(value[key])
    selector = value.get("selector")
    if isinstance(selector, dict):
        options = selector.get("options") or []
        if options:
            values = [
                item
                for item in (
                    _extract_title(option.get("value")) or _extract_title(option.get("name"))
                    for option in options
                )
                if item
            ]
            return ",".join(values) if values else None
    members = value.get("members") or []
    if members:
        first_member = members[0]
        return first_member.get("name") or first_member.get("userid")
    departments = value.get("departments") or []
    if departments:
        names = [
            item.get("name") or item.get("openapi_name") or item.get("id")
            for item in departments
            if isinstance(item, dict)
        ]
        return ",".join(str(item) for item in names if item)
    return None
