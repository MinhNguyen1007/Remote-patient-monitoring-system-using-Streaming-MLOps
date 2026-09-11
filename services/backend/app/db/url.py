"""Chuỗi kết nối PostgreSQL từ biến môi trường (POSTGRES_*), dùng chung cho app và Alembic."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

REPO_ROOT = Path(__file__).resolve().parents[3]


def database_url(driver: str = "postgresql+psycopg2") -> URL:
    """Biến đã đặt trong shell được ưu tiên hơn `.env` (vd chạy trên host: POSTGRES_HOST=localhost)."""
    load_dotenv(REPO_ROOT / ".env", override=False)
    return URL.create(
        driver,
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ["POSTGRES_DB"],
    )
