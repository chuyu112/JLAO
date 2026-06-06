"""PaddleOCR 中文识别服务。

使用 PaddleOCR 实现本地中文截图 OCR 识别，替代 Windows OCR 和阿里云 OCR。
"""

import io
import logging
import os
from pathlib import Path

import numpy as np


logger = logging.getLogger(__name__)

# PaddleOCR 配置
PADDLEOCR_LANG = os.getenv("PADDLEOCR_LANG", "ch")
PADDLEOCR_USE_GPU = os.getenv("PADDLEOCR_USE_GPU", "false").lower() == "true"

# PaddleOCR 引擎（延迟加载）
_paddleocr_engine = None
_paddleocr_available = False


def _get_paddleocr_engine():
    """获取或初始化 PaddleOCR 引擎。"""
    global _paddleocr_engine, _paddleocr_available

    if _paddleocr_engine is not None:
        return _paddleocr_engine

    try:
        from paddleocr import PaddleOCR

        logger.info("正在初始化 PaddleOCR...")
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

        # 使用 PaddleOCR 识别
        result = engine.ocr(img_array, cls=True)

        if not result or not result[0]:
            return []

        # 提取文字
        lines = []
        for line in result[0]:
            if line:
                text = line[1][0]  # text content
                confidence = line[1][1]  # confidence score
                if text and confidence > 0.5:  # 过滤低置信度结果
                    lines.append(text)

        return lines
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
        # 使用 PaddleOCR 识别
        result = engine.ocr(str(image_path), cls=True)

        if not result or not result[0]:
            return []

        # 提取文字
        lines = []
        for line in result[0]:
            if line:
                text = line[1][0]  # text content
                confidence = line[1][1]  # confidence score
                if text and confidence > 0.5:  # 过滤低置信度结果
                    lines.append(text)

        return lines
    except Exception as exc:
        raise RuntimeError(f"PaddleOCR 识别失败：{exc}") from exc


# 兼容性别名
recognize_image = recognize_with_paddleocr
