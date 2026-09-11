"""Giai đoạn G: email thông báo drift cho Admin được ghi notification_logs; lý do quality gate của từng version.

- notification_logs: mỗi dòng gắn với đúng 1 đối tượng — cảnh báo (alert_id) hoặc báo cáo drift (drift_report_id).
- model_versions.gate_reasons: lý do bị quality gate từ chối (trống khi đạt).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-11 20:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('model_versions', sa.Column('gate_reasons', sa.Text(), nullable=True))
    op.alter_column('notification_logs', 'alert_id', existing_type=sa.UUID(), nullable=True)
    op.add_column('notification_logs', sa.Column('drift_report_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_notification_logs_drift_report', 'notification_logs', 'drift_reports',
        ['drift_report_id'], ['id'], ondelete='CASCADE',
    )
    op.create_check_constraint(
        'ck_notification_logs_one_subject', 'notification_logs', '(alert_id IS NULL) <> (drift_report_id IS NULL)'
    )


def downgrade() -> None:
    op.execute('DELETE FROM notification_logs WHERE drift_report_id IS NOT NULL')
    op.drop_constraint('ck_notification_logs_one_subject', 'notification_logs', type_='check')
    op.drop_constraint('fk_notification_logs_drift_report', 'notification_logs', type_='foreignkey')
    op.drop_column('notification_logs', 'drift_report_id')
    op.alter_column('notification_logs', 'alert_id', existing_type=sa.UUID(), nullable=False)
    op.drop_column('model_versions', 'gate_reasons')
