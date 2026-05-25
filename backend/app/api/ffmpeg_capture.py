from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import ffmpeg_capture_service
from app.state import app_state

router = APIRouter()


class FfmpegCaptureRequest(BaseModel):
    source_url: str | None = None
    interval_seconds: float = Field(default=3, ge=1, le=30)


def resolve_source_url(session_id: str, source_url: str | None) -> str:
    session = app_state.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    source = (source_url or session.live_url or "").strip()
    if not source:
        raise HTTPException(status_code=400, detail="请先填写 m3u8/mp4/rtmp/flv 等直连视频流地址")
    return source


@router.post("/sessions/{session_id}/ffmpeg-capture/once")
async def capture_once(session_id: str, payload: FfmpegCaptureRequest) -> dict:
    source = resolve_source_url(session_id, payload.source_url)
    try:
        return await ffmpeg_capture_service.capture_once(session_id, source)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/ffmpeg-capture/start")
async def start_capture(session_id: str, payload: FfmpegCaptureRequest) -> dict:
    source = resolve_source_url(session_id, payload.source_url)
    try:
        return await ffmpeg_capture_service.start_capture(session_id, source, payload.interval_seconds)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/ffmpeg-capture/stop")
async def stop_capture(session_id: str) -> dict:
    return await ffmpeg_capture_service.stop_capture(session_id)


@router.get("/sessions/{session_id}/ffmpeg-capture/status")
async def capture_status(session_id: str) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return ffmpeg_capture_service.status(session_id)
