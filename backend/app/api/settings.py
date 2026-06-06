from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.schemas.settings import SettingItem, SettingsUpdate
from app.services.system_settings import get_runtime_settings, list_settings, update_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/public-brand")
def get_public_brand(db: Session = Depends(get_db)) -> dict[str, str]:
    runtime = get_runtime_settings(db)
    return {
        "company_name": runtime.ticket_company_name,
        "footer_text": runtime.ticket_footer_text,
    }


@router.get("", response_model=list[SettingItem])
def get_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> list[SystemSetting]:
    return list_settings(db)


@router.put("", response_model=list[SettingItem])
def save_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> list[SystemSetting]:
    return update_settings(db, payload.values)
