"""Schema ban đầu theo docs/design/02_7_erd.md, gồm hypertable TimescaleDB cho vital_records và predictions.

Revision ID: 0001
Revises: 
Create Date: 2026-09-11 11:38:56.555173
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('model_versions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('model_name', sa.String(length=64), nullable=False),
    sa.Column('mlflow_version', sa.String(length=16), nullable=False),
    sa.Column('mlflow_run_id', sa.String(length=64), nullable=False),
    sa.Column('gate_status', sa.Enum('PROMOTED', 'REJECTED', name='gate_status', native_enum=False, create_constraint=True, length=16), nullable=False),
    sa.Column('is_champion', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('trigger', sa.Enum('INITIAL', 'DRIFT', 'MANUAL', name='model_trigger', native_enum=False, create_constraint=True, length=16), nullable=False),
    sa.Column('drift_report_id', sa.UUID(), nullable=True),
    sa.Column('dag_run_id', sa.String(length=250), nullable=True),
    sa.Column('metrics', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('trained_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('model_name', 'mlflow_version', name='uq_model_versions_name_version')
    )
    op.create_table('patients',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('display_name', sa.String(length=100), nullable=False),
    sa.Column('gender', sa.String(length=1), nullable=True),
    sa.Column('age', sa.Integer(), nullable=True),
    sa.Column('mimic_subject_id', sa.Integer(), nullable=False),
    sa.Column('mimic_icustay_id', sa.Integer(), nullable=False),
    sa.Column('admitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('mimic_icustay_id'),
    sa.UniqueConstraint('mimic_subject_id')
    )
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.Enum('ADMIN', 'DOCTOR', 'NURSE', name='user_role', native_enum=False, create_constraint=True, length=16), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('alert_settings',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('risk_critical_threshold', sa.Float(), nullable=True),
    sa.Column('anomaly_threshold', sa.Float(), nullable=False),
    sa.Column('cooldown_hours', sa.Integer(), nullable=False),
    sa.Column('updated_by', sa.UUID(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('alerts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('patient_id', sa.UUID(), nullable=False),
    sa.Column('prediction_id', sa.UUID(), nullable=False),
    sa.Column('prediction_recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('alert_type', sa.Enum('RISK', 'ANOMALY', name='alert_type', native_enum=False, create_constraint=True, length=16), nullable=False),
    sa.Column('status', sa.Enum('OPEN', 'ACKNOWLEDGED', 'RESOLVED', name='alert_status', native_enum=False, create_constraint=True, length=16), server_default='OPEN', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('acknowledged_by', sa.UUID(), nullable=True),
    sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolved_by', sa.UUID(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolution_note', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['acknowledged_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alerts_patient_type_status', 'alerts', ['patient_id', 'alert_type', 'status'], unique=False)
    op.create_table('drift_reports',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('run_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('window_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('window_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('n_records', sa.Integer(), nullable=False),
    sa.Column('reference_model_version_id', sa.UUID(), nullable=True),
    sa.Column('max_psi', sa.Float(), nullable=True),
    sa.Column('feature_stats', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('drift_detected', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('triggered_retrain', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('dag_run_id', sa.String(length=250), nullable=True),
    sa.ForeignKeyConstraint(['reference_model_version_id'], ['model_versions.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('patient_assignments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('patient_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('assigned_by', sa.UUID(), nullable=True),
    sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('patient_id', 'user_id', name='uq_patient_assignments_patient_user')
    )
    op.create_table('predictions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('patient_id', sa.UUID(), nullable=False),
    sa.Column('predicted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('news2_score', sa.Integer(), nullable=True),
    sa.Column('risk_level', sa.Enum('NORMAL', 'WARNING', 'CRITICAL', name='risk_level', native_enum=False, create_constraint=True, length=16), nullable=False),
    sa.Column('risk_score', sa.Float(), nullable=False),
    sa.Column('anomaly_score', sa.Float(), nullable=True),
    sa.Column('is_anomaly', sa.Boolean(), nullable=True),
    sa.Column('risk_model_version_id', sa.UUID(), nullable=False),
    sa.Column('anomaly_model_version_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['anomaly_model_version_id'], ['model_versions.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['risk_model_version_id'], ['model_versions.id'], ),
    sa.PrimaryKeyConstraint('id', 'recorded_at')
    )
    op.create_index('ix_predictions_patient_recorded', 'predictions', ['patient_id', 'recorded_at'], unique=False)
    # Khóa ngoại vòng model_versions ↔ drift_reports: tạo sau khi cả hai bảng đã có
    op.create_foreign_key(
        'fk_model_versions_drift_report', 'model_versions', 'drift_reports', ['drift_report_id'], ['id'], ondelete='SET NULL'
    )
    op.create_table('vital_records',
    sa.Column('patient_id', sa.UUID(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('hour_index', sa.Integer(), nullable=False),
    sa.Column('heart_rate', sa.Float(), nullable=True),
    sa.Column('spo2', sa.Float(), nullable=True),
    sa.Column('respiratory_rate', sa.Float(), nullable=True),
    sa.Column('systolic_bp', sa.Float(), nullable=True),
    sa.Column('diastolic_bp', sa.Float(), nullable=True),
    sa.Column('temperature', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('patient_id', 'recorded_at')
    )
    op.create_table('notification_logs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('alert_id', sa.UUID(), nullable=False),
    sa.Column('recipient_user_id', sa.UUID(), nullable=False),
    sa.Column('channel', sa.String(length=16), server_default='EMAIL', nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    # Hypertable phân vùng theo recorded_at (khóa chính đã chứa cột phân vùng)
    op.execute("SELECT create_hypertable('vital_records', by_range('recorded_at', INTERVAL '1 day'))")
    op.execute("SELECT create_hypertable('predictions', by_range('recorded_at', INTERVAL '1 day'))")


def downgrade() -> None:
    op.drop_constraint('fk_model_versions_drift_report', 'model_versions', type_='foreignkey')
    op.drop_table('notification_logs')
    op.drop_table('vital_records')
    op.drop_index('ix_predictions_patient_recorded', table_name='predictions')
    op.drop_table('predictions')
    op.drop_table('patient_assignments')
    op.drop_table('drift_reports')
    op.drop_index('ix_alerts_patient_type_status', table_name='alerts')
    op.drop_table('alerts')
    op.drop_table('alert_settings')
    op.drop_table('users')
    op.drop_table('patients')
    op.drop_table('model_versions')
