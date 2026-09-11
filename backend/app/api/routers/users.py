"""UC03 Quản lý tài khoản người dùng — chỉ Admin. Không xóa cứng: khóa tài khoản bằng `is_active` để giữ lịch sử."""

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.security import hash_password
from app.db.models import PatientAssignment, RoleEnum, User
from app.db.session import get_db
from app.schemas.users import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


def get_user_or_404(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy người dùng")
    return user


@router.get("", response_model=list[UserOut])
def list_users(role: RoleEnum | None = None, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    query = select(User).order_by(User.role, User.full_name)
    if role is not None:
        query = query.where(User.role == role)
    return db.scalars(query).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> User:
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email đã được sử dụng")
    user = User(id=uuid.uuid4(), full_name=body.full_name, email=email,
                password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.commit()
    return user


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> User:
    return get_user_or_404(db, user_id)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: UUID, body: UserUpdate, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)) -> User:
    user = get_user_or_404(db, user_id)
    if user.id == admin.id and (body.is_active is False or (body.role is not None and body.role != RoleEnum.ADMIN)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Không thể tự khóa hoặc tự bỏ quyền Admin của chính mình")
    if body.role is not None and body.role == RoleEnum.ADMIN and user.role != RoleEnum.ADMIN:
        # Admin không được phân công bệnh nhân: đổi sang Admin thì gỡ phân công hiện có
        for assignment in db.scalars(select(PatientAssignment).where(PatientAssignment.user_id == user.id)):
            db.delete(assignment)
    for field in ("full_name", "role", "is_active"):
        value = getattr(body, field)
        if value is not None:
            setattr(user, field, value)
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    db.commit()
    return user
