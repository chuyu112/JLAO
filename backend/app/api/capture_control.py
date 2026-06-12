from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import capture_resource_service
from app.state import app_state

router = APIRouter()


class FrontendResourceUpdate(BaseModel):
    running: bool = True
    last_error: str = ""
    metadata: dict = Field(default_factory=dict)


@router.get("/sessions/{session_id}/capture/status")
async def get_capture_status(session_id: str) -> dict:
    _ensure_session(session_id)
    return capture_resource_service.aggregate_status(session_id)


@router.post("/sessions/{session_id}/capture/browser-video")
async def update_browser_video_status(session_id: str, payload: FrontendResourceUpdate) -> dict:
    _ensure_session(session_id)
    try:
        capture_resource_service.mark_browser_video(
            session_id,
            payload.running,
            last_error=payload.last_error,
            metadata=payload.metadata,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await capture_resource_service.broadcast_status(session_id)
    return capture_resource_service.aggregate_status(session_id)


@router.post("/sessions/{session_id}/capture/ocr")
async def update_ocr_capture_status(session_id: str, payload: FrontendResourceUpdate) -> dict:
    _ensure_session(session_id)
    try:
        capture_resource_service.mark_ocr_capture(
            session_id,
            payload.running,
            last_error=payload.last_error,
            metadata=payload.metadata,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await capture_resource_service.broadcast_status(session_id)
    return capture_resource_service.aggregate_status(session_id)


@router.post("/sessions/{session_id}/capture/reset/soft")
async def soft_reset_capture(session_id: str) -> dict:
    _ensure_session(session_id)
    return await capture_resource_service.soft_reset(session_id)


@router.post("/sessions/{session_id}/capture/reset/hard")
async def hard_reset_capture(session_id: str) -> dict:
    _ensure_session(session_id)
    return await capture_resource_service.hard_reset(session_id)


def _ensure_session(session_id: str) -> None:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
