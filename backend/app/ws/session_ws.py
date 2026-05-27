from fastapi import APIRouter, Query, WebSocket

from app.auth_utils import decode_access_token
from app.ws.manager import manager

router = APIRouter()


@router.websocket("/ws/sessions/{session_id}")
async def session_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(None),
) -> None:
    if not token:
        await websocket.close(code=1008, reason="缺少认证信息")
        return
    try:
        decode_access_token(token)
    except Exception:
        await websocket.close(code=1008, reason="认证无效")
        return

    await manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        manager.disconnect(session_id, websocket)
