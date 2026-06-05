import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.system_setting import SystemSetting


SETTING_DEFINITIONS: dict[str, str] = {
    "app_base_url": "系统公网访问地址，用于生成员工饭票链接",
    "app_timezone": "饭票过期计算时区",
    "ticket_company_name": "饭票二维码图片顶部公司名称",
    "ticket_footer_text": "饭票二维码图片底部版权声明",
    "meal_window_breakfast": "早餐允许核销时间段，格式 HH:MM-HH:MM",
    "meal_window_lunch": "午餐允许核销时间段，格式 HH:MM-HH:MM",
    "meal_window_dinner": "晚餐允许核销时间段，格式 HH:MM-HH:MM",
    "wecom_corp_id": "企业微信 CorpID",
    "wecom_agent_id": "企业微信自建应用 AgentID",
    "wecom_secret": "企业微信自建应用 Secret",
    "wecom_approval_token": "审批回调 Token",
    "wecom_approval_aes_key": "审批回调 EncodingAESKey",
    "wecom_approval_template_id": "饭票审批模板 ID",
    "wecom_field_meal_date": "审批模板里的用餐日期字段名",
    "wecom_field_meal_type": "审批模板里的餐别字段名",
    "wecom_field_diner_count": "审批模板里的用餐人数字段名",
    "wecom_field_department": "审批模板里的部门字段名",
    "wecom_field_reason": "审批模板里的申请原因字段名",
    "wecom_department_mapping": "企业微信部门ID到中文名称映射，每行一个，如：28=IT部",
}


DEFAULT_VALUES: dict[str, str | None] = {
    "app_base_url": settings.app_base_url,
    "app_timezone": settings.app_timezone,
    "ticket_company_name": settings.ticket_company_name,
    "ticket_footer_text": settings.ticket_footer_text,
    "meal_window_breakfast": "06:00-09:00",
    "meal_window_lunch": "11:00-13:30",
    "meal_window_dinner": "17:00-19:30",
    "wecom_corp_id": settings.wecom_corp_id,
    "wecom_agent_id": settings.wecom_agent_id,
    "wecom_secret": settings.wecom_secret,
    "wecom_approval_token": settings.wecom_approval_token,
    "wecom_approval_aes_key": settings.wecom_approval_aes_key,
    "wecom_approval_template_id": settings.wecom_approval_template_id,
    "wecom_field_meal_date": settings.wecom_field_meal_date,
    "wecom_field_meal_type": settings.wecom_field_meal_type,
    "wecom_field_diner_count": settings.wecom_field_diner_count,
    "wecom_field_department": settings.wecom_field_department,
    "wecom_field_reason": settings.wecom_field_reason,
    "wecom_department_mapping": "",
}


@dataclass(frozen=True)
class RuntimeSettings:
    app_base_url: str
    app_timezone: str
    ticket_company_name: str
    ticket_footer_text: str
    meal_window_breakfast: str | None
    meal_window_lunch: str | None
    meal_window_dinner: str | None
    wecom_corp_id: str | None
    wecom_agent_id: str | None
    wecom_secret: str | None
    wecom_approval_token: str | None
    wecom_approval_aes_key: str | None
    wecom_approval_template_id: str | None
    wecom_field_meal_date: str
    wecom_field_meal_type: str
    wecom_field_diner_count: str
    wecom_field_department: str
    wecom_field_reason: str
    wecom_department_mapping: str | None


def seed_default_settings(db: Session) -> None:
    existing = set(db.scalars(select(SystemSetting.key)).all())
    for key, description in SETTING_DEFINITIONS.items():
        if key not in existing:
            db.add(SystemSetting(key=key, value=DEFAULT_VALUES.get(key), description=description))
    db.commit()


def list_settings(db: Session) -> list[SystemSetting]:
    seed_default_settings(db)
    return list(db.scalars(select(SystemSetting).order_by(SystemSetting.id.asc())).all())


def update_settings(db: Session, values: dict[str, str | None]) -> list[SystemSetting]:
    seed_default_settings(db)
    rows = {row.key: row for row in db.scalars(select(SystemSetting)).all()}
    for key, value in values.items():
        if key not in SETTING_DEFINITIONS:
            continue
        row = rows.get(key)
        if row:
            row.value = value
        else:
            db.add(
                SystemSetting(
                    key=key,
                    value=value,
                    description=SETTING_DEFINITIONS.get(key),
                )
            )
    db.commit()
    return list_settings(db)


def get_runtime_settings(db: Session) -> RuntimeSettings:
    rows = {row.key: row.value for row in list_settings(db)}

    def value(key: str) -> str | None:
        item = rows.get(key)
        if item == "":
            return None
        return item if item is not None else DEFAULT_VALUES.get(key)

    return RuntimeSettings(
        app_base_url=value("app_base_url") or settings.app_base_url,
        app_timezone=value("app_timezone") or settings.app_timezone,
        ticket_company_name=value("ticket_company_name") or settings.ticket_company_name,
        ticket_footer_text=value("ticket_footer_text") or settings.ticket_footer_text,
        meal_window_breakfast=value("meal_window_breakfast"),
        meal_window_lunch=value("meal_window_lunch"),
        meal_window_dinner=value("meal_window_dinner"),
        wecom_corp_id=value("wecom_corp_id"),
        wecom_agent_id=value("wecom_agent_id"),
        wecom_secret=value("wecom_secret"),
        wecom_approval_token=value("wecom_approval_token"),
        wecom_approval_aes_key=value("wecom_approval_aes_key"),
        wecom_approval_template_id=value("wecom_approval_template_id"),
        wecom_field_meal_date=value("wecom_field_meal_date") or settings.wecom_field_meal_date,
        wecom_field_meal_type=value("wecom_field_meal_type") or settings.wecom_field_meal_type,
        wecom_field_diner_count=(
            value("wecom_field_diner_count") or settings.wecom_field_diner_count
        ),
        wecom_field_department=value("wecom_field_department") or settings.wecom_field_department,
        wecom_field_reason=value("wecom_field_reason") or settings.wecom_field_reason,
        wecom_department_mapping=value("wecom_department_mapping"),
    )


def parse_wecom_department_mapping(value: str | None) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for line in (value or "").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        parts = re.split(r"\s*[=:：]\s*|\s+", text, maxsplit=1)
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].strip():
            continue
        mapping[int(parts[0])] = parts[1].strip()
    return mapping


def department_names_from_mapping(
    department_ids: list[int],
    mapping_text: str | None,
) -> list[str]:
    mapping = parse_wecom_department_mapping(mapping_text)
    return [mapping[item] for item in department_ids if item in mapping]


def normalize_department_display(
    department: str | None,
    mapping_text: str | None,
) -> str | None:
    if not department:
        return department
    mapping = parse_wecom_department_mapping(mapping_text)
    if not mapping:
        return department

    def replace_match(match: re.Match[str]) -> str:
        department_id = int(match.group(1))
        return mapping.get(department_id, match.group(0))

    text = re.sub(r"部门ID\s*(\d+)", replace_match, department)
    tokens = re.split(r"([,/，、|;；\s]+)", text)
    changed = False
    for index, token in enumerate(tokens):
        if token.isdigit() and int(token) in mapping:
            tokens[index] = mapping[int(token)]
            changed = True
    return "".join(tokens) if changed else text
