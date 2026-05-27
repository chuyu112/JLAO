import traceback

from fastapi import APIRouter, HTTPException

from app.schemas import ScrcpyStartRequest
from app.services import scrcpy_service
from app.state import app_state

router = APIRouter()


@router.post("/sessions/{session_id}/scrcpy/start")
async def start_scrcpy(session_id: str, payload: ScrcpyStartRequest) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    try:
        return await scrcpy_service.start_scrcpy(
            session_id=session_id,
            serial=payload.serial,
            max_size=payload.max_size,
            bit_rate=payload.bit_rate,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="启动 scrcpy 失败，请检查设备连接和配置")


@router.post("/sessions/{session_id}/scrcpy/stop")
async def stop_scrcpy(session_id: str) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return await scrcpy_service.stop_scrcpy(session_id)


@router.get("/sessions/{session_id}/scrcpy/status")
async def get_scrcpy_status(session_id: str) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return scrcpy_service.status(session_id)
