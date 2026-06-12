import asyncio
from pathlib import Path
from datetime import datetime, timezone

from app.schemas import CaptureArchiveItem, FrameSnapshot
from app.services.jade_multimodal_service import analyze_jade_image, analyze_live_jade_context, upsert_live_jade_product
from app.services.jade_frame_ocr_service import recognize_jade_frame_ocr_text
from app.services.jade_live_sample_service import record_live_jade_weak_sample
from app.services.product_recognition_service import (
    apply_recognition,
    extract_color_from_image,
    match_products_by_image,
)
from app.services.live_comment_service import process_live_comments_from_frame
from app.services.live_room_name_service import update_live_room_name_from_frame
from app.repositories import save_capture_archive, save_frame_snapshot
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
    analysis = await asyncio.to_thread(analyze_image_basic, image_path)
    recent_context_text = "\n".join(segment.text for segment in app_state.transcripts.get(session_id, [])[-5:])
    ocr_signal = await recognize_jade_frame_ocr_text(session_id, image_path)
    ocr_text = str(ocr_signal.get("text") or "")
    image_context_text = recent_context_text
    image_jade_analysis = await asyncio.to_thread(analyze_jade_image, image_path, context_text=image_context_text)
    jade_analysis = await asyncio.to_thread(
        analyze_live_jade_context,
        session_id,
        image_analysis=image_jade_analysis,
        ocr_text=ocr_text,
    )

    image_scores = await asyncio.to_thread(match_products_by_image, image_path)
    detected_color = jade_analysis.color or await asyncio.to_thread(extract_color_from_image, image_path)
    recognized, confidence, source = await apply_recognition(
        session_id,
        image_scores=image_scores,
        detected_color=detected_color,
        detected_extra=jade_analysis.style or jade_analysis.theme,
    )
    await upsert_live_jade_product(session_id, jade_analysis)
    weak_sample = await asyncio.to_thread(record_live_jade_weak_sample, session_id=session_id, image_url=image_url, analysis=jade_analysis)

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
        jade_color=jade_analysis.color,
        jade_water=jade_analysis.water,
        jade_style=jade_analysis.style,
        jade_theme=jade_analysis.theme,
        jade_size=jade_analysis.size,
        jade_price=jade_analysis.price,
        jade_confidence=round(jade_analysis.confidence, 3),
        jade_attribute_sources=(jade_analysis.signals or {}).get("attribute_sources") or {},
        jade_color_analysis=(jade_analysis.signals or {}).get("color_analysis") or {},
        jade_detections=jade_analysis.detections,
        jade_ocr_text=ocr_text,
        jade_ocr_lines=list(ocr_signal.get("lines") or []),
        jade_ocr_error=str(ocr_signal.get("error") or ""),
        created_at=now,
    )
    _MAX_FRAMES_PER_SESSION = 30
    frames = app_state.frames.setdefault(session_id, [])
    frames.insert(0, snapshot)
    del frames[_MAX_FRAMES_PER_SESSION:]
    save_frame_snapshot(snapshot)
    save_capture_archive(
        CaptureArchiveItem(
            id=f"arch-{snapshot.id}",
            session_id=session_id,
            artifact_type="image",
            source="phone-capture",
            path=image_url,
            content="",
            metadata={
                "detected_scene": snapshot.detected_scene,
                "sharpness_score": snapshot.sharpness_score,
                "brightness_score": snapshot.brightness_score,
                "change_score": snapshot.change_score,
                "recognized_product_id": snapshot.recognized_product_id,
                "recognized_product_name": snapshot.recognized_product_name,
                "recognition_confidence": snapshot.recognition_confidence,
                "recognition_source": snapshot.recognition_source,
                "jade_analysis": {
                    "color": jade_analysis.color,
                    "water": jade_analysis.water,
                    "style": jade_analysis.style,
                    "theme": jade_analysis.theme,
                    "size": jade_analysis.size,
                    "price": jade_analysis.price,
                    "confidence": jade_analysis.confidence,
                    "detections": jade_analysis.detections,
                    "signals": jade_analysis.signals,
                    "ocr": ocr_signal,
                    "weak_sample": weak_sample,
                },
            },
            created_at=snapshot.created_at,
        )
    )
    # NOTE: 不再 trim 数据库，确保所有截图的置信度元数据都被持久化
    # trim_frame_snapshots(session_id, keep=_MAX_FRAMES_PER_SESSION)
    await manager.broadcast(session_id, "frame_snapshot", snapshot.model_dump(mode="json"))
    asyncio.create_task(update_live_room_name_from_frame(session_id, image_path))
    asyncio.create_task(process_live_comments_from_frame(session_id, image_path))
    return snapshot
