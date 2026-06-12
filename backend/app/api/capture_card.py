from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app.services import capture_card_service, capture_resource_service
from app.state import app_state

router = APIRouter()


class CaptureCardPreviewRequest(BaseModel):
    device_id: str = ""
    video_index: int | None = Field(default=None, ge=0, le=16)
    width: int = Field(default=1280, ge=160, le=3840)
    height: int = Field(default=720, ge=120, le=2160)
    fps: int = Field(default=30, ge=1, le=60)


@router.get("/capture-card/devices")
async def list_capture_card_devices() -> dict:
    return await capture_card_service.enumerate_devices()


@router.post("/sessions/{session_id}/capture-card/start")
async def start_capture_card_preview(session_id: str, payload: CaptureCardPreviewRequest) -> dict:
    _ensure_session(session_id)
    try:
        result = await capture_card_service.start_preview(
            session_id,
            device_id=payload.device_id,
            video_index=payload.video_index,
            width=payload.width,
            height=payload.height,
            fps=payload.fps,
        )
        await capture_resource_service.broadcast_status(session_id)
        return result
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/capture-card/stop")
async def stop_capture_card_preview(session_id: str) -> dict:
    _ensure_session(session_id)
    result = await capture_card_service.stop_preview(session_id)
    await capture_resource_service.broadcast_status(session_id)
    return result


@router.get("/sessions/{session_id}/capture-card/status")
async def capture_card_preview_status(session_id: str) -> dict:
    _ensure_session(session_id)
    return capture_card_service.status(session_id)


@router.get("/sessions/{session_id}/capture-card/snapshot")
async def capture_card_snapshot(session_id: str) -> Response:
    _ensure_session(session_id)
    try:
        frame = await capture_card_service.snapshot(session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(content=frame, media_type="image/jpeg")


@router.get("/sessions/{session_id}/capture-card/stream")
async def capture_card_stream(session_id: str) -> StreamingResponse:
    _ensure_session(session_id)
    if not capture_card_service.status(session_id).get("running"):
        raise HTTPException(status_code=409, detail="采集卡预览未启动")
    stream = capture_card_service.mjpeg_stream(session_id)
    return StreamingResponse(
        stream,
        media_type=f"multipart/x-mixed-replace; boundary={capture_card_service.MJPEG_BOUNDARY}",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


def _ensure_session(session_id: str) -> None:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
