from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import CurrentUser, LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserOut, UserUpdate

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
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        name=payload.name,
        wecom_userid=payload.wecom_userid,
        department=payload.department,
        roles=payload.roles,
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
    if payload.password:
        user.password_hash = hash_password(payload.password)
    if payload.name is not None:
        user.name = payload.name
    if payload.wecom_userid is not None:
        user.wecom_userid = payload.wecom_userid or None
    if payload.department is not None:
        user.department = payload.department or None
    if payload.roles is not None:
        user.roles = payload.roles
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user
