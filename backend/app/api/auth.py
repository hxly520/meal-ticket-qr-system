from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import CurrentUser, LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserOut, UserPasswordReset, UserUpdate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=CurrentUser)
def me(user: User = Depends(get_current_user)) -> CurrentUser:
    return CurrentUser(id=user.id, username=user.username, name=user.name, roles=user.roles or [])


@router.post("/users", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> User:
    ensure_unique_user_fields(db, payload.username, payload.wecom_userid)
    user = User(
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
        wecom_userid=normalize_optional(payload.wecom_userid),
        department=normalize_optional(payload.department),
        roles=normalize_roles(payload.roles),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id.desc())).all())


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("admin")),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="不能停用当前登录账号")
    next_roles = normalize_roles(payload.roles) if payload.roles is not None else user.roles or []
    next_active = payload.is_active if payload.is_active is not None else user.is_active
    ensure_admin_remains(db, user, next_roles, next_active)
    if payload.wecom_userid is not None:
        ensure_unique_user_fields(db, user.username, payload.wecom_userid, user_id=user.id)
    if payload.password:
        user.password_hash = hash_password(payload.password)
    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.wecom_userid is not None:
        user.wecom_userid = normalize_optional(payload.wecom_userid)
    if payload.department is not None:
        user.department = normalize_optional(payload.department)
    if payload.roles is not None:
        user.roles = next_roles
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-password", response_model=UserOut)
def reset_user_password(
    user_id: int,
    payload: UserPasswordReset,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(user)
    return user


def normalize_optional(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def normalize_roles(roles: list[str] | None) -> list[str]:
    allowed = {"admin", "hr", "verifier", "auditor"}
    result = [role for role in dict.fromkeys(roles or []) if role in allowed]
    if not result:
        raise HTTPException(status_code=400, detail="用户至少需要一个角色")
    return result


def ensure_unique_user_fields(
    db: Session,
    username: str,
    wecom_userid: str | None,
    *,
    user_id: int | None = None,
) -> None:
    username_text = username.strip()
    username_user = db.scalar(select(User).where(User.username == username_text))
    if username_user and username_user.id != user_id:
        raise HTTPException(status_code=409, detail="账号已存在")
    wecom_text = normalize_optional(wecom_userid)
    if not wecom_text:
        return
    wecom_user = db.scalar(select(User).where(User.wecom_userid == wecom_text))
    if wecom_user and wecom_user.id != user_id:
        raise HTTPException(status_code=409, detail="企业微信 UserID 已绑定其他账号")


def ensure_admin_remains(
    db: Session,
    target: User,
    next_roles: list[str],
    next_active: bool,
) -> None:
    if next_active and "admin" in next_roles:
        return
    active_admins = db.scalars(
        select(User).where(
            User.is_active.is_(True),
        )
    ).all()
    other_admin_exists = any(
        user.id != target.id and "admin" in (user.roles or []) for user in active_admins
    )
    if not other_admin_exists and "admin" in (target.roles or []):
        raise HTTPException(status_code=400, detail="至少保留一个启用的管理员账号")
