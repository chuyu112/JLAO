from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services import recording_service
from app.state import app_state

router = APIRouter()


@router.post("/sessions/{session_id}/recorder/start")
async def start_recording(session_id: str) -> dict:
    _ensure_session(session_id)
    try:
        return await recording_service.start_recording(session_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"启动录屏失败：{exc}") from exc


@router.post("/sessions/{session_id}/recorder/stop")
async def stop_recording(session_id: str, file: UploadFile = File(...)) -> dict:
    _ensure_session(session_id)
    try:
        content = await file.read()
        return await recording_service.finish_recording(session_id, content, file.filename or "recording.webm")
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"停止录屏失败：{exc}") from exc


@router.post("/sessions/{session_id}/recorder/abort")
async def abort_recording(session_id: str) -> dict:
    _ensure_session(session_id)
    return await recording_service.stop_recording(session_id, abort=True)


@router.get("/sessions/{session_id}/recorder/status")
async def get_recording_status(session_id: str) -> dict:
    _ensure_session(session_id)
    return recording_service.status(session_id)


def _ensure_session(session_id: str) -> None:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")

