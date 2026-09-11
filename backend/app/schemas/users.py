from datetime import datetime
from uuid import UUID

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.db.models import RoleEnum
from app.schemas.common import ORMModel

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s.]+$")


def normalize_email(value: str) -> str:
    """Kiểm tra cú pháp local@domain.tld và chuẩn hóa chữ thường.

    Không dùng kiểu email của Pydantic: thư viện email-validator từ chối tên miền dành riêng như `.local`, trong khi
    hệ thống nội bộ bệnh viện và tài khoản demo dùng đúng loại tên miền này.
    """
    value = value.strip().lower()
    if len(value) > 320 or not EMAIL_PATTERN.match(value):
        raise ValueError("email không hợp lệ")
    return value


Email = Annotated[str, AfterValidator(normalize_email)]


class UserOut(ORMModel):
    id: UUID
    full_name: str
    email: str
    role: RoleEnum
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: Email
    password: str = Field(min_length=8, max_length=128)
    role: RoleEnum


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: RoleEnum | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
