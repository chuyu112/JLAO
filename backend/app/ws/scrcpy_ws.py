from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services import scrcpy_service
from app.state import app_state

router = APIRouter()


@router.websocket("/ws/sessions/{session_id}/scrcpy")
async def scrcpy_websocket(websocket: WebSocket, session_id: str) -> None:
    if session_id not in app_state.sessions:
        await websocket.close(code=1008, reason="直播会话不存在")
        return

    await websocket.accept()
    scrcpy_service.add_client(session_id, websocket)

    try:
        while True:
            message = await websocket.receive_text()
            # Phase 2: handle control events from frontend
            # For now just ignore or echo back
            print(f"[scrcpy_ws {session_id}] received: {message}")
    except WebSocketDisconnect:
        pass
    finally:
        scrcpy_service.remove_client(session_id, websocket)
