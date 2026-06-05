from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "饭票二维码核销系统"
    app_base_url: str = "http://localhost:8080"
    app_timezone: str = "Asia/Shanghai"
    ticket_company_name: str = "公司名称"
    ticket_footer_text: str = "版权归IT部所有，有问题联系欧阳祖宇"
    database_url: str = "postgresql+psycopg://meal:meal@postgres:5432/meal_ticket"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    wecom_corp_id: str | None = None
    wecom_agent_id: str | None = None
    wecom_secret: str | None = None
    wecom_approval_token: str | None = None
    wecom_approval_aes_key: str | None = None
    wecom_approval_template_id: str | None = None
    wecom_field_meal_date: str = "用餐日期"
    wecom_field_meal_type: str = "餐别"
    wecom_field_diner_count: str = "用餐人数"
    wecom_field_department: str = "部门"
    wecom_field_reason: str = "申请原因"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
