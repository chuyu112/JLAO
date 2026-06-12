from pathlib import Path

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.repositories import save_frame_snapshot
from app.schemas import FrameSnapshot
from app.services import capture_card_service
from app.services.frame_service import create_frame_snapshot
from app.services.jade_live_sample_service import record_frame_jade_correction
from app.state import WORKSPACE_DIR, app_state
from app.ws.manager import manager

router = APIRouter()

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"}
_MAX_FILE_SIZE = 10 * 1024 * 1024


class CaptureCardFrameRequest(BaseModel):
    rotation: int = Field(default=0)
    mirror: bool = False


@router.post("/sessions/{session_id}/frames/upload", response_model=FrameSnapshot)
async def upload_frame(session_id: str, file: UploadFile = File(...)) -> FrameSnapshot:
    _ensure_session(session_id)
    content_type = file.content_type or ""
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="image file required")

    contents = await file.read()
    if len(contents) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="image file too large")

    suffix = ".jpg"
    if content_type == "image/png":
        suffix = ".png"
    elif content_type == "image/webp":
        suffix = ".webp"

    image_path, image_url = _save_frame_contents(session_id, contents, suffix=suffix)
    return await create_frame_snapshot(session_id, image_path, image_url)


@router.post("/sessions/{session_id}/frames/capture-card", response_model=FrameSnapshot)
async def upload_capture_card_frame(session_id: str, payload: CaptureCardFrameRequest) -> FrameSnapshot:
    _ensure_session(session_id)
    try:
        contents = await capture_card_service.transformed_snapshot(
            session_id,
            rotation=payload.rotation,
            mirror=payload.mirror,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if len(contents) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="image file too large")

    image_path, image_url = _save_frame_contents(session_id, contents, suffix=".jpg")
    return await create_frame_snapshot(session_id, image_path, image_url)


@router.get("/sessions/{session_id}/frames", response_model=list[FrameSnapshot])
async def list_frames(session_id: str) -> list[FrameSnapshot]:
    _ensure_session(session_id)
    return app_state.frames.get(session_id, [])


@router.post("/sessions/{session_id}/frames/{frame_id}/jade-feedback", response_model=FrameSnapshot)
async def save_frame_jade_feedback(
    session_id: str,
    frame_id: str,
    payload: dict = Body(...),
) -> FrameSnapshot:
    _ensure_session(session_id)
    frames = app_state.frames.get(session_id, [])
    frame_index = next((index for index, item in enumerate(frames) if item.id == frame_id), -1)
    if frame_index < 0:
        raise HTTPException(status_code=404, detail="frame-not-found")

    frame = frames[frame_index]
    corrected = payload.get("corrected") if isinstance(payload.get("corrected"), dict) else payload
    cleaned = {
        "color": str(corrected.get("color") or "").strip(),
        "water": str(corrected.get("water") or "").strip(),
        "style": str(corrected.get("style") or "").strip(),
        "theme": str(corrected.get("theme") or "").strip(),
    }
    if not any(cleaned.values()):
        raise HTTPException(status_code=400, detail="empty-correction")

    feedback = record_frame_jade_correction(frame=frame, corrected=cleaned)
    if feedback.get("status") != "ok":
        raise HTTPException(status_code=400, detail=str(feedback.get("reason") or "feedback-save-failed"))

    updated_sources = dict(frame.jade_attribute_sources or {})
    updates: dict[str, object] = {}
    for key, value in cleaned.items():
        if not value:
            continue
        frame_field = f"jade_{key}"
        previous = getattr(frame, frame_field)
        updates[frame_field] = value
        updated_sources[key] = {
            "source": "live-frame-correction",
            "method": "manual",
            "value": value,
            "from": previous,
        }
    updates["jade_attribute_sources"] = updated_sources
    updates["jade_confidence"] = max(frame.jade_confidence, 0.92)

    updated_frame = frame.model_copy(update=updates)
    frames[frame_index] = updated_frame
    save_frame_snapshot(updated_frame)
    await manager.broadcast(session_id, "frame_snapshot", updated_frame.model_dump(mode="json"))
    return updated_frame


def _ensure_session(session_id: str) -> None:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="session-not-found")


def _save_frame_contents(session_id: str, contents: bytes, *, suffix: str) -> tuple[Path, str]:
    upload_dir = WORKSPACE_DIR / "uploads" / "frames" / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_suffix = suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"
    image_path = upload_dir / f"{app_state.new_id('frame')}{safe_suffix}"
    image_path.write_bytes(contents)
    image_url = f"/uploads/frames/{session_id}/{image_path.name}"
    return image_path, image_url
