from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.auth_utils import decode_access_token
from app.services import scrcpy_service
from app.state import app_state

router = APIRouter()


@router.websocket("/ws/sessions/{session_id}/scrcpy")
async def scrcpy_websocket(
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

    if session_id not in app_state.sessions:
        await websocket.close(code=1008, reason="直播会话不存在")
        return

    await websocket.accept()
    scrcpy_service.add_client(session_id, websocket)

    try:
        while True:
            message = await websocket.receive_text()
            print(f"[scrcpy_ws {session_id}] received: {message}")
    except WebSocketDisconnect:
        pass
    finally:
        scrcpy_service.remove_client(session_id, websocket)
