from pathlib import Path
from datetime import datetime, timezone

from app.schemas import FrameSnapshot
from app.services.product_recognition_service import (
    apply_recognition,
    extract_color_from_image,
    match_products_by_image,
)
from app.repositories import save_frame_snapshot, trim_frame_snapshots
from app.state import app_state
from app.ws.manager import manager


def analyze_image_basic(image_path: Path) -> dict[str, float | str]:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {
            "detected_scene": "OpenCV 未安装",
            "sharpness_score": None,
            "brightness_score": None,
            "change_score": None,
        }

    image = cv2.imread(str(image_path))
    if image is None:
        return {
            "detected_scene": "图片读取失败",
            "sharpness_score": None,
            "brightness_score": None,
            "change_score": None,
        }

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))

    scene = "清晰商品画面" if sharpness > 80 else "画面可能偏糊"
    if brightness < 60:
        scene = "画面偏暗"
    elif brightness > 210:
        scene = "画面偏亮"

    return {
        "detected_scene": scene,
        "sharpness_score": round(sharpness, 2),
        "brightness_score": round(brightness, 2),
        "change_score": None,
    }


async def create_frame_snapshot(session_id: str, image_path: Path, image_url: str) -> FrameSnapshot:
    analysis = analyze_image_basic(image_path)

    image_scores = match_products_by_image(image_path)
    detected_color = extract_color_from_image(image_path)
    recognized, confidence, source = await apply_recognition(
        session_id, image_scores=image_scores, detected_color=detected_color
    )

    now = datetime.now(timezone.utc)
    snapshot = FrameSnapshot(
        id=app_state.new_id("snap"),
        session_id=session_id,
        timestamp=now,
        image_path=image_url,
        summary=f"OpenCV 基础检测：{analysis.get('detected_scene')}",
        detected_scene=str(analysis.get("detected_scene")),
        sharpness_score=analysis.get("sharpness_score"),
        brightness_score=analysis.get("brightness_score"),
        change_score=analysis.get("change_score"),
        recognized_product_id=recognized.id if recognized else None,
        recognized_product_name=recognized.name if recognized else "",
        recognition_confidence=round(confidence, 3) if recognized else None,
        recognition_source=source,
        created_at=now,
    )
    _MAX_FRAMES_PER_SESSION = 30
    frames = app_state.frames.setdefault(session_id, [])
    frames.insert(0, snapshot)
    del frames[_MAX_FRAMES_PER_SESSION:]
    save_frame_snapshot(snapshot)
    trim_frame_snapshots(session_id, keep=_MAX_FRAMES_PER_SESSION)
    await manager.broadcast(session_id, "frame_snapshot", snapshot.model_dump(mode="json"))
    return snapshot
