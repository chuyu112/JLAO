from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from app.services.jade_training_service import (
    DEFAULT_DATASET_ROOT,
    DEFAULT_MODEL_PATH,
    auto_prepare_validation_split,
    build_jade_feedback_dataset,
    get_jade_training_status,
)
from app.services.jade_yolo_service import get_ultralytics_runtime_availability


WORKSPACE_DIR = Path(__file__).resolve().parents[3]
TRAIN_SCRIPT_PATH = WORKSPACE_DIR / "scripts" / "train_jade_yolo.py"
TRAIN_LOG_PATH = WORKSPACE_DIR / "tmp" / "jade-yolo-training.log"
MIN_TRAIN_LABELS_TO_START = 10
MIN_VAL_LABELS_TO_START = 2

_training_process: subprocess.Popen | None = None
_last_auto_build: dict[str, Any] = {}
_last_auto_fix: dict[str, Any] = {}


def get_jade_yolo_training_run_status() -> dict[str, Any]:
    global _training_process
    readiness = get_jade_training_start_readiness()
    return_code = None
    running = False
    pid = 0
    if _training_process is not None:
        return_code = _training_process.poll()
        running = return_code is None
        pid = _training_process.pid

    return {
        "status": "running" if running else "idle",
        "running": running,
        "pid": pid,
        "return_code": return_code,
        "can_start": readiness["can_start"],
        "blocking_reasons": readiness["blocking_reasons"],
        "runtime": readiness["runtime"],
        "auto_build": _last_auto_build,
        "auto_fix": _last_auto_fix,
        "script": str(TRAIN_SCRIPT_PATH),
        "log_path": str(TRAIN_LOG_PATH),
        "log_tail": read_training_log_tail(),
        "model_path": str(DEFAULT_MODEL_PATH),
        "model_exists": DEFAULT_MODEL_PATH.exists(),
        "model_size": DEFAULT_MODEL_PATH.stat().st_size if DEFAULT_MODEL_PATH.exists() else 0,
    }


def get_jade_training_start_readiness() -> dict[str, Any]:
    training_status = get_jade_training_status()
    ultralytics_status = get_ultralytics_runtime_availability()
    package_available = bool(ultralytics_status["available"])
    blocking_reasons: list[str] = []
    if not package_available:
        blocking_reasons.append(f"ultralytics/YOLO 导入失败：{ultralytics_status['error'] or '未安装'}")
    if not TRAIN_SCRIPT_PATH.exists():
        blocking_reasons.append(f"训练脚本不存在：{TRAIN_SCRIPT_PATH}")
    if not (DEFAULT_DATASET_ROOT / "dataset.yaml").exists():
        blocking_reasons.append(f"数据集配置不存在：{DEFAULT_DATASET_ROOT / 'dataset.yaml'}")
    if training_status["dataset"]["labels"]["train"] <= 0:
        blocking_reasons.append("训练集 train 标签为空")
    if training_status["dataset"]["labels"]["val"] <= 0:
        blocking_reasons.append("验证集 val 标签为空")
    if 0 < training_status["dataset"]["labels"]["train"] < MIN_TRAIN_LABELS_TO_START:
        blocking_reasons.append(f"训练集样本太少：train 至少需要 {MIN_TRAIN_LABELS_TO_START} 条标签")
    if 0 < training_status["dataset"]["labels"]["val"] < MIN_VAL_LABELS_TO_START:
        blocking_reasons.append(f"验证集样本太少：val 至少需要 {MIN_VAL_LABELS_TO_START} 条标签")
    return {
        "can_start": not blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "runtime": {
            "ultralytics_available": package_available,
            "ultralytics_error": ultralytics_status["error"],
            "python": sys.executable,
            "dataset_yaml": str(DEFAULT_DATASET_ROOT / "dataset.yaml"),
            "train_labels": training_status["dataset"]["labels"]["train"],
            "val_labels": training_status["dataset"]["labels"]["val"],
            "class_counts": training_status["dataset"].get("class_counts") or {},
            "min_train_labels": MIN_TRAIN_LABELS_TO_START,
            "min_val_labels": MIN_VAL_LABELS_TO_START,
        },
    }

def start_jade_yolo_training(
    *,
    epochs: int = 50,
    imgsz: int = 640,
    batch: str = "auto",
    model: str = "yolo11n.pt",
) -> dict[str, Any]:
    global _last_auto_build, _last_auto_fix, _training_process
    if _training_process is not None and _training_process.poll() is None:
        return get_jade_yolo_training_run_status()

    before_prepare = get_jade_training_status()
    if before_prepare["dataset"]["labels"]["train"] <= 0 and before_prepare["feedback"]["usable_for_yolo"] > 0:
        _last_auto_build = build_jade_feedback_dataset(split="train", val_every=5, write_yaml=True)
    else:
        _last_auto_build = {
            "status": "noop",
            "reason": "train labels already exist or no usable feedback",
            "records": before_prepare["feedback"]["records"],
            "written": 0,
            "skipped": 0,
            "missing_image": 0,
            "no_class": 0,
        }
    _last_auto_fix = auto_prepare_validation_split()
    readiness = get_jade_training_status()
    start_readiness = get_jade_training_start_readiness()
    if start_readiness["blocking_reasons"]:
        raise ValueError("；".join(start_readiness["blocking_reasons"]))
    if not TRAIN_SCRIPT_PATH.exists():
        raise FileNotFoundError(f"training script not found: {TRAIN_SCRIPT_PATH}")
    if not (DEFAULT_DATASET_ROOT / "dataset.yaml").exists():
        raise FileNotFoundError(f"dataset yaml not found: {DEFAULT_DATASET_ROOT / 'dataset.yaml'}")
    if readiness["dataset"]["labels"]["train"] <= 0 or readiness["dataset"]["labels"]["val"] <= 0:
        raise ValueError("training requires at least one train label and one val label")

    TRAIN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        str(TRAIN_SCRIPT_PATH),
        "--data",
        str(DEFAULT_DATASET_ROOT / "dataset.yaml"),
        "--model",
        model,
        "--epochs",
        str(max(1, min(500, int(epochs)))),
        "--imgsz",
        str(max(160, min(1280, int(imgsz)))),
        "--batch",
        str(batch or "auto"),
        "--output",
        str(DEFAULT_MODEL_PATH),
    ]
    with TRAIN_LOG_PATH.open("w", encoding="utf-8") as log_file:
        log_file.write("[JLAO] Starting jade YOLO training\n")
        log_file.write(" ".join(command) + "\n\n")
        log_file.flush()
        _training_process = subprocess.Popen(
            command,
            cwd=str(WORKSPACE_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
    return get_jade_yolo_training_run_status()


def read_training_log_tail(max_chars: int = 4000) -> str:
    if not TRAIN_LOG_PATH.exists():
        return ""
    try:
        text = TRAIN_LOG_PATH.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return text[-max_chars:]

