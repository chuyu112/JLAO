import traceback

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.auth_utils import decode_access_token
from app.services.local_stt_service import LocalChunkStt, LocalSttNotConfigured
from app.services.transcript_service import append_transcript
from app.state import app_state
from app.ws.manager import manager

router = APIRouter()

STT_PROVIDER = "local"


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
        await manager.broadcast(session_id, "transcript_segment", segment.model_dump(mode="json"))
        await websocket.send_json({"event": "transcript_segment", "data": segment.model_dump(mode="json")})
        await websocket.send_json({"event": "transcript_partial", "data": {"text": ""}})

    async def on_error(message: str) -> None:
        await _send_stt_error(websocket, message)

    stt = _create_stt(on_partial=on_partial, on_final=on_final, on_error=on_error)
    audio_chunks = 0
    audio_bytes = 0
    try:
        await stt.connect()
        print(f"[stt {session_id}] connected provider={STT_PROVIDER}", flush=True)
        await websocket.send_json({"event": "stt_status", "data": {"status": "connected", "provider": STT_PROVIDER}})
        while True:
            message = await websocket.receive()
            audio = message.get("bytes")
            if audio:
                audio_chunks += 1
                audio_bytes += len(audio)
                if audio_chunks == 1 or audio_chunks % 50 == 0:
                    print(f"[stt {session_id}] audio_chunks={audio_chunks} audio_bytes={audio_bytes}", flush=True)
                await stt.send_audio(audio)
    except LocalSttNotConfigured as error:
        await _send_stt_error(websocket, str(error))
    except WebSocketDisconnect:
        pass
    except RuntimeError as error:
        if not _is_expected_disconnect_error(error):
            traceback.print_exc()
            await _send_stt_error(websocket, "实时语音识别异常")
    except Exception:
        traceback.print_exc()
        await _send_stt_error(websocket, "实时语音识别异常")
    finally:
        print(f"[stt {session_id}] closed audio_chunks={audio_chunks} audio_bytes={audio_bytes}", flush=True)
        await stt.close()


def _create_stt(on_partial, on_final, on_error):
    return LocalChunkStt(on_partial=on_partial, on_final=on_final, on_error=on_error)


async def _send_stt_error(websocket: WebSocket, message: str) -> None:
    try:
        await websocket.send_json({"event": "stt_error", "data": {"message": message}})
    except RuntimeError:
        pass


def _is_expected_disconnect_error(error: RuntimeError) -> bool:
    return 'Cannot call "receive" once a disconnect message has been received.' in str(error)
