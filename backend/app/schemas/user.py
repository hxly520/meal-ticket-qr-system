from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    wecom_userid: str | None = None
    department: str | None = None
    roles: list[str] = Field(default_factory=list, min_length=1)


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=128)
    name: str | None = None
    wecom_userid: str | None = None
    department: str | None = None
    roles: list[str] | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class UserPasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    name: str
    wecom_userid: str | None
    department: str | None
    roles: list[str]
    is_active: bool

    model_config = {"from_attributes": True}
