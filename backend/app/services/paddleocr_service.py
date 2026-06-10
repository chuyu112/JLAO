"""PaddleOCR 中文识别服务。

使用 PaddleOCR 实现本地中文截图 OCR 识别。
"""

import io
import logging
import os
import threading
from pathlib import Path
from typing import Any

import numpy as np


logger = logging.getLogger(__name__)

# PaddleOCR 配置
PADDLEOCR_LANG = os.getenv("PADDLEOCR_LANG", "ch")
PADDLEOCR_VERSION = os.getenv("PADDLEOCR_VERSION", "PP-OCRv4")
PADDLEOCR_USE_GPU = os.getenv("PADDLEOCR_USE_GPU", "false").lower() == "true"
WORKSPACE_DIR = Path(__file__).resolve().parents[3]

os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(WORKSPACE_DIR / ".paddlex"))
os.environ.setdefault("PADDLE_PDX_CPU_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

if not os.access(os.path.expanduser("~"), os.W_OK):
    os.environ.setdefault("HOME", str(WORKSPACE_DIR))
    os.environ.setdefault("USERPROFILE", str(WORKSPACE_DIR))

# PaddleOCR 引擎（延迟加载）
_paddleocr_engine = None
_paddleocr_available = False
_paddleocr_lock = threading.RLock()


def _get_paddleocr_engine():
    """获取或初始化 PaddleOCR 引擎。"""
    global _paddleocr_engine, _paddleocr_available

    if _paddleocr_engine is not None:
        return _paddleocr_engine

    try:
        from paddleocr import PaddleOCR

        logger.info("正在初始化 PaddleOCR...")
        try:
            # PaddleOCR 3.x
            _paddleocr_engine = PaddleOCR(
                lang=PADDLEOCR_LANG,
                ocr_version=PADDLEOCR_VERSION,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=True,
            )
        except Exception:
            # PaddleOCR 2.x
            _paddleocr_engine = PaddleOCR(
                use_angle_cls=True,
                lang=PADDLEOCR_LANG,
                use_gpu=PADDLEOCR_USE_GPU,
                show_log=False,
            )
        _paddleocr_available = True
        logger.info("PaddleOCR 初始化完成")
        return _paddleocr_engine
    except ImportError as exc:
        logger.warning("PaddleOCR 未安装：%s", exc)
        raise
    except Exception as exc:
        logger.error("PaddleOCR 初始化失败：%s", exc)
        raise


_get_paddleocr_engine_unlocked = _get_paddleocr_engine


def _get_paddleocr_engine():
    with _paddleocr_lock:
        return _get_paddleocr_engine_unlocked()


def recognize_with_paddleocr(image_bytes: bytes) -> list[str]:
    """使用 PaddleOCR 识别图片中的文字。

    Args:
        image_bytes: 图片字节数据

    Returns:
        识别出的文字行列表
    """
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("Pillow 未安装，无法使用 PaddleOCR")

    engine = _get_paddleocr_engine()

    try:
        # 将 bytes 转为 PIL Image
        image = Image.open(io.BytesIO(image_bytes))
        # 转为 numpy array
        img_array = np.array(image)

        return _extract_ocr_lines(_run_ocr(engine, img_array))
    except Exception as exc:
        raise RuntimeError(f"PaddleOCR 识别失败：{exc}") from exc


def recognize_with_paddleocr_from_path(image_path: Path) -> list[str]:
    """使用 PaddleOCR 从文件路径识别图片中的文字。

    Args:
        image_path: 图片文件路径

    Returns:
        识别出的文字行列表
    """
    engine = _get_paddleocr_engine()

    try:
        return _extract_ocr_lines(_run_ocr(engine, str(image_path)))
    except Exception as exc:
        raise RuntimeError(f"PaddleOCR 识别失败：{exc}") from exc


def _run_ocr(engine: Any, image: Any) -> Any:
    with _paddleocr_lock:
        try:
            return engine.predict(image)
        except AttributeError:
            return engine.ocr(image, cls=True)
        except TypeError:
            return engine.ocr(image, cls=True)


def _extract_ocr_lines(result: Any) -> list[str]:
    lines: list[str] = []

    if not result:
        return lines

    for item in _flatten_ocr_result(result):
        text = ""
        confidence = 1.0

        if isinstance(item, dict):
            text = str(item.get("text") or item.get("rec_text") or "")
            score = item.get("score") or item.get("rec_score")
            if isinstance(score, int | float):
                confidence = float(score)
        elif isinstance(item, (list, tuple)):
            if len(item) >= 2 and isinstance(item[1], (list, tuple)) and item[1]:
                text = str(item[1][0] or "")
                if len(item[1]) > 1 and isinstance(item[1][1], int | float):
                    confidence = float(item[1][1])
            elif len(item) >= 2 and isinstance(item[0], str):
                text = str(item[0])
                if isinstance(item[1], int | float):
                    confidence = float(item[1])
        elif hasattr(item, "json"):
            try:
                data = item.json
                if callable(data):
                    data = data()
                lines.extend(_extract_ocr_lines(data))
            except Exception:
                pass
            continue

        if text and confidence > 0.5:
            lines.append(text)

    return lines


def _flatten_ocr_result(value: Any) -> list[Any]:
    if isinstance(value, dict):
        if "res" in value:
            return _flatten_ocr_result(value["res"])
        items: list[Any] = []
        for key in ("rec_texts", "rec_scores", "texts", "scores"):
            if key in value:
                texts = value.get("rec_texts") or value.get("texts") or []
                scores = value.get("rec_scores") or value.get("scores") or []
                return list(zip(texts, scores or [1.0] * len(texts)))
        return [value]

    if isinstance(value, (list, tuple)):
        flattened: list[Any] = []
        for item in value:
            if isinstance(item, (list, tuple, dict)) and not (
                isinstance(item, (list, tuple))
                and len(item) >= 2
                and isinstance(item[1], (list, tuple))
            ):
                flattened.extend(_flatten_ocr_result(item))
            else:
                flattened.append(item)
        return flattened

    if hasattr(value, "json"):
        try:
            data = value.json
            if callable(data):
                data = data()
            return _flatten_ocr_result(data)
        except Exception:
            return [value]

    return [value]


# 兼容性别名
recognize_image = recognize_with_paddleocr
