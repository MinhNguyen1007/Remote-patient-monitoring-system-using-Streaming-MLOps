"""Băm mật khẩu (bcrypt) và JWT (PyJWT) — docs/design/02_4 mục 2.4.2."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def create_access_token(user_id: UUID, role: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    minutes = settings.backend_access_token_expire_minutes if expires_minutes is None else expires_minutes
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "role": role, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, settings.backend_secret_key, algorithm=settings.backend_jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Ném jwt.PyJWTError nếu token sai chữ ký, sai định dạng hoặc hết hạn."""
    settings = get_settings()
    return jwt.decode(token, settings.backend_secret_key, algorithms=[settings.backend_jwt_algorithm])
