from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from app.services.live_comment_service import _recognize_all_comment_variants, sanitize_ocr_error


JADE_OCR_INTERVAL_SECONDS = float(os.getenv("JLAO_JADE_OCR_INTERVAL_SECONDS", "1.2"))
MAX_JADE_OCR_LINES = 24

_last_ocr_at: dict[str, float] = {}
_last_ocr_result: dict[str, dict[str, Any]] = {}

_JADE_TEXT_HINTS = (
    "翡翠",
    "冰种",
    "高冰",
    "玻璃种",
    "糯冰",
    "冰糯",
    "细糯",
    "豆种",
    "阳绿",
    "蓝水",
    "晴水",
    "白冰",
    "飘花",
    "紫罗兰",
    "手镯",
    "珠串",
    "蛋面",
    "戒面",
    "吊坠",
    "挂件",
    "平安扣",
    "观音",
    "佛公",
    "如意",
    "叶子",
    "山水",
    "貔貅",
    "葫芦",
    "尺寸",
    "内径",
    "直径",
    "厚",
    "mm",
    "MM",
    "¥",
    "￥",
    "w",
    "W",
)


def get_jade_ocr_runtime_status() -> dict[str, Any]:
    tesseract_path = shutil.which("tesseract") or ""
    if not tesseract_path:
        return {
            "source": "frame-ocr",
            "enabled": False,
            "reason": "tesseract-not-installed",
            "engine": "",
            "languages": [],
            "interval_seconds": JADE_OCR_INTERVAL_SECONDS,
        }

    languages: list[str] = []
    language_error = ""
    try:
        completed = subprocess.run(
            [tesseract_path, "--list-langs"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=8,
            check=False,
        )
        if completed.returncode == 0:
            languages = [
                line.strip()
                for line in completed.stdout.splitlines()
                if line.strip() and not line.lower().startswith("list of")
            ]
        else:
            language_error = (completed.stderr or completed.stdout or "").strip()[:200]
    except Exception as exc:
        language_error = str(exc)[:200]

    has_chinese = "chi_sim" in languages
    has_english = "eng" in languages
    enabled = has_chinese and has_english
    if enabled:
        reason = "ready"
    elif not has_chinese:
        reason = "chi-sim-language-not-installed"
    else:
        reason = "eng-language-not-installed"
    return {
        "source": "frame-ocr",
        "enabled": enabled,
        "reason": reason,
        "engine": tesseract_path,
        "languages": languages,
        "language_error": language_error,
        "interval_seconds": JADE_OCR_INTERVAL_SECONDS,
    }


async def recognize_jade_frame_ocr_text(session_id: str, image_path: Path) -> dict[str, Any]:
    now = time.monotonic()
    cached = _last_ocr_result.get(session_id)
    if cached and now - _last_ocr_at.get(session_id, 0) < JADE_OCR_INTERVAL_SECONDS:
        return {**cached, "cached": True}

    try:
        image_bytes = image_path.read_bytes()
        raw_lines = await _recognize_all_comment_variants([image_bytes])
        lines = filter_jade_ocr_lines(raw_lines)
        result = {
            "source": "frame-ocr",
            "ok": bool(raw_lines),
            "cached": False,
            "line_count": len(lines),
            "lines": lines,
            "text": "\n".join(lines),
        }
    except Exception as exc:
        result = {
            "source": "frame-ocr",
            "ok": False,
            "cached": False,
            "line_count": 0,
            "lines": [],
            "text": "",
            "error": sanitize_ocr_error(str(exc)),
        }

    _last_ocr_at[session_id] = now
    _last_ocr_result[session_id] = result
    return result


def filter_jade_ocr_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw_line in lines:
        line = clean_jade_ocr_line(raw_line)
        if not line or line in seen:
            continue
        if not is_probable_jade_product_line(line):
            continue
        seen.add(line)
        result.append(line)
        if len(result) >= MAX_JADE_OCR_LINES:
            break
    return result


def clean_jade_ocr_line(value: str) -> str:
    line = re.sub(r"\s+", " ", value or "").strip()
    line = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", line)
    return line.strip("·|,，。[]【】()（）")


def is_probable_jade_product_line(line: str) -> bool:
    if len(line) < 2 or len(line) > 120:
        return False
    if any(hint in line for hint in _JADE_TEXT_HINTS):
        return True
    if re.search(r"\d+(?:\.\d+)?\s*(?:mm|MM|毫米)", line):
        return True
    if re.search(r"(?:¥|￥)?\s*\d{3,8}(?:\.\d+)?\s*(?:元|块|w|W)?", line):
        return True
    return False
