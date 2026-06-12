from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from app.services.aliyun_stt_service import normalize_stt_provider
from app.state import WORKSPACE_DIR


RUNTIME_SETTINGS_PATH = WORKSPACE_DIR / "tmp" / "runtime-settings.json"
VALID_LOCAL_STT_DEVICES = {"cpu", "cuda"}
VALID_STT_PROVIDERS = {"local", "aliyun"}


def get_stt_provider() -> str:
    settings = _load_settings()
    return normalize_stt_provider(
        settings.get("stt_provider")
        or os.getenv("NATIVE_STT_PROVIDER")
        or os.getenv("STT_PROVIDER")
        or "local"
    )


def get_local_stt_device() -> str:
    settings = _load_settings()
    return _normalize_local_stt_device(settings.get("local_stt_device") or os.getenv("LOCAL_STT_DEVICE", "cpu"))


def get_stt_runtime_settings() -> dict[str, Any]:
    device = get_local_stt_device()
    provider = get_stt_provider()
    cuda_available = _cuda_available()
    aliyun_configured = _aliyun_stt_configured()
    return {
        "stt_provider": provider,
        "stt_provider_options": [
            {"label": "本地 FunASR", "value": "local", "available": True},
            {"label": "阿里云", "value": "aliyun", "available": aliyun_configured},
        ],
        "aliyun_configured": aliyun_configured,
        "local_stt_engine": os.getenv("LOCAL_STT_ENGINE", "funasr"),
        "local_stt_device": device,
        "local_stt_device_options": [
            {"label": "CPU", "value": "cpu", "available": True},
            {"label": "GPU (CUDA)", "value": "cuda", "available": cuda_available},
        ],
        "cuda_available": cuda_available,
        "model_cache_loaded": _local_stt_model_loaded(),
    }


def update_stt_runtime_settings(*, local_stt_device: str | None = None, stt_provider: str | None = None) -> dict[str, Any]:
    device = _normalize_local_stt_device(local_stt_device) if local_stt_device is not None else get_local_stt_device()
    provider = normalize_stt_provider(stt_provider) if stt_provider is not None else get_stt_provider()
    if provider not in VALID_STT_PROVIDERS:
        raise RuntimeError("不支持的语音识别服务")
    if provider == "aliyun" and not _aliyun_stt_configured():
        raise RuntimeError("阿里云语音识别未配置 appkey/token")
    if device == "cuda" and not _cuda_available():
        raise RuntimeError("当前后端环境未检测到 CUDA，不能切换 GPU")
    if _native_stt_running():
        raise RuntimeError("请先停止语音识别，再切换 STT 服务或 FunASR CPU/GPU")

    settings = _load_settings()
    previous_device = _normalize_local_stt_device(settings.get("local_stt_device") or os.getenv("LOCAL_STT_DEVICE", "cpu"))
    settings["local_stt_device"] = device
    settings["stt_provider"] = provider
    _save_settings(settings)
    if previous_device != device:
        _clear_local_stt_model_cache()
    return get_stt_runtime_settings()


def _normalize_local_stt_device(value: Any) -> str:
    device = str(value or "cpu").strip().lower()
    if device == "gpu":
        device = "cuda"
    if device not in VALID_LOCAL_STT_DEVICES:
        return "cpu"
    return device


def _load_settings() -> dict[str, Any]:
    if not RUNTIME_SETTINGS_PATH.exists():
        return {}
    try:
        data = json.loads(RUNTIME_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_settings(settings: dict[str, Any]) -> None:
    RUNTIME_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _cuda_available() -> bool:
    if importlib.util.find_spec("torch") is None:
        return False
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _aliyun_stt_configured() -> bool:
    return bool(os.getenv("ALIYUN_STT_APP_KEY", "").strip() and os.getenv("ALIYUN_STT_TOKEN", "").strip())


def _native_stt_running() -> bool:
    try:
        from app.services import native_stt_service

        return any(bool(info.get("running")) for info in (native_stt_service.status(sid) for sid in native_stt_service.native_stt_tasks))
    except Exception:
        return False


def _local_stt_model_loaded() -> bool:
    try:
        from app.services.local_stt_service import LocalChunkStt

        return LocalChunkStt.model_cache_loaded()
    except Exception:
        return False


def _clear_local_stt_model_cache() -> None:
    try:
        from app.services.local_stt_service import LocalChunkStt

        LocalChunkStt.reset_model_cache()
    except Exception:
        return
