"""UC01 Đăng nhập. UC02 Đăng xuất là phía client (xóa token) vì JWT không lưu trạng thái ở server."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.db.models import User
from app.db.session import get_db
from app.schemas.users import LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # Cùng một thông báo cho sai email, sai mật khẩu và tài khoản bị khóa (không lộ tài khoản nào tồn tại)
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email hoặc mật khẩu không đúng")
    minutes = get_settings().backend_access_token_expire_minutes
    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value, minutes),
        expires_in=minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
