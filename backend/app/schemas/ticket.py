from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

MEAL_TYPES = {"breakfast", "lunch", "dinner"}


class TicketCreate(BaseModel):
    employee_userid: str | None = None
    employee_name: str
    department: str | None = None
    meal_date: date
    meal_type: str = Field(pattern="^(breakfast|lunch|dinner)$")
    diner_count: int = Field(default=1, ge=1, le=200)
    diner_index: int = Field(default=1, ge=1, le=200)
    expire_at: datetime | None = None


class TicketBatchCreate(BaseModel):
    tickets: list[TicketCreate]


class TicketBatchVoid(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


class TicketBatchVoidResult(BaseModel):
    updated: int
    skipped_used: int
    missing: int


class TicketGenerate(BaseModel):
    employee_userid: str | None = None
    employee_name: str
    department: str | None = None
    meal_date: date
    meal_types: list[str] = Field(min_length=1)
    diner_count: int = Field(default=1, ge=1, le=200)
    expire_at: datetime | None = None

    @field_validator("meal_types")
    @classmethod
    def validate_meal_types(cls, value: list[str]) -> list[str]:
        unique = []
        for item in value:
            if item not in MEAL_TYPES:
                raise ValueError("餐别只能选择 breakfast/lunch/dinner")
            if item not in unique:
                unique.append(item)
        return unique


class TicketOut(BaseModel):
    id: int
    ticket_no: str
    employee_userid: str | None
    employee_name: str
    department: str | None
    meal_date: date
    meal_type: str
    diner_count: int
    diner_index: int
    source: str
    status: str
    expire_at: datetime
    used_at: datetime | None
    approval_sp_no: str | None
    created_at: datetime
    qr_url: str | None = None

    model_config = {"from_attributes": True}


class TicketPage(BaseModel):
    items: list[TicketOut]
    total: int
    page: int
    page_size: int


class VerifyPreview(BaseModel):
    ticket_no: str
    employee_name: str
    department: str | None
    meal_date: date
    meal_type: str
    diner_count: int
    diner_index: int
    status: str
    expire_at: datetime

    model_config = {"from_attributes": True}


class VerifyConsume(BaseModel):
    token: str
