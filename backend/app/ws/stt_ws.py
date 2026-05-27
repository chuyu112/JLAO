import os

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.auth_utils import decode_access_token
from app.services.local_stt_service import LocalChunkStt, LocalSttNotConfigured
from app.services.stt_service import AliyunRealtimeStt, AliyunSttNotConfigured
from app.services.transcript_service import append_transcript
from app.state import app_state
from app.ws.manager import manager

router = APIRouter()

STT_PROVIDER = os.getenv("STT_PROVIDER", "local").lower()


@router.websocket("/ws/sessions/{session_id}/stt")
async def stt_websocket(
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

    await websocket.accept()
    if session_id not in app_state.sessions:
        await websocket.send_json({"event": "stt_error", "data": {"message": "直播会话不存在"}})
        await websocket.close(code=1008)
        return

    async def on_partial(text: str) -> None:
        await manager.broadcast(session_id, "transcript_partial", {"text": text})
        await websocket.send_json({"event": "transcript_partial", "data": {"text": text}})

    async def on_final(text: str) -> None:
        segment = await append_transcript(session_id, text)
        await websocket.send_json({"event": "transcript_segment", "data": segment.model_dump(mode="json")})
        await websocket.send_json({"event": "transcript_partial", "data": {"text": ""}})

    async def on_error(message: str) -> None:
        await websocket.send_json({"event": "stt_error", "data": {"message": message}})

    stt = _create_stt(on_partial=on_partial, on_final=on_final, on_error=on_error)
    try:
        await stt.connect()
        await websocket.send_json({"event": "stt_status", "data": {"status": "connected", "provider": STT_PROVIDER}})
        while True:
            message = await websocket.receive()
            audio = message.get("bytes")
            if audio:
                await stt.send_audio(audio)
    except (AliyunSttNotConfigured, LocalSttNotConfigured) as error:
        await websocket.send_json({"event": "stt_error", "data": {"message": str(error)}})
    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.send_json({"event": "stt_error", "data": {"message": "实时语音识别异常"}})
    finally:
        await stt.close()


def _create_stt(on_partial, on_final, on_error):
    if STT_PROVIDER == "aliyun":
        return AliyunRealtimeStt(on_partial=on_partial, on_final=on_final, on_error=on_error)
    return LocalChunkStt(on_partial=on_partial, on_final=on_final, on_error=on_error)
