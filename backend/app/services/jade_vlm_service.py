from __future__ import annotations

import base64
import importlib.util
import json
import mimetypes
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.jade_feedback_learning_service import clean_attribute_value


DEFAULT_OLLAMA_VLM_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_VLM_MODEL = "qwen3.5:9b"

DEFAULT_VLM_PROMPT = (
    "你是翡翠图片识别助手。只输出JSON，不要解释，不要描述性文字。\n"
    "你的任务是识别翡翠颜色、种水、形态和题材，同时描述可见透明度、颗粒和质感特征。\n"
    "直播间、户外、上身佩戴、手持讲货画面中，只看翡翠本体；人、手、皮肤、衣服、背景、价签、托盘和灯光都是干扰，不能用于判断翡翠颜色和种水。\n"
    "\n"
    "你必须严格按照以下选项输出，不能自由发挥，不能写描述性文字，不能写句子，只能写选项中的词。\n"
    "\n"
    "输出格式：\n"
    '{"color":"","water":"","object_style":"","transparency":"","grain":"","texture_fineness":"","luster":"","shape_theme":"","confidence":0}'
    "\n"
    "严格从以下选项中选择：\n"
    "- color: 帝王绿/阳绿/辣绿/苹果绿/豆绿/绿色/蓝水/晴水/油青/紫罗兰/春带彩/白冰/无色/白底青/飘花/洒金/黄翡/冰黄/墨翠/红翡/多彩\n"
    "- water: 玻璃种/高冰/冰种/冰胶/起冰/冰糯/糯冰/起胶/糯化/细糯/糯种/豆种\n"
    "- object_style: 手镯/平安扣/蛋面/戒面/戒指/挂件/吊坠/珠串/牌子/摆件/其他\n"
    "- transparency: 不透/微透/半透/高透\n"
    "- grain: 无明显/轻微/明显/很粗\n"
    "- texture_fineness: 细腻/中等/粗\n"
    "- luster: 弱/中/强\n"
    "- shape_theme: 无/观音/佛公/如意/叶子/山水/貔貅/葫芦/无事牌/财神/龙/福瓜/福豆/其他\n"
    "- confidence: 0-100整数\n"
)
EMPTY_VALUES = {
    "",
    "未知",
    "无法判断",
    "不确定",
    "看不清",
    "无",
    "none",
    "null",
    "None",
}
VLM_DESCRIPTION_KEYS = ["name", "title", "description", "caption", "summary", "text", "识别结果", "描述"]
VLM_TERM_CATALOGS: dict[str, dict[str, tuple[str, ...]]] = {
    "color": {
        "帝王绿": ("帝王绿", "高阳绿", "满绿"),
        "阳绿": ("阳绿", "正阳绿"),
        "辣绿": ("辣绿", "辣阳绿"),
        "苹果绿": ("苹果绿", "果绿", "苹果绿色"),
        "豆绿": ("豆绿", "豆青绿"),
        "绿色": ("绿色", "浅绿", "淡绿", "嫩绿", "绿底"),
        "蓝水": ("蓝水", "老蓝水", "蓝底", "蓝绿", "海蓝", "天空蓝"),
        "晴水": ("晴水", "晴底", "晴蓝", "晴绿"),
        "油青": ("油青", "油青绿", "灰绿", "灰绿色"),
        "紫罗兰": ("紫罗兰", "紫色", "淡紫", "春彩", "茄紫"),
        "春带彩": ("春带彩", "春彩"),
        "白冰": ("白冰", "冰白", "白色"),
        "无色": ("无色", "玻璃白", "高冰白", "透明无色"),
        "白底青": ("白底青", "白底飘绿", "白底带绿"),
        "飘花": ("飘花", "飘蓝花", "飘绿花", "蓝花", "绿花"),
        "洒金": ("洒金", "金点", "洒金翡"),
        "黄翡": ("黄翡", "黄雾", "鸡油黄"),
        "冰黄": ("冰黄", "冰种黄翡", "高冰黄翡"),
        "墨翠": ("墨翠", "黑冰", "乌鸡", "黑色"),
        "红翡": ("红翡", "红雾", "红黄翡"),
        "多彩": ("多彩", "彩色", "五彩", "多色"),
    },
    "water": {
        "玻璃种": ("玻璃种", "玻璃底"),
        "高冰": ("高冰", "高冰种", "高冰底"),
        "冰种": ("冰种", "冰底"),
        "冰胶": ("冰胶", "冰起胶", "冰胶感"),
        "起冰": ("起冰", "起冰感"),
        "冰糯": ("冰糯", "冰糯种"),
        "糯冰": ("糯冰", "糯冰种"),
        "起胶": ("起胶", "胶感", "胶块感", "胶质感"),
        "糯化": ("糯化", "糯化种", "化开"),
        "细糯": ("细糯", "细糯种"),
        "糯种": ("糯种", "糯底"),
        "豆种": ("豆种", "豆底"),
    },
    "style": {
        "手镯": ("手镯", "镯子", "圆条", "正圈", "贵妃镯", "平安镯", "手环"),
        "珠串": ("珠串", "手串", "珠子", "珠链", "项链", "佛珠"),
        "蛋面": ("蛋面", "鸽子蛋", "裸石"),
        "戒面": ("戒面", "戒面石"),
        "吊坠": ("吊坠", "坠子", "镶嵌坠", "裸石坠"),
        "挂件": ("挂件", "牌坠", "牌子", "无事牌", "山水牌", "龙牌", "龙牌吊坠", "山水牌吊坠", "小挂件", "观音", "佛公", "叶子", "如意", "葫芦", "福瓜", "福豆", "貔貅"),
        "戒指": ("戒指", "戒托", "戒圈"),
        "平安扣": ("平安扣", "扣子", "怀古"),
        "摆件": ("摆件", "把件", "手把件"),
    },
    "theme": {
        "观音": ("观音", "观世音"),
        "佛公": ("佛公", "弥勒佛", "笑佛", "佛"),
        "如意": ("如意", "如意头"),
        "叶子": ("叶子", "树叶", "金枝玉叶"),
        "山水": ("山水", "山水牌"),
        "貔貅": ("貔貅", "皮丘"),
        "葫芦": ("葫芦", "福禄"),
        "无事牌": ("无事牌", "平安无事牌"),
        "财神": ("财神", "关公", "武财神"),
        "龙": ("龙", "龙牌", "龙纹", "生肖龙"),
        "福瓜": ("福瓜", "瓜"),
        "福豆": ("福豆", "四季豆", "豆荚", "豆子"),
    },
}

def get_vlm_runtime_status() -> dict[str, Any]:
    http_url = configured_vlm_http_url()
    http_model = configured_vlm_http_model()
    http_format = configured_vlm_http_format()
    httpx_available = importlib.util.find_spec("httpx") is not None
    if http_url or http_model:
        local_http = is_ollama_http_url(http_url)
        enabled = bool(http_url and http_model and httpx_available and local_http)
        if enabled:
            reason = "ready"
        elif not local_http:
            reason = "remote-http-vlm-disabled"
        elif not http_url:
            reason = "http-url-not-configured"
        elif not http_model:
            reason = "http-model-not-configured"
        else:
            reason = "httpx-not-installed"
        return {
            "source": "local-vlm-http",
            "enabled": enabled,
            "reason": reason,
            "configured_model_path": http_model,
            "http_url": http_url,
            "http_format": http_format,
            "package_available": {"httpx": httpx_available},
            "env": "JLAO_VLM_HTTP_URL/JLAO_VLM_HTTP_MODEL",
            "default_http_url": DEFAULT_OLLAMA_VLM_URL,
            "default_http_model": DEFAULT_OLLAMA_VLM_MODEL,
            "using_default_http_url": http_url == DEFAULT_OLLAMA_VLM_URL and not os.getenv("JLAO_VLM_HTTP_URL", "").strip(),
            "using_default_http_model": http_model == DEFAULT_OLLAMA_VLM_MODEL and not os.getenv("JLAO_VLM_HTTP_MODEL", "").strip(),
            "config_path": "/opt/jlao/.env",
            "required_env": [],
            "install_hint": "默认通过本机 Ollama 调用 qwen3.5:9b；先运行 ollama pull qwen3.5:9b，并确保 Ollama 服务可访问。",
        }

    model_path = configured_vlm_model()
    transformers_available = importlib.util.find_spec("transformers") is not None
    torch_available = importlib.util.find_spec("torch") is not None
    pillow_available = importlib.util.find_spec("PIL") is not None
    enabled = bool(model_path) and transformers_available and torch_available and pillow_available
    if enabled:
        reason = "ready"
    elif not model_path:
        reason = "model-not-configured"
    elif not transformers_available:
        reason = "transformers-not-installed"
    elif not torch_available:
        reason = "torch-not-installed"
    else:
        reason = "pillow-not-installed"
    return {
        "source": "local-vlm",
        "enabled": enabled,
        "reason": reason,
        "configured_model_path": model_path,
        "package_available": {
            "transformers": transformers_available,
            "torch": torch_available,
            "pillow": pillow_available,
        },
        "env": "JLAO_VLM_MODEL",
        "config_path": "/opt/jlao/.env",
        "required_env": ["JLAO_VLM_MODEL"],
        "install_hint": "本地 transformers VLM 只用于预标注，结果必须人工确认后才能进入训练；服务器不默认运行大模型。",
    }


def analyze_jade_image_with_vlm(image_path: Path, context_text: str = "") -> tuple[dict[str, str], dict[str, Any]]:
    status = get_vlm_runtime_status()
    if not status["enabled"]:
        return {}, status

    if status["source"] == "local-vlm-http":
        return analyze_jade_image_with_http_vlm(image_path, context_text=context_text, status=status)

    try:
        from PIL import Image
    except ImportError:
        return {}, {**status, "enabled": False, "reason": "pillow-not-installed"}

    try:
        pipe = _load_vlm_pipeline(status["configured_model_path"])
        image = Image.open(image_path).convert("RGB")
        prompt = build_vlm_prompt(context_text)
        raw = pipe({"image": image, "text": prompt}, max_new_tokens=180)
        generated = extract_pipeline_text(raw)
        attributes = parse_vlm_attributes(generated)
        return attributes, {
            **status,
            "raw_text": generated[:800],
            "attributes": attributes,
        }
    except Exception as exc:
        return {}, {
            **status,
            "enabled": False,
            "reason": "inference-failed",
            "error": str(exc)[:300],
        }


def configured_vlm_model() -> str:
    return os.getenv("JLAO_VLM_MODEL", "").strip()


def configured_vlm_http_url() -> str:
    return os.getenv("JLAO_VLM_HTTP_URL", DEFAULT_OLLAMA_VLM_URL).strip().rstrip("/")


def configured_vlm_http_model() -> str:
    return os.getenv("JLAO_VLM_HTTP_MODEL", DEFAULT_OLLAMA_VLM_MODEL).strip()


def configured_vlm_http_format() -> str:
    return "ollama"


def configured_vlm_http_timeout() -> float:
    try:
        return max(2.0, min(300.0, float(os.getenv("JLAO_VLM_HTTP_TIMEOUT", "120"))))
    except ValueError:
        return 120.0


def analyze_jade_image_with_http_vlm(
    image_path: Path,
    *,
    context_text: str,
    status: dict[str, Any],
) -> tuple[dict[str, str], dict[str, Any]]:
    try:
        import httpx
    except ImportError:
        return {}, {**status, "enabled": False, "reason": "httpx-not-installed"}

    try:
        # 阶段1：CV 颜色特征提取
        cv_features = extract_color_features(image_path)

        image_base64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        response = post_http_vlm(
            httpx_module=httpx,
            image_base64=image_base64,
            mime_type=mimetypes.guess_type(image_path.name)[0] or "image/jpeg",
            prompt=build_vlm_prompt(context_text),
            status=status,
        )
        generated = extract_http_vlm_text(response)

        # 阶段2：解析 VLM 形态特征
        vlm_features = parse_json_object(generated)
        if vlm_features and any(k in vlm_features for k in ["transparency", "grain", "texture_fineness", "luster", "object_style"]):
            # CV + VLM 两阶段识别
            mapped = map_features_to_jade_labels(vlm_features, cv_features)
            attributes = {
                "color": mapped.get("color", ""),
                "water": mapped.get("water", ""),
                "water_type": mapped.get("water_type", ""),
                "style": mapped.get("style", ""),
                "theme": mapped.get("theme", ""),
                "confidence": mapped.get("confidence", "0"),
            }
        else:
            # 兼容旧的直接输出
            attributes = parse_vlm_attributes(generated)

        return attributes, {
            **status,
            "raw_text": generated[:800],
            "cv_features": cv_features,
            "vlm_features": vlm_features,
            "attributes": attributes,
        }
    except Exception as exc:
        return {}, {
            **status,
            "enabled": False,
            "reason": "http-inference-failed",
            "error": str(exc)[:300],
        }


def build_vlm_prompt(context_text: str = "") -> str:
    prompt = DEFAULT_VLM_PROMPT
    cleaned = re.sub(r"\s+", " ", context_text or "").strip()
    if cleaned:
        prompt += f"\\n主播讲解或屏幕文字参考：{cleaned[:500]}"
    return prompt


def post_http_vlm(
    *,
    httpx_module: Any,
    image_base64: str,
    mime_type: str,
    prompt: str,
    status: dict[str, Any],
) -> Any:
    url = str(status.get("http_url") or "").rstrip("/")
    model = str(status.get("configured_model_path") or "")
    timeout = configured_vlm_http_timeout()
    headers: dict[str, str] = {}

    if not is_ollama_http_url(url):
        raise RuntimeError("remote-http-vlm-disabled")

    endpoint = url if url.endswith("/api/chat") else f"{url}/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": "json",
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_base64],
            }
        ],
        "options": {
            "temperature": 0,
            "num_ctx": 2048,
            "num_predict": 200,
        },
    }
    response = httpx_module.post(endpoint, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def is_ollama_http_url(url: str) -> bool:
    cleaned = str(url or "").rstrip("/")
    return (
        cleaned == DEFAULT_OLLAMA_VLM_URL
        or cleaned.endswith("/api/chat")
        or cleaned.startswith("http://127.0.0.1:11434")
        or cleaned.startswith("http://localhost:11434")
    )


@lru_cache(maxsize=1)
def _load_vlm_pipeline(model_path: str) -> Any:
    from transformers import pipeline

    return pipeline(
        "image-text-to-text",
        model=model_path,
        device_map="auto",
        trust_remote_code=True,
    )


def extract_pipeline_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in ["generated_text", "text", "answer", "output"]:
                value = first.get(key)
                if isinstance(value, str):
                    return value
                if isinstance(value, list):
                    return " ".join(str(item) for item in value)
    if isinstance(raw, dict):
        for key in ["generated_text", "text", "answer", "output"]:
            value = raw.get(key)
            if isinstance(value, str):
                return value
    return str(raw)


def extract_http_vlm_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if not isinstance(raw, dict):
        return str(raw)
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                return " ".join(str(item.get("text") or item) for item in content)
    message = raw.get("message")
    if isinstance(message, dict):
        # Prefer content, fallback to thinking for models that put JSON there
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        thinking = message.get("thinking")
        if isinstance(thinking, str) and thinking.strip():
            return thinking
    for key in ["response", "text", "answer", "output", "generated_text"]:
        value = raw.get(key)
        if isinstance(value, str):
            return value
    return json.dumps(raw, ensure_ascii=False)


def extract_color_features(image_path: Path) -> dict[str, Any]:
    """用 OpenCV 提取图片颜色特征。"""
    try:
        import cv2
        import numpy as np
        from PIL import Image
    except ImportError:
        return {}

    try:
        img = Image.open(image_path).convert("RGB")
        img_array = np.array(img)
        # Convert to OpenCV BGR format
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        # Convert to HSV
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

        # Filter out background: white, light gray, black, very dark
        # White/light background: high value, low saturation
        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 40, 255])
        mask_white = cv2.inRange(hsv, lower_white, upper_white)

        # Gray background: medium value, very low saturation
        lower_gray = np.array([0, 0, 80])
        upper_gray = np.array([180, 40, 200])
        mask_gray = cv2.inRange(hsv, lower_gray, upper_gray)

        # Black/dark background: very low value
        lower_dark = np.array([0, 0, 0])
        upper_dark = np.array([180, 255, 60])
        mask_dark = cv2.inRange(hsv, lower_dark, upper_dark)

        # Human skin is common in live-room/try-on images and otherwise looks
        # like red/yellow jade to simple HSV statistics. Exclude only the
        # lower-saturation skin band so saturated red/yellow jade remains.
        mask_skin = _skin_like_mask_hsv(hsv, np)

        # Combine background masks
        mask_bg = mask_white | mask_gray | mask_dark | mask_skin
        mask_fg = cv2.bitwise_not(mask_bg)

        # If too much is filtered, use green/yellow-green mask instead
        fg_ratio = np.count_nonzero(mask_fg) / mask_fg.size
        if fg_ratio < 0.05:
            # Fallback: keep only green/yellow-green pixels
            lower_green = np.array([25, 20, 20])
            upper_green = np.array([90, 255, 255])
            mask_fg = cv2.inRange(hsv, lower_green, upper_green)
            fg_ratio = np.count_nonzero(mask_fg) / mask_fg.size
            if fg_ratio < 0.05:
                # Last resort: use center crop
                h, w = hsv.shape[:2]
                cy, cx = h // 2, w // 2
                ch, cw = h // 3, w // 3
                mask_fg = np.zeros_like(mask_fg)
                mask_fg[cy-ch:cy+ch, cx-cw:cx+cw] = 255

        # Get foreground pixels
        fg_pixels = img_array[mask_fg > 0]
        fg_hsv = hsv[mask_fg > 0]

        if len(fg_pixels) == 0:
            return {}

        # Calculate stats
        rgb_median = np.median(fg_pixels, axis=0).tolist()
        hsv_median = np.median(fg_hsv, axis=0).tolist()
        hsv_mean = np.mean(fg_hsv, axis=0).tolist()

        # Hue is 0-179 in OpenCV HSV
        hue_median = hsv_median[0]
        hue_mean = hsv_mean[0]
        sat_median = hsv_median[1] / 255.0  # Normalize to 0-1
        sat_mean = hsv_mean[1] / 255.0
        val_median = hsv_median[2] / 255.0
        val_mean = hsv_mean[2] / 255.0

        # Green ratio (hue between 35 and 85 in OpenCV HSV)
        green_mask = (fg_hsv[:, 0] >= 35) & (fg_hsv[:, 0] <= 85)
        green_ratio = np.count_nonzero(green_mask) / len(fg_hsv)
        hue_bucket_ratios = _hue_bucket_ratios(fg_hsv)

        # Grayness score: low saturation = gray
        grayness_score = 1.0 - sat_mean

        # Brightness score
        brightness_score = val_mean

        return {
            "rgb_median": rgb_median,
            "hsv_median": hsv_median,
            "hue_mean": float(hue_mean),
            "hue_median": float(hue_median),
            "saturation_mean": float(sat_mean),
            "saturation_median": float(sat_median),
            "value_mean": float(val_mean),
            "value_median": float(val_median),
            "green_ratio": float(green_ratio),
            "foreground_ratio": float(fg_ratio),
            "skin_filtered_ratio": float(np.count_nonzero(mask_skin) / mask_skin.size),
            "hue_bucket_ratios": hue_bucket_ratios,
            "grayness_score": float(grayness_score),
            "brightness_score": float(brightness_score),
        }
    except Exception:
        return {}


def _skin_like_mask_hsv(hsv: Any, np_module: Any) -> Any:
    h_chan = hsv[..., 0]
    s_chan = hsv[..., 1]
    v_chan = hsv[..., 2]
    hue_skin = (h_chan <= 25) | (h_chan >= 170)
    saturation_skin = (s_chan >= 28) & (s_chan <= 145)
    value_skin = (v_chan >= 70) & (v_chan <= 248)
    return (hue_skin & saturation_skin & value_skin).astype("uint8") * 255


def _hue_bucket_ratios(fg_hsv: Any) -> dict[str, float]:
    if len(fg_hsv) == 0:
        return {}
    total = max(1, len(fg_hsv))
    h_chan = fg_hsv[:, 0]
    return {
        "green": float((((h_chan >= 35) & (h_chan <= 85)).sum()) / total),
        "cyan": float((((h_chan >= 86) & (h_chan <= 105)).sum()) / total),
        "blue": float((((h_chan >= 106) & (h_chan <= 125)).sum()) / total),
        "purple": float((((h_chan >= 126) & (h_chan <= 160)).sum()) / total),
        "yellow": float((((h_chan >= 16) & (h_chan <= 34)).sum()) / total),
        "red_brown": float(((((h_chan >= 0) & (h_chan <= 15)) | (h_chan >= 165)).sum()) / total),
    }


def classify_green_color_by_cv(cv_features: dict[str, Any], vlm_features: dict[str, Any]) -> str:
    """结合 CV 颜色特征和 VLM 特征判断绿色分类。"""
    if not cv_features:
        return "绿色"

    sat_mean = cv_features.get("saturation_mean", 0.5)
    val_mean = cv_features.get("value_mean", 0.5)
    grayness_score = cv_features.get("grayness_score", 0.0)
    hue_mean = cv_features.get("hue_mean", 60)

    grain = str(vlm_features.get("grain", "")).strip()
    texture_fineness = str(vlm_features.get("texture_fineness", "")).strip()
    transparency = str(vlm_features.get("transparency", "")).strip()

    # 苹果绿优先：偏黄绿、明亮、不灰暗
    if 50 <= hue_mean <= 65 and val_mean > 0.45 and sat_mean > 0.3 and grayness_score < 0.5:
        return "苹果绿"
    if val_mean > 0.55 and sat_mean > 0.35 and sat_mean < 0.6 and grayness_score < 0.45:
        return "苹果绿"

    # 豆绿：灰暗、颗粒感、低饱和
    if grayness_score > 0.6 or sat_mean < 0.25:
        return "豆绿"
    if grain in {"明显", "很粗"} or texture_fineness == "粗":
        return "豆绿"
    if transparency in {"不透", "微透"} and sat_mean < 0.35:
        return "豆绿"

    # 苹果绿兜底：偏黄绿、不太灰暗
    if 35 <= hue_mean <= 60 and sat_mean < 0.6 and grayness_score < 0.55:
        return "苹果绿"

    # 阳绿：鲜艳、正绿、高饱和
    if sat_mean > 0.6 and grayness_score < 0.2 and val_mean > 0.4:
        return "阳绿"

    # 油青：偏蓝绿、灰蓝
    if hue_mean < 45 or hue_mean > 80:
        if grayness_score > 0.3:
            return "油青"

    # 默认
    return "绿色"


def map_features_to_jade_labels(vlm_features: dict[str, Any], cv_features: dict[str, Any]) -> dict[str, str]:
    """第二阶段：将 VLM 形态特征 + CV 颜色特征映射为翡翠行业标签。"""
    result = {
        "color": "",
        "water_type": "",
        "style": "",
        "theme": "",
        "confidence": "0",
    }

    transparency = str(vlm_features.get("transparency", "")).strip()
    grain = str(vlm_features.get("grain", "")).strip()
    texture_fineness = str(vlm_features.get("texture_fineness", "")).strip()
    object_style = str(vlm_features.get("object_style", "")).strip()
    shape_theme = str(vlm_features.get("shape_theme", "")).strip()
    direct_color = normalize_vlm_attribute(
        "color",
        clean_attribute_value(
            "color",
            first_payload_value(vlm_features, ["color", "颜色", "color_detail", "color_name"]),
        ),
    )
    direct_water = normalize_vlm_attribute(
        "water",
        clean_attribute_value(
            "water",
            first_payload_value(vlm_features, ["water", "种水", "water_type", "water_detail"]),
        ),
    )

    # 颜色：用 CV 判断
    result["color"] = direct_color or classify_green_color_by_cv(cv_features, vlm_features)

    # 种水规则（结合 VLM 和 CV 特征）
    grayness_score = cv_features.get("grayness_score", 0.0)
    sat_mean = cv_features.get("saturation_mean", 0.5)

    # CV 特征强烈暗示豆种（灰暗、低饱和）- 优先判断
    if direct_water:
        result["water_type"] = direct_water
    elif grayness_score > 0.55 and sat_mean < 0.4:
        result["water_type"] = "豆种"
    # 豆种：低透明 + 粗颗粒
    elif transparency in {"不透", "微透"} and (grain in {"明显", "很粗"} or texture_fineness == "粗"):
        result["water_type"] = "豆种"
    elif transparency in {"微透", "半透"} and texture_fineness in {"细腻", "中等"} and grain in {"无明显", "轻微"}:
        result["water_type"] = "糯种"
    elif transparency in {"半透", "高透"} and grain in {"无明显", "轻微"}:
        result["water_type"] = "冰种"
    elif transparency == "高透" and grain == "无明显":
        result["water_type"] = "高冰"
    else:
        result["water_type"] = "糯种"  # 默认

    # style 映射
    style_map = {
        "手镯": "手镯",
        "珠串": "珠串",
        "蛋面": "蛋面",
        "戒面": "戒面",
        "戒指": "戒指",
        "平安扣": "平安扣",
        "挂件": "挂件",
        "吊坠": "吊坠",
        "牌子": "挂件",
        "戒面": "戒面",
        "摆件": "摆件",
        "其他": "",
    }
    result["style"] = style_map.get(object_style, "")

    # theme 映射
    if shape_theme and shape_theme != "无":
        result["theme"] = normalize_vlm_attribute("theme", shape_theme) or shape_theme

    # confidence
    conf = vlm_features.get("confidence", 0)
    result["confidence"] = str(conf)

    # 兼容 CORE_ATTRIBUTES (color, water, style, theme)
    result["water"] = result["water_type"]

    return result


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?|```$", "", text or "", flags=re.I | re.M).strip()
    try:
        direct_value = json.loads(cleaned)
    except json.JSONDecodeError:
        direct_value = None
    direct_object = first_object_payload(direct_value)
    if direct_object:
        return direct_object
    match = re.search(r"\{.*", cleaned, flags=re.S)
    if not match:
        return {}
    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError:
        # Try to fix incomplete JSON
        json_str = match.group(0)
        # Add missing closing brace and confidence value
        json_str += ' 0}'
        try:
            value = json.loads(json_str)
        except json.JSONDecodeError:
            return {}
    return first_object_payload(value)


def first_labeled_value(text: str, labels: list[str]) -> str:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*[:：]\s*([^,，;；。.!！?？、\n\r}}]+)", text or "", flags=re.I)
        if match:
            return match.group(1).strip().strip('"').strip("'")
    return ""


def parse_vlm_attributes(text: str) -> dict[str, str]:
    raw = parse_json_object(text)
    source = flatten_attribute_payload(raw) if raw else {}
    description = first_description_text(source)
    full_text = " ".join(part for part in [text, description] if part)
    color = normalize_vlm_attribute(
        "color",
        clean_attribute_value(
            "color",
            first_payload_value(source, ["color", "颜色", "翠色", "色", "color_name"])
            or first_labeled_value(text, ["color", "颜色", "翠色", "色"]),
        ),
    ) or first_term_from_description("color", full_text)
    water = normalize_vlm_attribute(
        "water",
        clean_attribute_value(
            "water",
            first_payload_value(source, ["water", "种水", "水头", "透明度", "seed", "texture"])
            or first_labeled_value(text, ["water", "种水", "水头", "透明度"]),
        ),
    ) or first_term_from_description("water", full_text)
    style = legacy_style_from_text(
        first_payload_value(source, ["style", "样式", "器型", "款式", "形制", "type", "shape"])
        or first_labeled_value(text, ["style", "样式", "器型", "款式", "形制"])
        or full_text
    )
    theme = legacy_theme_from_text(
        first_payload_value(source, ["theme", "题材", "主题", "雕工题材", "subject", "motif"])
        or first_labeled_value(text, ["theme", "题材", "主题", "雕工题材"])
        or full_text
    )
    return {"color": color, "water": water, "style": style, "theme": theme}


def legacy_style_from_text(value: Any) -> str:
    compact = str(value or "").strip().replace(" ", "").replace("·", "").replace("/", "")
    if not compact:
        return ""
    catalogs = {
        "平安扣": ("平安扣", "扣子", "怀古"),
        "手镯": ("手镯", "镯子", "圆条", "正圈", "贵妃镯", "平安镯"),
        "珠串": ("珠串", "手串", "珠子", "珠链", "项链"),
        "蛋面": ("蛋面", "鸽子蛋", "裸石"),
        "戒面": ("戒面", "戒面石"),
        "戒指": ("戒指", "戒托", "戒圈"),
        "牌子": ("牌子", "牌型", "龙牌", "山水牌", "无事牌"),
        "吊坠": ("吊坠", "挂件", "坠子", "观音", "佛公", "叶子", "如意", "葫芦", "福瓜", "福豆", "貔貅"),
        "摆件": ("摆件", "把件", "手把件"),
    }
    for canonical, aliases in catalogs.items():
        if compact == canonical or any(alias and alias in compact for alias in aliases):
            return canonical
    return ""


def legacy_theme_from_text(value: Any) -> str:
    compact = str(value or "").strip().replace(" ", "").replace("·", "").replace("/", "")
    if not compact:
        return ""
    catalogs = {
        "观音": ("观音", "观世音"),
        "佛公": ("佛公", "弥勒佛", "笑佛"),
        "如意": ("如意", "如意头"),
        "叶子": ("叶子", "树叶", "金枝玉叶"),
        "山水": ("山水", "山水牌"),
        "貔貅": ("貔貅", "皮丘"),
        "葫芦": ("葫芦", "福禄"),
        "无事牌": ("无事牌", "平安无事牌"),
        "财神": ("财神", "关公", "武财神"),
        "龙牌": ("龙牌", "龙纹", "生肖龙", "龙"),
        "福瓜": ("福瓜", "瓜"),
        "福豆": ("福豆", "四季豆", "豆荚", "豆子"),
    }
    for canonical, aliases in catalogs.items():
        if compact == canonical or any(alias and alias in compact for alias in aliases):
            return canonical
    return ""


def normalize_attribute_dict(raw: dict[str, Any]) -> dict[str, str]:
    source = flatten_attribute_payload(raw)
    description = first_description_text(source)
    color = normalize_vlm_attribute(
        "color",
        clean_attribute_value(
        "color",
        first_payload_value(source, ["color", "颜色", "翠色", "色", "color_name"]),
        ),
    )
    color_detail = normalize_vlm_attribute(
        "color",
        clean_attribute_value(
        "color",
        first_payload_value(source, ["color_detail", "细分色", "细分颜色", "detail_color"]),
        ),
    )
    color_pattern = normalize_color_pattern(first_payload_value(source, ["color_pattern", "花色", "花色结构", "pattern"]))
    color_family = normalize_color_family(first_payload_value(source, ["color_family", "大色系", "色系", "family"]))
    if color_detail in {"飘花", "白底青", "春带彩", "多彩", "洒金"}:
        if not color_pattern or color_pattern == "纯色":
            color_pattern = color_detail
        color_detail = ""
    if not color_detail and color and color not in {"飘花", "白底青", "春带彩", "多彩", "洒金"}:
        color_detail = color
    if not color_pattern:
        color_pattern = color_pattern_from_color(color)
    derived_family = color_family_from_color(color if color_pattern in {"飘花", "白底青", "春带彩", "多彩", "洒金"} else color_detail or color)
    if derived_family:
        color_family = derived_family
    elif not color_family:
        color_family = color_family_from_color(color_detail or color)
    if not color:
        color = color if color else color_from_layers(color_detail=color_detail, color_pattern=color_pattern, color_family=color_family)
    attributes = {
        "color": color,
        "color_family": color_family,
        "color_detail": color_detail,
        "color_pattern": color_pattern,
        "water": normalize_vlm_attribute(
            "water",
            clean_attribute_value(
            "water",
            first_payload_value(source, ["water", "种水", "水头", "透明度", "seed", "texture"]),
            ),
        ),
        "water_detail": normalize_vlm_attribute(
            "water",
            clean_attribute_value(
            "water",
            first_payload_value(source, ["water_detail", "种水细分", "细分种水", "water_grade"]),
            ),
        ),
        "water_texture": normalize_water_texture(
            first_payload_value(source, ["water_texture", "质感", "种水质感", "texture_detail"])
        ),
        "style": normalize_vlm_attribute(
            "style",
            clean_attribute_value(
            "style",
            first_payload_value(source, ["style", "样式", "器型", "款式", "形制", "type", "shape"]),
            ),
        ),
        "theme": normalize_vlm_attribute(
            "theme",
            clean_attribute_value(
            "theme",
            first_payload_value(source, ["theme", "题材", "主题", "雕工题材", "subject", "motif"]),
            ),
        ),
    }
    if not attributes.get("water") and attributes.get("water_detail"):
        attributes["water"] = attributes["water_detail"]
    if not attributes.get("water_detail") and attributes.get("water"):
        attributes["water_detail"] = attributes["water"]
    for key, value in list(attributes.items()):
        if not value and description:
            if key == "color_family":
                attributes[key] = color_family_from_color(attributes.get("color_detail") or attributes.get("color") or first_term_from_description("color", description))
            elif key == "color_pattern":
                attributes[key] = color_pattern_from_color(attributes.get("color") or first_term_from_description("color", description))
            elif key == "color_detail":
                detail_candidate = normalize_vlm_attribute("color", clean_attribute_value("color", first_term_from_description("color", description)))
                attributes[key] = "" if detail_candidate in {"飘花", "白底青", "春带彩", "多彩", "洒金"} else detail_candidate
            elif key == "water_detail":
                attributes[key] = normalize_vlm_attribute("water", clean_attribute_value("water", first_term_from_description("water", description)))
            elif key == "water_texture":
                attributes[key] = normalize_water_texture(description)
            else:
                attributes[key] = normalize_vlm_attribute(key, clean_attribute_value(key, first_term_from_description(key, description)))
    if attributes.get("color_pattern") in {"飘花", "白底青", "春带彩", "多彩", "洒金"}:
        attributes["color"] = attributes["color_pattern"]
    if not attributes.get("color"):
        attributes["color"] = color_from_layers(
            color_detail=attributes.get("color_detail", ""),
            color_pattern=attributes.get("color_pattern", ""),
            color_family=attributes.get("color_family", ""),
        )
    return attributes


def normalize_color_family(value: Any) -> str:
    text = clean_value(value)
    if not text:
        return ""
    compact = text.replace(" ", "").replace("·", "").replace("/", "")
    catalogs = {
        "绿色": ("绿色", "绿", "翠绿"),
        "蓝绿色": ("蓝绿色", "蓝绿", "青色", "青绿", "蓝水", "晴水", "油青"),
        "白色无色": ("白色无色", "白色", "无色", "白冰", "透明", "清透"),
        "紫色": ("紫色", "紫罗兰", "紫"),
        "黄色": ("黄色", "黄", "黄翡", "冰黄", "金黄", "洒金"),
        "红色": ("红色", "红", "红翡", "红黄"),
        "黑色": ("黑色", "黑", "墨翠", "乌鸡"),
        "多彩": ("多彩", "多色", "彩色", "春带彩", "白底青", "飘花"),
    }
    for canonical, aliases in catalogs.items():
        if compact == canonical or any(alias and alias in compact for alias in aliases):
            return canonical
    return ""


def normalize_color_pattern(value: Any) -> str:
    text = clean_value(value)
    if not text:
        return ""
    compact = text.replace(" ", "").replace("·", "").replace("/", "")
    catalogs = {
        "飘花": ("飘花", "飘蓝花", "飘绿花", "蓝花", "绿花"),
        "白底青": ("白底青", "白底带绿", "白底飘绿"),
        "春带彩": ("春带彩", "春彩"),
        "多彩": ("多彩", "五彩", "多色", "彩色"),
        "洒金": ("洒金", "黄雾", "金点"),
        "纯色": ("纯色", "单色", "满色", "均色", "无花"),
    }
    for canonical, aliases in catalogs.items():
        if compact == canonical or any(alias and alias in compact for alias in aliases):
            return canonical
    return ""


def color_family_from_color(color: str) -> str:
    mapping = {
        "帝王绿": "绿色",
        "阳绿": "绿色",
        "辣绿": "绿色",
        "苹果绿": "绿色",
        "豆绿": "绿色",
        "绿色": "绿色",
        "蓝水": "蓝绿色",
        "晴水": "蓝绿色",
        "油青": "蓝绿色",
        "白冰": "白色无色",
        "无色": "白色无色",
        "紫罗兰": "紫色",
        "黄翡": "黄色",
        "冰黄": "黄色",
        "洒金": "黄色",
        "红翡": "红色",
        "墨翠": "黑色",
        "飘花": "多彩",
        "白底青": "多彩",
        "春带彩": "多彩",
        "多彩": "多彩",
    }
    return mapping.get(str(color or ""), "")


def color_pattern_from_color(color: str) -> str:
    if color in {"飘花", "白底青", "春带彩", "多彩", "洒金"}:
        return color
    return "纯色" if color else ""


def color_from_layers(*, color_detail: str, color_pattern: str, color_family: str) -> str:
    if color_pattern in {"飘花", "白底青", "春带彩", "多彩", "洒金"}:
        return color_pattern
    return color_detail or color_family


def normalize_water_texture(value: Any) -> str:
    text = clean_value(value)
    if not text:
        return ""
    compact = text.replace(" ", "").replace("·", "").replace("/", "")
    catalogs = {
        "玻璃感": ("玻璃感", "玻璃", "镜面感", "晶体感"),
        "冰透": ("冰透", "冰感", "起冰", "冰润", "清透"),
        "冰胶": ("冰胶", "冰起胶", "冰胶感"),
        "起胶": ("起胶", "胶感", "胶块感", "果冻感", "玛瑙感"),
        "糯化": ("糯化", "化开", "棉化开", "雾感化开", "糯感"),
        "细腻": ("细腻", "细糯", "结构细", "肉细"),
        "颗粒感": ("颗粒感", "豆性", "颗粒", "晶体粗"),
        "干": ("干", "发干", "石性", "不水"),
    }
    for canonical, aliases in catalogs.items():
        if compact == canonical or any(alias and alias in compact for alias in aliases):
            return canonical
    return ""


def flatten_attribute_payload(raw: dict[str, Any]) -> dict[str, Any]:
    for key in ["attributes", "attribute", "result", "analysis", "jade", "翡翠"]:
        value = raw.get(key)
        if isinstance(value, dict):
            return {**raw, **value}
    return raw


def first_payload_value(raw: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = raw.get(key)
        if value not in [None, ""]:
            return unwrap_payload_value(value)
    return ""


def first_description_text(raw: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in VLM_DESCRIPTION_KEYS:
        value = first_payload_value(raw, [key])
        if value not in [None, ""]:
            parts.append(str(value))
    return " ".join(parts)


def first_term_from_description(key: str, text: str) -> str:
    compact = str(text or "").replace(" ", "").replace("·", "").replace("/", "")
    catalog = VLM_TERM_CATALOGS.get(key) or {}
    if key == "water":
        if "糯冰" in compact:
            return "糯冰"
        if "冰糯" in compact:
            return "冰糯"
    for canonical, aliases in catalog.items():
        if any(alias and alias in compact for alias in aliases):
            return canonical
    return ""


def normalize_vlm_attribute(key: str, value: Any) -> str:
    text = clean_value(value)
    if not text:
        return ""
    matched = first_term_from_description(key, text)
    return matched or text


def first_object_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return {}


def unwrap_payload_value(value: Any) -> Any:
    if isinstance(value, dict):
        for key in ["value", "name", "label", "text", "answer"]:
            nested = value.get(key)
            if nested not in [None, ""]:
                return unwrap_payload_value(nested)
        return ""
    if isinstance(value, list):
        for item in value:
            nested = unwrap_payload_value(item)
            if nested not in [None, ""]:
                return nested
        return ""
    return value


def clean_value(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text in EMPTY_VALUES else text[:24]
