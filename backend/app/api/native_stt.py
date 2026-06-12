from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import native_stt_service
from app.state import app_state

router = APIRouter()


class NativeSttStartRequest(BaseModel):
    serial: str = ""
    chunk_seconds: int = Field(default=0, ge=0, le=8)


@router.post("/sessions/{session_id}/native-stt/start")
async def start_native_stt(session_id: str, payload: NativeSttStartRequest) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    try:
        return await native_stt_service.start_native_stt(
            session_id=session_id,
            serial=payload.serial,
            chunk_seconds=payload.chunk_seconds,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"启动原生手机音频转写失败：{exc}") from exc


@router.post("/sessions/{session_id}/native-stt/stop")
async def stop_native_stt(session_id: str) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return await native_stt_service.stop_native_stt(session_id)


@router.get("/sessions/{session_id}/native-stt/status")
async def get_native_stt_status(session_id: str) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return native_stt_service.status(session_id)
