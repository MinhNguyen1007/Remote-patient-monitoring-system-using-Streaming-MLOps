"""WebSocket realtime — docs/design/02_4 mục 2.4.2.

Kết nối `/ws?token=<JWT>`: token sai/hết hạn hoặc tài khoản bị khóa → đóng với mã 1008 (policy violation).
Sau khi kết nối, server chỉ đẩy sự kiện (`prediction`, `alert`, `alert_update`) của bệnh nhân được phân công.
Client có thể gửi "ping" để giữ kết nối; server trả "pong".
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.api.deps import user_from_token
from app.db.session import SessionLocal

router = APIRouter(tags=["realtime"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = ""):
    with SessionLocal() as db:
        user = user_from_token(token, db) if token else None
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    manager = websocket.app.state.ws_manager
    await websocket.accept()
    await manager.connect(user.id, websocket)
    await websocket.send_json({"type": "connected", "data": {"user_id": str(user.id), "role": user.role.value}})
    try:
        while True:
            if await websocket.receive_text() == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(user.id, websocket)
