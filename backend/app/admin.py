from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_user, hash_password, verify_password
from app.models import Role, User, UserRole

router = APIRouter(prefix="/api/v1")


def is_admin(user: User, db: Session) -> bool:
    return db.scalar(select(UserRole.id).join(Role, Role.id == UserRole.role_id).where(
        UserRole.user_id == user.id, Role.name == "admin"
    )) is not None


def require_admin(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not is_admin(user, db):
        raise HTTPException(403, "仅系统管理员可以执行此操作")
    return user


class AccountCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=12, max_length=128)
    college: Optional[str] = Field(default=None, max_length=128)


class AccountUpdate(BaseModel):
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=12, max_length=128)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


def account(user: User, admin: bool):
    return {"id": user.id, "username": user.username, "name": user.name,
            "college": user.college, "is_active": user.is_active, "is_admin": admin}


@router.get("/auth/me")
def session_details(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return account(user, is_admin(user, db))


@router.put("/auth/password")
def change_password(payload: PasswordChange, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(400, "当前密码不正确")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"ok": True}


@router.get("/admin/users", dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db), after: int = Query(0, ge=0)):
    admin_ids = select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(Role.name == "admin")
    rows = db.execute(select(User, User.id.in_(admin_ids)).where(User.id > after).order_by(User.id).limit(101)).all()
    return {"items": [account(user, admin) for user, admin in rows[:100]],
            "next": rows[99][0].id if len(rows) > 100 else None}


@router.post("/admin/users", status_code=201, dependencies=[Depends(require_admin)])
def create_user(payload: AccountCreate, db: Session = Depends(get_db)):
    user = User(username=payload.username.lower(), name=payload.name.strip(),
                college=payload.college, password_hash=hash_password(payload.password))
    if not user.name:
        raise HTTPException(422, "请填写教师姓名")
    role = db.scalar(select(Role).where(Role.name == "teacher"))
    try:
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "账号已存在") from exc
    return account(user, False)


@router.patch("/admin/users/{user_id}", dependencies=[Depends(require_admin)])
def update_user(user_id: int, payload: AccountUpdate, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "账号不存在")
    if is_admin(user, db):
        raise HTTPException(403, "管理员账号请通过本人修改密码")
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    db.commit()
    return account(user, False)
