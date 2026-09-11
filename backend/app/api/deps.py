"""Dependency xác thực và phân quyền — docs/design/02_2 (phạm vi dữ liệu theo phân công)."""

from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models import Patient, PatientAssignment, RoleEnum, User
from app.db.session import get_db

bearer = HTTPBearer(auto_error=False)
STAFF_ROLES = (RoleEnum.DOCTOR, RoleEnum.NURSE)


def user_from_token(token: str, db: Session) -> User | None:
    """User đang hoạt động ứng với token, hoặc None nếu token sai/hết hạn/tài khoản bị khóa (dùng cả cho WebSocket)."""
    try:
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    user = db.get(User, user_id)
    return user if user is not None and user.is_active else None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    user = user_from_token(credentials.credentials, db) if credentials else None
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token không hợp lệ hoặc đã hết hạn", headers={"WWW-Authenticate": "Bearer"}
        )
    return user


def require_role(*roles: RoleEnum):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Vai trò không có quyền thực hiện thao tác này")
        return user

    return dependency


require_admin = require_role(RoleEnum.ADMIN)
require_staff = require_role(*STAFF_ROLES)
require_doctor = require_role(RoleEnum.DOCTOR)


def assigned_patient_ids(db: Session, user: User) -> list[UUID]:
    return list(db.scalars(select(PatientAssignment.patient_id).where(PatientAssignment.user_id == user.id)))


def get_assigned_patient(patient_id: UUID, user: User = Depends(require_staff), db: Session = Depends(get_db)) -> Patient:
    """Bệnh nhân tồn tại (404) và được phân công cho người đang đăng nhập (403)."""
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy bệnh nhân")
    assigned = db.scalar(
        select(PatientAssignment.id).where(
            PatientAssignment.patient_id == patient_id, PatientAssignment.user_id == user.id
        )
    )
    if assigned is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bệnh nhân không được phân công cho bạn")
    return patient
