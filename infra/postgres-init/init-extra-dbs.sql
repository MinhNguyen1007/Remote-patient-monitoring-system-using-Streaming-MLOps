-- Chạy tự động khi container Postgres khởi tạo lần đầu (mounted vào /docker-entrypoint-initdb.d).
-- Tạo thêm database riêng cho MLflow và Airflow, tách khỏi rpm_db (dữ liệu nghiệp vụ chính).
CREATE DATABASE mlflow_db;
CREATE DATABASE airflow_db;

-- Bật extension TimescaleDB cho database nghiệp vụ chính (vital_records, predictions dùng hypertable).
\connect rpm_db
CREATE EXTENSION IF NOT EXISTS timescaledb;
