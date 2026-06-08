import asyncio
import io
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from app.repositories import save_live_session
from app.services.live_comment_service import _recognize_all_with_windows, _unique_clean_lines
from app.services.live_room_profile_service import live_room_catalog
from app.state import app_state
from app.ws.manager import manager


_ROOM_NAME_OCR_INTERVAL_SECONDS = 3.0
_session_last_room_ocr_at: dict[str, float] = {}

_NOISE_EXACT = {
    "LIVE",
    "live",
    "直播",
    "直播中",
    "视频号",
    "关注",
    "已关注",
    "更多",
    "搜索",
    "推荐",
}
_NOISE_CONTAINS = (
    "在线",
    "人看过",
    "观看",
    "热度",
    "点赞",
    "说点什么",
    "分享",
    "购物车",
    "礼物墙",
    "5G",
    "4G",
    "WiFi",
    "wifi",
    "信号",
    "电池",
    "时间",
    ":",
    "电池",
)


async def update_live_room_name_from_frame(session_id: str, image_path: Path) -> str:
    """更新直播间名称 - 从截图 OCR 自动识别"""
    session = app_state.sessions.get(session_id)
    if not session:
        return ""

    detected = await detect_live_room_name_from_frame(image_path)
    if not detected:
        return session.live_room_name

    if session.live_room_name == detected:
        return detected

    updated = session.model_copy(update={"live_room_name": detected, "updated_at": datetime.now(timezone.utc)})
    app_state.sessions[session_id] = updated
    save_live_session(updated)
    await manager.broadcast(session_id, "session_status", updated.model_dump(mode="json"))
    return detected


async def detect_live_room_name_from_frame(image_path: Path) -> str:
    variants = await asyncio.to_thread(_read_live_room_name_region_variants, image_path)
    if not variants:
        return ""

    lines, ok = await _recognize_all_with_windows(variants)
    if not ok:
        return ""
    return extract_live_room_name(_unique_clean_lines(lines))


def extract_live_room_name(lines: Iterable[str]) -> str:
    known_names, canonical_by_label = live_room_catalog()
    for line in lines:
        candidate = _clean_room_name_line(line)
        # 优先匹配已知直播间名
        for known_name in known_names:
            if known_name in candidate:
                return canonical_by_label.get(known_name, known_name)
        # 如果包含"浅玩翡翠"，直接返回固定名称
        if "浅玩翡翠" in candidate:
            return "浅玩翡翠-2号店"
        if _is_valid_room_name(candidate):
            return candidate
    return ""


def cleanup_session_room_name_cache(session_id: str) -> None:
    _session_last_room_ocr_at.pop(session_id, None)


def _should_detect_room_name(session_id: str) -> bool:
    return time.monotonic() - _session_last_room_ocr_at.get(session_id, 0) >= _ROOM_NAME_OCR_INTERVAL_SECONDS


def _read_live_room_name_region_variants(image_path: Path) -> list[bytes]:
    try:
        from PIL import Image, ImageEnhance, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is required to crop live room name region") from exc

    with Image.open(image_path) as image:
        image = image.convert("RGB")
        width, height = image.size
        configs = [
            (0, 0, int(width * 0.72), int(height * 0.18)),
            (0, int(height * 0.02), int(width * 0.78), int(height * 0.14)),
            (0, int(height * 0.04), int(width * 0.66), int(height * 0.20)),
        ]
        variants: list[bytes] = []
        for box in configs:
            crop = image.crop(box)
            crop = ImageOps.autocontrast(crop)
            crop = ImageEnhance.Sharpness(crop).enhance(1.4)
            crop = ImageEnhance.Contrast(crop).enhance(1.2)
            if crop.width < 700:
                crop = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            crop.save(output, format="JPEG", quality=92, optimize=True)
            variants.append(output.getvalue())
        return variants


def _clean_room_name_line(value: str) -> str:
    cleaned = value.replace("\u3000", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^(?:直播间|直播中|LIVE)\s*[:：-]?\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s*(?:的直播间|直播间)$", "", cleaned).strip()
    return cleaned.strip("·|,，。:：[]【】()（）")


def _is_valid_room_name(value: str) -> bool:
    if not value or value in _NOISE_EXACT:
        return False
    if len(value) < 2 or len(value) > 32:
        return False
    if any(marker in value for marker in _NOISE_CONTAINS):
        return False
    if re.fullmatch(r"[\d.,万wW+\-\s]+", value):
        return False
    if not re.search(r"[A-Za-z\u4e00-\u9fff]", value):
        return False
    if re.search(r"[?？!！]", value):
        return False
    return True
