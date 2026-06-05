from pydantic import BaseModel


class SettingItem(BaseModel):
    key: str
    value: str | None = None
    description: str | None = None

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    values: dict[str, str | None]
