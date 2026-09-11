"""Seed tài khoản.

- Khi backend khởi động: nếu chưa có Admin nào thì tạo Admin từ ADMIN_EMAIL / ADMIN_PASSWORD (.env).
- `python -m app.seed --demo` (từ services/backend): tạo 2 bác sĩ + 1 điều dưỡng mẫu và phân công bệnh nhân đang có
  (bác sĩ 1 phụ trách nửa đầu, bác sĩ 2 nửa sau, điều dưỡng phụ trách tất cả) để minh họa phạm vi xem theo phân công.
  Cần có bệnh nhân trong DB (chạy stream consumer + producer trước).
"""

import argparse
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.models import Patient, PatientAssignment, RoleEnum, User

log = logging.getLogger(__name__)

DEMO_USERS = (
    ("bs.an@rpm.local", "BS. Nguyễn Văn An", RoleEnum.DOCTOR),
    ("bs.binh@rpm.local", "BS. Trần Thị Bình", RoleEnum.DOCTOR),
    ("dd.cuong@rpm.local", "ĐD. Lê Văn Cường", RoleEnum.NURSE),
)


def ensure_admin(db: Session, settings: Settings) -> User | None:
    """Tạo Admin đầu tiên nếu hệ thống chưa có Admin; trả về user vừa tạo hoặc None."""
    if db.scalar(select(User.id).where(User.role == RoleEnum.ADMIN).limit(1)) is not None:
        return None
    admin = User(
        id=uuid.uuid4(),
        full_name=settings.admin_full_name,
        email=settings.admin_email.lower(),
        password_hash=hash_password(settings.admin_password),
        role=RoleEnum.ADMIN,
    )
    db.add(admin)
    db.commit()
    log.info("đã tạo Admin đầu tiên: %s", admin.email)
    return admin


def seed_demo(db: Session, password: str) -> dict:
    admin = db.scalar(select(User).where(User.role == RoleEnum.ADMIN).limit(1))
    users = []
    for email, name, role in DEMO_USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(id=uuid.uuid4(), full_name=name, email=email, password_hash=hash_password(password), role=role)
            db.add(user)
        users.append(user)
    db.flush()

    patients = db.scalars(select(Patient).order_by(Patient.mimic_subject_id)).all()
    half = (len(patients) + 1) // 2
    plan = [(users[0], patients[:half]), (users[1], patients[half:]), (users[2], patients)]
    created = 0
    for user, group in plan:
        for patient in group:
            exists = db.scalar(
                select(PatientAssignment.id).where(
                    PatientAssignment.patient_id == patient.id, PatientAssignment.user_id == user.id
                )
            )
            if exists is None:
                db.add(PatientAssignment(id=uuid.uuid4(), patient_id=patient.id, user_id=user.id,
                                         assigned_by=admin.id if admin else None))
                created += 1
    db.commit()
    return {"users": [u.email for u in users], "patients": len(patients), "new_assignments": created}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo", action="store_true", help="tạo bác sĩ/điều dưỡng mẫu và phân công bệnh nhân")
    parser.add_argument("--password", default="demo12345", help="mật khẩu cho tài khoản mẫu")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        ensure_admin(db, get_settings())
        if args.demo:
            print(seed_demo(db, args.password))


if __name__ == "__main__":
    main()
