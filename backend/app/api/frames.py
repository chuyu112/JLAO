from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas import FrameSnapshot
from app.services.frame_service import create_frame_snapshot
from app.state import WORKSPACE_DIR, app_state

router = APIRouter()


@router.post("/sessions/{session_id}/frames/upload", response_model=FrameSnapshot)
async def upload_frame(session_id: str, file: UploadFile = File(...)) -> FrameSnapshot:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")

    upload_dir = WORKSPACE_DIR / "uploads" / "frames" / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "frame.jpg").suffix or ".jpg"
    image_path = upload_dir / f"{app_state.new_id('frame')}{suffix}"
    image_path.write_bytes(await file.read())
    image_url = f"/uploads/frames/{session_id}/{image_path.name}"

    return await create_frame_snapshot(session_id, image_path, image_url)


@router.get("/sessions/{session_id}/frames", response_model=list[FrameSnapshot])
async def list_frames(session_id: str) -> list[FrameSnapshot]:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return app_state.frames.get(session_id, [])
