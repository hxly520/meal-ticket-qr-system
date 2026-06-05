from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str
    password: str
    name: str
    wecom_userid: str | None = None
    department: str | None = None
    roles: list[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    password: str | None = None
    name: str | None = None
    wecom_userid: str | None = None
    department: str | None = None
    roles: list[str] | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: int
    username: str
    name: str
    wecom_userid: str | None
    department: str | None
    roles: list[str]
    is_active: bool

    model_config = {"from_attributes": True}
