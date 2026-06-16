from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _default_yolo_device() -> str:
    configured = os.getenv("JLAO_YOLO_DEVICE", "").strip()
    if configured:
        return configured
    try:
        import torch
    except Exception:
        return ""
    try:
        return "0" if torch.cuda.is_available() else ""
    except Exception:
        return ""


DEFAULT_YOLO_MODEL_CANDIDATES = (
    "models/jade-yolo.pt",
    "backend/models/jade-yolo.pt",
    "models/yolo11n.pt",
    "models/yolov8n.pt",
)
DEFAULT_PRETRAINED_YOLO_MODEL = "models/yolo11n.pt"
DEFAULT_YOLO_MIN_CONFIDENCE = _float_env("JLAO_YOLO_MIN_CONFIDENCE", 0.15)
DEFAULT_YOLO_DEVICE = _default_yolo_device()
WORKSPACE_DIR = Path(__file__).resolve().parents[3]
YOLO_CONFIG_DIR = WORKSPACE_DIR / ".ultralytics"
YOLO_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(YOLO_CONFIG_DIR))
MPL_CONFIG_DIR = WORKSPACE_DIR / ".matplotlib"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))


@dataclass(frozen=True)
class YoloDetection:
    label: str
    confidence: float
    box: tuple[float, float, float, float]
    style: str = ""
    theme: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "box": [round(value, 2) for value in self.box],
            "style": self.style,
            "theme": self.theme,
        }


def resolve_yolo_model_path(model_path: str | Path | None = None) -> Path | None:
    configured = str(model_path or os.getenv("JLAO_YOLO_MODEL") or "").strip()
    candidates = [configured] if configured else list(DEFAULT_YOLO_MODEL_CANDIDATES)
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if not path.is_absolute():
            path = WORKSPACE_DIR / path
        if path.exists() and path.is_file():
            return path.resolve()
    return None


def resolve_pretrained_yolo_model_ref() -> str:
    configured_pretrained = os.getenv("JLAO_YOLO_PRETRAINED_MODEL", "").strip()
    if configured_pretrained:
        return configured_pretrained
    local_pretrained = WORKSPACE_DIR / DEFAULT_PRETRAINED_YOLO_MODEL
    if local_pretrained.exists() and local_pretrained.is_file():
        return str(local_pretrained)
    return "yolo11n.pt"


@lru_cache(maxsize=1)
def get_ultralytics_runtime_availability() -> dict[str, Any]:
    try:
        from ultralytics import YOLO
    except Exception as exc:
        return {"available": False, "error": str(exc)[:240], "yolo_class": None}
    return {"available": True, "error": "", "yolo_class": YOLO}


def resolve_yolo_model_reference(model_path: str | Path | None = None) -> dict[str, Any]:
    configured = str(model_path or os.getenv("JLAO_YOLO_MODEL") or "").strip()
    resolved_model = resolve_yolo_model_path(model_path)
    if resolved_model is not None:
        return {
            "model_ref": str(resolved_model),
            "resolved_model_path": str(resolved_model),
            "model_kind": "jade-trained" if "jade" in resolved_model.stem.lower() else "local-yolo",
            "pretrained_fallback": False,
        }
    if configured:
        return {
            "model_ref": "",
            "resolved_model_path": "",
            "model_kind": "missing-configured-model",
            "pretrained_fallback": False,
        }
    return {
        "model_ref": resolve_pretrained_yolo_model_ref(),
        "resolved_model_path": "",
        "model_kind": "pretrained-fallback",
        "pretrained_fallback": True,
    }


def get_yolo_runtime_status(model_path: str | Path | None = None) -> dict[str, Any]:
    configured = str(model_path or os.getenv("JLAO_YOLO_MODEL") or "").strip()
    model_reference = resolve_yolo_model_reference(model_path)
    ultralytics_status = get_ultralytics_runtime_availability()
    package_available = bool(ultralytics_status["available"])
    enabled = bool(model_reference["model_ref"]) and package_available
    if enabled and model_reference["model_kind"] == "pretrained-fallback":
        reason = "pretrained-fallback"
    elif enabled:
        reason = "ready"
    elif model_reference["model_kind"] in {"missing-configured-model", "pretrained-fallback"}:
        reason = "model-not-configured"
    elif not package_available:
        reason = "ultralytics-import-failed" if ultralytics_status["error"] else "ultralytics-not-installed"
    else:
        reason = "model-not-configured"
    return {
        "source": "yolo",
        "enabled": enabled,
        "reason": reason,
        "configured_model_path": configured,
        "resolved_model_path": model_reference["resolved_model_path"],
        "model_ref": model_reference["model_ref"],
        "model_kind": model_reference["model_kind"],
        "pretrained_fallback": model_reference["pretrained_fallback"],
        "package_available": package_available,
        "package_error": ultralytics_status["error"],
        "model_candidates": list(DEFAULT_YOLO_MODEL_CANDIDATES),
        "pretrained_model": resolve_pretrained_yolo_model_ref(),
        "min_confidence": DEFAULT_YOLO_MIN_CONFIDENCE,
        "device": DEFAULT_YOLO_DEVICE or "auto",
    }


def jade_attributes_from_yolo_label(label: str) -> tuple[str, str]:
    normalized = _normalize_label_text(label)
    style_terms = {
        "手镯": ("bangle", "bracelet", "jade_bangle", "jade_bracelet", "shouzhuo", "手镯", "镯子", "手环"),
        "珠串": ("bead", "beads", "bracelet_beads", "jade_beads", "珠串", "手串"),
        "珠链": ("necklace", "jade_necklace", "珠链", "项链"),
        "蛋面": ("cabochon", "egg", "jade_cabochon", "ring_face", "蛋面", "戒面", "鸽子蛋"),
        "吊坠": (
            "pendant",
            "jade_pendant",
            "挂件",
            "吊坠",
            "坠子",
            "plaque",
            "jade_plaque",
            "牌子",
            "无事牌",
            "山水牌",
            "龙牌",
            "pingan_kou",
            "safety_buckle",
            "平安扣",
            "怀古",
        ),
        "戒指": ("ring", "jade_ring", "戒指", "戒托", "戒圈"),
        "摆件": ("ornament", "display", "carving", "摆件", "把件", "手把件"),
        "耳饰": ("earring", "earrings", "ear_jewelry", "jade_earring", "耳饰", "耳环", "耳坠", "耳钉"),
    }
    theme_terms = {
        "观音": ("guanyin", "kwanyin", "观音", "观世音"),
        "佛公": ("buddha", "fo_gong", "弥勒佛", "佛公", "笑佛"),
        "如意": ("ruyi", "如意", "如意头"),
        "叶子": ("leaf", "leaves", "叶子", "金枝玉叶"),
        "山水": ("landscape", "shanshui", "山水", "山水牌"),
        "貔貅": ("pixiu", "貔貅", "皮丘"),
        "葫芦": ("gourd", "hulu", "葫芦", "福禄"),
        "平安扣": ("pingan_kou", "safety_buckle", "平安扣", "怀古"),
        "无事牌": ("safe_plaque", "wushi", "无事牌", "平安无事牌"),
        "财神": ("caishen", "wealth_god", "财神", "关公", "武财神"),
        "龙牌": ("dragon", "dragon_plaque", "longpai", "龙牌", "龙纹", "生肖龙"),
        "福瓜": ("fu_gua", "fugua", "福瓜", "瓜"),
        "福豆": ("fu_dou", "fudou", "bean", "beans", "福豆", "四季豆", "豆荚", "豆子"),
    }
    return _first_label_match(normalized, style_terms), _first_label_match(normalized, theme_terms)


def detect_jade_candidates(
    image_path: Path,
    *,
    model_path: str | Path | None = None,
    min_confidence: float = DEFAULT_YOLO_MIN_CONFIDENCE,
    max_detections: int = 6,
) -> tuple[list[YoloDetection], dict[str, Any]]:
    status = get_yolo_runtime_status(model_path)
    model_ref = status.get("model_ref") or ""
    if not status["enabled"] or not model_ref:
        return [], {
            "source": "yolo",
            "enabled": False,
            "reason": status["reason"],
            "package_available": status["package_available"],
            "model_candidates": status["model_candidates"],
            "model_kind": status.get("model_kind", ""),
        }

    ultralytics_status = get_ultralytics_runtime_availability()
    if not ultralytics_status["available"] or ultralytics_status["yolo_class"] is None:
        return [], {
            "source": "yolo",
            "enabled": False,
            "reason": "ultralytics-import-failed",
            "model_path": model_ref,
            "model_kind": status.get("model_kind", ""),
            "error": ultralytics_status["error"],
        }

    try:
        model = _load_yolo_model(model_ref, model_cache_token(model_ref), ultralytics_status["yolo_class"])
        predict_kwargs: dict[str, Any] = {
            "source": str(image_path),
            "conf": min_confidence,
            "imgsz": 640,
            "max_det": max_detections,
            "verbose": False,
        }
        if DEFAULT_YOLO_DEVICE:
            predict_kwargs["device"] = DEFAULT_YOLO_DEVICE
        results = model.predict(**predict_kwargs)
    except Exception as exc:
        return [], {
            "source": "yolo",
            "enabled": False,
            "reason": "inference-failed",
            "model_path": model_ref,
            "model_kind": status.get("model_kind", ""),
            "error": str(exc)[:240],
        }

    detections: list[YoloDetection] = []
    names = getattr(model, "names", {}) or {}
    for result in results or []:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            cls_value = int(box.cls[0].item()) if getattr(box, "cls", None) is not None else -1
            label = str(names.get(cls_value, cls_value))
            confidence = float(box.conf[0].item()) if getattr(box, "conf", None) is not None else 0.0
            coords = tuple(float(value) for value in box.xyxy[0].tolist())
            style, theme = jade_attributes_from_yolo_label(label)
            detections.append(YoloDetection(label=label, confidence=confidence, box=coords, style=style, theme=theme))

    detections.sort(key=lambda item: item.confidence, reverse=True)
    limited = detections[:max_detections]
    return limited, {
        "source": "yolo",
        "enabled": True,
        "model_path": model_ref,
        "model_kind": status.get("model_kind", ""),
        "pretrained_fallback": status.get("pretrained_fallback", False),
        "min_confidence": min_confidence,
        "device": DEFAULT_YOLO_DEVICE or "auto",
        "detections": [item.to_dict() for item in limited],
    }


def model_cache_token(model_ref: str) -> str:
    path = Path(model_ref)
    if not path.exists() or not path.is_file():
        return "external"
    try:
        stat = path.stat()
    except OSError:
        return "unknown"
    return f"{stat.st_mtime_ns}:{stat.st_size}"


@lru_cache(maxsize=4)
def _load_yolo_model(model_path: str, cache_token: str, yolo_class: Any) -> Any:
    return yolo_class(model_path)


def _normalize_label_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        repaired = text.encode("gbk").decode("utf-8")
        if _chinese_count(repaired) > _chinese_count(text):
            text = repaired
    except UnicodeError:
        pass
    return text.lower().replace("-", "_").replace(" ", "_")


def _first_label_match(normalized: str, catalog: dict[str, tuple[str, ...]]) -> str:
    for canonical, aliases in catalog.items():
        for alias in aliases:
            normalized_alias = _normalize_label_text(alias)
            if normalized_alias and normalized_alias in normalized:
                return canonical
    return ""


def _chinese_count(value: str) -> int:
    return sum(1 for char in value if "\u4e00" <= char <= "\u9fff")
