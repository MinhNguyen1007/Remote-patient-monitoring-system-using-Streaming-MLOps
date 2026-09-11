"""Quản lý kết nối WebSocket theo user — chỉ đẩy sự kiện tới đúng người được phân công."""

import asyncio
import logging
from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[user_id].add(websocket)

    async def disconnect(self, user_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]

    def connected_users(self) -> set[UUID]:
        return set(self._connections)

    async def send_to_users(self, user_ids, message: dict) -> int:
        """Gửi tới mọi kết nối của các user; kết nối hỏng bị gỡ. Trả về số kết nối đã gửi thành công."""
        async with self._lock:
            targets = [(uid, ws) for uid in user_ids for ws in self._connections.get(uid, ())]
        sent = 0
        for user_id, websocket in targets:
            try:
                await websocket.send_json(message)
                sent += 1
            except Exception:  # client đã đóng kết nối
                log.info("gỡ kết nối WebSocket hỏng của user %s", user_id)
                await self.disconnect(user_id, websocket)
        return sent
