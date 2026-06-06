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
    "wanoa_base_url": "万傲瑞达 V6000/V6600 平台地址，如：https://wanoa.example.com",
    "wanoa_client_id": "万傲 API 授权用户名 ID",
    "wanoa_client_secret": "万傲 API access_token",
    "wanoa_access_token": "万傲 API access_token，如与客户端密钥不同则填写",
    "wanoa_person_list_path": "万傲人员列表接口路径",
    "wanoa_card_list_path": "万傲饭卡列表接口路径",
    "wanoa_balance_path": "万傲离线消费流水接口路径",
    "wanoa_balance_method": "万傲余额查询接口方法，GET 或 POST",
    "wanoa_balance_pin_param": "万傲余额接口人员编号参数名",
    "wanoa_balance_card_param": "万傲余额接口卡号参数名；接口不需要卡号时留空",
    "wanoa_balance_extra_params": "万傲余额接口额外查询参数，如：pageNo=1&pageSize=1",
    "wanoa_balance_json_path": "万傲离线消费余额字段 JSON 路径，默认 data.0.balance",
    "wanoa_balance_amount_unit": "万傲离线消费余额字段金额单位，默认 yuan",
    "wanoa_sync_page_size": "万傲用户同步每页数量",
    "external_user_sync_enabled": "是否启用企业微信与万傲用户定时同步，true/false",
    "external_user_sync_interval_minutes": "企业微信与万傲用户定时同步间隔分钟",
    "external_user_auto_bind_enabled": "是否启用候选用户自动关系绑定，true/false",
    "low_balance_alert_enabled": "是否启用饭卡低余额企业微信提醒，true/false",
    "low_balance_alert_threshold": "低余额提醒判断金额",
    "low_balance_alert_interval_minutes": "同一用户低余额提醒间隔分钟",
    "low_balance_alert_frequency": "低余额提醒推送周期，daily 或 weekly",
    "low_balance_alert_weekday": "低余额提醒每周推送星期，0-6 表示周一到周日",
    "low_balance_alert_time": "低余额提醒推送时间，格式 HH:MM",
    "low_balance_alert_title": "低余额提醒标题模板",
    "low_balance_alert_content": "低余额提醒内容模板",
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
    "wanoa_base_url": "",
    "wanoa_client_id": "",
    "wanoa_client_secret": "",
    "wanoa_access_token": "",
    "wanoa_person_list_path": "/api/v2/person/getPersonList",
    "wanoa_card_list_path": "/api/v2/card/getCards",
    "wanoa_balance_path": "/api/transaction/listPosTransaction",
    "wanoa_balance_method": "GET",
    "wanoa_balance_pin_param": "personPin",
    "wanoa_balance_card_param": "",
    "wanoa_balance_extra_params": "pageNo=1&pageSize=1",
    "wanoa_balance_json_path": "data.0.balance",
    "wanoa_balance_amount_unit": "yuan",
    "wanoa_sync_page_size": "50",
    "external_user_sync_enabled": "true",
    "external_user_sync_interval_minutes": "60",
    "external_user_auto_bind_enabled": "true",
    "low_balance_alert_enabled": "false",
    "low_balance_alert_threshold": "20",
    "low_balance_alert_interval_minutes": "1440",
    "low_balance_alert_frequency": "daily",
    "low_balance_alert_weekday": "0",
    "low_balance_alert_time": "11:00",
    "low_balance_alert_title": "饭卡余额提醒",
    "low_balance_alert_content": (
        "{name}，你的饭卡余额为 {balance} 元，低于 {threshold} 元，请及时处理。"
    ),
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
    wanoa_base_url: str | None
    wanoa_client_id: str | None
    wanoa_client_secret: str | None
    wanoa_access_token: str | None
    wanoa_person_list_path: str
    wanoa_card_list_path: str
    wanoa_balance_path: str | None
    wanoa_balance_method: str
    wanoa_balance_pin_param: str
    wanoa_balance_card_param: str | None
    wanoa_balance_extra_params: str | None
    wanoa_balance_json_path: str
    wanoa_balance_amount_unit: str
    wanoa_sync_page_size: int
    external_user_sync_enabled: bool
    external_user_sync_interval_minutes: int
    external_user_auto_bind_enabled: bool
    low_balance_alert_enabled: bool
    low_balance_alert_threshold: str
    low_balance_alert_interval_minutes: int
    low_balance_alert_frequency: str
    low_balance_alert_weekday: int
    low_balance_alert_time: str
    low_balance_alert_title: str
    low_balance_alert_content: str


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
        wanoa_base_url=value("wanoa_base_url"),
        wanoa_client_id=value("wanoa_client_id"),
        wanoa_client_secret=value("wanoa_client_secret"),
        wanoa_access_token=value("wanoa_access_token"),
        wanoa_person_list_path=value("wanoa_person_list_path") or "/api/v2/person/getPersonList",
        wanoa_card_list_path=value("wanoa_card_list_path") or "/api/v2/card/getCards",
        wanoa_balance_path=value("wanoa_balance_path") or "/api/transaction/listPosTransaction",
        wanoa_balance_method=(value("wanoa_balance_method") or "GET").upper(),
        wanoa_balance_pin_param=value("wanoa_balance_pin_param") or "personPin",
        wanoa_balance_card_param=value("wanoa_balance_card_param"),
        wanoa_balance_extra_params=value("wanoa_balance_extra_params"),
        wanoa_balance_json_path=value("wanoa_balance_json_path") or "data.balance",
        wanoa_balance_amount_unit=(value("wanoa_balance_amount_unit") or "cent").lower(),
        wanoa_sync_page_size=parse_int(value("wanoa_sync_page_size"), default=50),
        external_user_sync_enabled=parse_bool(
            value("external_user_sync_enabled"),
            default=True,
        ),
        external_user_sync_interval_minutes=max(
            parse_int(value("external_user_sync_interval_minutes"), default=60),
            5,
        ),
        external_user_auto_bind_enabled=parse_bool(
            value("external_user_auto_bind_enabled"),
            default=True,
        ),
        low_balance_alert_enabled=parse_bool(
            value("low_balance_alert_enabled"),
            default=False,
        ),
        low_balance_alert_threshold=value("low_balance_alert_threshold") or "20",
        low_balance_alert_interval_minutes=max(
            parse_int(value("low_balance_alert_interval_minutes"), default=1440),
            5,
        ),
        low_balance_alert_frequency=normalize_frequency(value("low_balance_alert_frequency")),
        low_balance_alert_weekday=min(
            max(parse_int(value("low_balance_alert_weekday"), default=0), 0),
            6,
        ),
        low_balance_alert_time=normalize_time(value("low_balance_alert_time")),
        low_balance_alert_title=value("low_balance_alert_title") or "饭卡余额提醒",
        low_balance_alert_content=(
            value("low_balance_alert_content")
            or "{name}，你的饭卡余额为 {balance} 元，低于 {threshold} 元，请及时处理。"
        ),
    )


def parse_int(value: str | None, *, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on", "启用", "是"}:
        return True
    if text in {"0", "false", "no", "n", "off", "停用", "否"}:
        return False
    return default


def normalize_frequency(value: str | None) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"daily", "weekly"} else "daily"


def normalize_time(value: str | None) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", text):
        return text
    return "11:00"


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
