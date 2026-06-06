from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ExternalUserCandidateOut(BaseModel):
    id: int
    source: str
    external_id: str
    name: str
    department_code: str | None
    department_name: str | None
    employee_no: str | None
    card_no: str | None
    synced_at: datetime

    model_config = {"from_attributes": True}


class CandidatePage(BaseModel):
    items: list[ExternalUserCandidateOut]
    total: int
    page: int
    page_size: int


class SyncResult(BaseModel):
    source: str
    total: int
    message: str


class CardUserBindingCreate(BaseModel):
    wecom_userid: str
    wanoa_pin: str


class CardUserBindingUpdate(BaseModel):
    wecom_userid: str | None = None
    wanoa_pin: str | None = None
    status: str | None = None


class CardUserBindingOut(BaseModel):
    id: int
    wecom_userid: str
    wanoa_pin: str
    wecom_name: str | None
    wanoa_name: str | None
    wecom_department: str | None
    wanoa_department: str | None
    wanoa_card_no: str | None
    status: str
    last_balance: Decimal | None
    balance_status: str | None
    balance_message: str | None
    last_balance_at: datetime | None

    model_config = {"from_attributes": True}


class BindingPage(BaseModel):
    items: list[CardUserBindingOut]
    total: int
    page: int
    page_size: int


class WecomUserBindingOut(BaseModel):
    wecom_userid: str
    wecom_name: str
    wecom_department: str | None = None
    wanoa_pin: str | None = None
    wanoa_name: str | None = None
    wanoa_department: str | None = None
    wanoa_card_no: str | None = None
    binding_status: str | None = None
    last_balance: Decimal | None = None
    last_balance_at: datetime | None = None
    low_balance_pushed_at: datetime | None = None


class WecomUserBindingPage(BaseModel):
    items: list[WecomUserBindingOut]
    total: int
    page: int
    page_size: int


class BalanceLookup(BaseModel):
    name: str | None = None
    wecom_userid: str | None = None
    wanoa_pin: str | None = None


class BalanceResult(BaseModel):
    status: str
    message: str
    name: str | None = None
    department: str | None = None
    wecom_userid: str | None = None
    wanoa_pin: str | None = None
    card_no: str | None = None
    account_no: str | None = None
    balance: Decimal | None = None
    money_wallet: Decimal | None = None
    allowance_wallet: Decimal | None = None
    available: bool | None = None
    account_kind_name: str | None = None
    balance_at: datetime | None = None


class PublicCardBalanceResult(BaseModel):
    status: str
    message: str
    wecom_userid: str | None = None
    wecom_name: str | None = None
    wecom_department: str | None = None
    wanoa_pin: str | None = None
    wanoa_name: str | None = None
    wanoa_department: str | None = None
    wanoa_card_no: str | None = None
    balance: Decimal | None = None
    balance_status: str | None = None
    balance_message: str | None = None
    last_balance_at: datetime | None = None
    refreshed_at: datetime | None = None


class LowBalanceAlertPreviewItem(BaseModel):
    wecom_userid: str
    name: str | None = None
    department: str | None = None
    card_no: str | None = None
    balance: Decimal
    threshold: Decimal
    last_balance_at: datetime | None = None
    last_pushed_at: datetime | None = None
    next_push_at: datetime | None = None
    schedule_frequency: str
    schedule_time: str
    schedule_weekday: int
    weekend_enabled: bool
    due: bool
    title: str
    content: str


class LowBalanceAlertPreview(BaseModel):
    enabled: bool
    threshold: Decimal
    interval_minutes: int
    frequency: str
    weekday: int
    push_time: str
    weekend_enabled: bool
    total: int
    due_total: int
    items: list[LowBalanceAlertPreviewItem]
