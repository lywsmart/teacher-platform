import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .config import get_settings
from .database import get_db


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
TEMPORARY_PASSWORD = "888888"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, rounds, salt, digest = encoded.split("$", 3)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(rounds))
        return hmac.compare_digest(actual, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


def create_token(user_id: int, password_hash: str, password_change_required: bool = False) -> str:
    settings = get_settings()
    expiry = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    revision = hashlib.sha256(password_hash.encode()).hexdigest()
    return jwt.encode({"sub": str(user_id), "exp": expiry, "revision": revision,
                       "password_change_required": password_change_required},
                      settings.secret_key, algorithm="HS256")


def authenticated_session(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from app.models import User
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except Exception as exc:
        raise HTTPException(401, "登录状态已失效") from exc
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "用户不存在或已停用")
    revision = hashlib.sha256(user.password_hash.encode()).hexdigest()
    if not hmac.compare_digest(str(payload.get("revision", "")), revision):
        raise HTTPException(401, "请重新登录")
    return user, bool(payload.get("password_change_required"))


def current_user(session=Depends(authenticated_session)):
    user, password_change_required = session
    if password_change_required:
        raise HTTPException(403, "请先修改临时密码")
    return user
