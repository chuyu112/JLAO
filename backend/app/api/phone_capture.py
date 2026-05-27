from fastapi import APIRouter, HTTPException

from app.schemas import PhoneCaptureStartRequest
from app.services import phone_capture_service
from app.state import app_state

router = APIRouter()


@router.post("/sessions/{session_id}/phone-capture/start")
async def start_phone_capture(session_id: str, payload: PhoneCaptureStartRequest) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    try:
        return await phone_capture_service.start_capture(
            session_id=session_id,
            serial=payload.serial,
            interval_seconds=payload.interval_seconds,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="启动手机截屏失败，请检查设备连接")


@router.post("/sessions/{session_id}/phone-capture/stop")
async def stop_phone_capture(session_id: str) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return await phone_capture_service.stop_capture(session_id)


@router.get("/sessions/{session_id}/phone-capture/status")
async def get_phone_capture_status(session_id: str) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return phone_capture_service.status(session_id)


@router.post("/sessions/{session_id}/phone-capture/once")
async def capture_phone_once(session_id: str, payload: PhoneCaptureStartRequest) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    try:
        return await phone_capture_service.capture_once(session_id=session_id, serial=payload.serial)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="手机截屏失败，请检查设备连接")
