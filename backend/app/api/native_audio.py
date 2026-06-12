from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import native_audio_service
from app.state import app_state

router = APIRouter()


class NativeAudioStartRequest(BaseModel):
    serial: str = ""
    source: str = ""
    device_id: str = ""
    device_name: str = ""


@router.post("/sessions/{session_id}/native-audio/start")
async def start_native_audio(session_id: str, payload: NativeAudioStartRequest) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    try:
        return await native_audio_service.start_native_audio(
            session_id=session_id,
            serial=payload.serial,
            source=payload.source,
            device_id=payload.device_id,
            device_name=payload.device_name,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"启动手机音频接入失败：{exc}") from exc


@router.post("/sessions/{session_id}/native-audio/stop")
async def stop_native_audio(session_id: str) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    try:
        return await native_audio_service.stop_native_audio(session_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/native-audio/status")
async def get_native_audio_status(session_id: str) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return native_audio_service.status(session_id)
