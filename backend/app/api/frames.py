from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas import FrameSnapshot
from app.services.frame_service import create_frame_snapshot
from app.state import WORKSPACE_DIR, app_state

router = APIRouter()

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"}
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/sessions/{session_id}/frames/upload", response_model=FrameSnapshot)
async def upload_frame(session_id: str, file: UploadFile = File(...)) -> FrameSnapshot:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")

    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="仅支持上传图片文件（JPEG/PNG/WebP/GIF/BMP）")

    contents = await file.read()
    if len(contents) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件大小超过 10MB 限制")

    upload_dir = WORKSPACE_DIR / "uploads" / "frames" / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 使用安全文件名，忽略原始文件名
    suffix = ".jpg"
    if file.content_type == "image/png":
        suffix = ".png"
    elif file.content_type == "image/webp":
        suffix = ".webp"

    image_path = upload_dir / f"{app_state.new_id('frame')}{suffix}"
    image_path.write_bytes(contents)
    image_url = f"/uploads/frames/{session_id}/{image_path.name}"

    return await create_frame_snapshot(session_id, image_path, image_url)


@router.get("/sessions/{session_id}/frames", response_model=list[FrameSnapshot])
async def list_frames(session_id: str) -> list[FrameSnapshot]:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return app_state.frames.get(session_id, [])
