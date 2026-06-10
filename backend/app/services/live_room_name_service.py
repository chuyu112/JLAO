import asyncio
import io
import re
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

from app.repositories import save_live_session
from app.services.live_comment_service import _recognize_all_comment_variants, _unique_clean_lines
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
    "看过",
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
    "：",
    "电池",
)

_ROOM_NAME_OCR_REPLACEMENTS = (
    ("翡翠手虱", "翡翠手镯"),
    ("翡翠手躅", "翡翠手镯"),
    ("手虱", "手镯"),
    ("手躅", "手镯"),
)
_ROOM_NAME_KEYWORDS = ("翡翠", "珠宝", "玉", "手镯", "寄售", "回流", "定制", "闲置", "珠宝")
_ROOM_NAME_BAD_OCR_CHARS = set("虱躅")


async def update_live_room_name_from_frame(session_id: str, image_path: Path) -> str:
    """更新直播间名称 - 从截图 OCR 自动识别"""
    session = app_state.sessions.get(session_id)
    if not session:
        return ""
    if not _should_detect_room_name(session_id):
        return session.live_room_name
    _session_last_room_ocr_at[session_id] = time.monotonic()

    detected = await detect_live_room_name_from_frame(image_path)
    if not detected:
        return session.live_room_name

    if session.live_room_name == detected:
        return detected

    if not _should_replace_room_name(session.live_room_name, detected):
        return session.live_room_name

    updated = session.model_copy(update={"live_room_name": detected, "updated_at": datetime.now(timezone.utc)})
    app_state.sessions[session_id] = updated
    save_live_session(updated)
    await manager.broadcast(session_id, "session_status", updated.model_dump(mode="json"))
    return detected


async def detect_live_room_name_from_frame(image_path: Path) -> str:
    variants = await asyncio.to_thread(_read_live_room_name_region_variants, image_path)
    if not variants:
        return ""

    lines = await _recognize_all_comment_variants(variants)
    if not lines:
        return ""
    return extract_live_room_name(_unique_clean_lines(lines))


def extract_live_room_name(lines: Iterable[str]) -> str:
    known_names, canonical_by_label = live_room_catalog()
    candidates: list[str] = []
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
            candidates.append(candidate)
    if not candidates:
        return ""
    return max(candidates, key=_room_name_score)


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
            (int(width * 0.08), int(height * 0.055), int(width * 0.62), int(height * 0.115)),
            (int(width * 0.05), int(height * 0.045), int(width * 0.68), int(height * 0.13)),
            (0, 0, int(width * 0.72), int(height * 0.16)),
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
    for source, replacement in _ROOM_NAME_OCR_REPLACEMENTS:
        cleaned = cleaned.replace(source, replacement)
    cleaned = re.sub(r"[.。·…]{2,}$", "", cleaned).strip()
    return cleaned.strip("·|,，。:：;；[]【】()（）-—_ ")


def _is_valid_room_name(value: str) -> bool:
    if not value or value in _NOISE_EXACT:
        return False
    if len(value) < 2 or len(value) > 32:
        return False
    if any(marker in value for marker in _NOISE_CONTAINS):
        return False
    if _looks_like_status_time(value):
        return False
    if value.startswith("+") or "关氵" in value:
        return False
    if re.fullmatch(r"[\d.,万wW+\-\s]+", value):
        return False
    if not re.search(r"[A-Za-z\u4e00-\u9fff]", value):
        return False
    if re.search(r"[?？!！]", value):
        return False
    return True


def _looks_like_status_time(value: str) -> bool:
    compact = re.sub(r"\s+", "", value)
    if re.fullmatch(r"\d{1,2}[:：]\d{2}", compact):
        return True
    if re.fullmatch(r"\d{1,2}[:：]\d{2}[\d.%％°·`'\"|/\\\\-]*", compact):
        return True
    if re.fullmatch(r"[\d:：.%％°·`'\"|/\\\\+\-\s]+", value):
        return True
    return False


def _room_name_score(value: str) -> tuple[int, int, int]:
    keyword_score = sum(1 for keyword in _ROOM_NAME_KEYWORDS if keyword in value)
    clean_score = -sum(1 for char in value if char in _ROOM_NAME_BAD_OCR_CHARS)
    return keyword_score, clean_score, len(value)


def _should_replace_room_name(current: str, detected: str) -> bool:
    current = _clean_room_name_line(current)
    detected = _clean_room_name_line(detected)
    if not current:
        return True

    known_names, canonical_by_label = live_room_catalog()
    current_known = current in canonical_by_label or current in known_names
    detected_known = detected in canonical_by_label or detected in known_names
    if detected_known and not current_known:
        return True
    if current_known and not detected_known:
        return False

    similarity = SequenceMatcher(None, current, detected).ratio()
    if similarity >= 0.72:
        return _room_name_score(detected) >= _room_name_score(current)

    return False
