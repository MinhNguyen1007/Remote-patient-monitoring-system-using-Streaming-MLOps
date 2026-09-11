"""FastAPI backend — REST + WebSocket + JWT. Chạy (từ services/backend): uvicorn app.main:app --reload --port 8000"""

import asyncio
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import admin, alerts, auth, patients, users, ws
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.events.dispatcher import EventDispatcher
from app.events.listener import KafkaEventListener
from app.seed import ensure_admin
from app.services.notification import make_email_sender
from app.services.ws_manager import ConnectionManager

log = logging.getLogger("app")
TOKEN_IN_QUERY = re.compile(r"(token=)[^&\s\"']+")


class RedactTokenFilter(logging.Filter):
    """WebSocket nhận JWT qua query string (`/ws?token=`); che token trước khi uvicorn ghi log truy cập."""

    @staticmethod
    def redact(text: str) -> str:
        return TOKEN_IN_QUERY.sub(lambda match: match.group(1) + "***", text)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(self.redact(a) if isinstance(a, str) else a for a in record.args)
        elif isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        return True


for _name in ("uvicorn.access", "uvicorn.error"):
    logging.getLogger(_name).addFilter(RedactTokenFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    with SessionLocal() as db:
        ensure_admin(db, settings)
    app.state.ws_manager = ConnectionManager()
    app.state.dispatcher = EventDispatcher(
        SessionLocal, app.state.ws_manager, make_email_sender(settings), settings.frontend_base_url
    )
    listener = None
    if settings.kafka_listener_enabled:
        listener = KafkaEventListener(settings, app.state.dispatcher, asyncio.get_running_loop())
        listener.start()
    log.info("backend sẵn sàng (Kafka listener: %s, email: %s)", bool(listener), settings.email_delivery)
    yield
    if listener is not None:
        await asyncio.to_thread(listener.stop)
    app.state.dispatcher.executor.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="RPM — Giám sát bệnh nhân từ xa", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )
    for module in (auth, users, patients, alerts, admin, ws):
        app.include_router(module.router)

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok"}

    try:  # /metrics cho Prometheus (thư viện tùy chọn)
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator().instrument(app).expose(app, include_in_schema=False)
    except ImportError:
        pass
    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
app = create_app()
