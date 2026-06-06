from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image

from app.services.jade_training_config import JADE_YOLO_CLASS_NAMES, build_jade_dataset_yaml


WORKSPACE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_FEEDBACK_PATH = WORKSPACE_DIR / "data" / "jade_feedback.jsonl"
DEFAULT_DATASET_ROOT = WORKSPACE_DIR / "data" / "jade_yolo"
DEFAULT_MODEL_PATH = WORKSPACE_DIR / "models" / "jade-yolo.pt"

STYLE_TO_CLASS = {
    "手镯": "jade_bangle",
    "镯子": "jade_bangle",
    "圆条": "jade_bangle",
    "正圈": "jade_bangle",
    "贵妃镯": "jade_bangle",
    "平安镯": "jade_bangle",
    "珠串": "jade_beads",
    "手串": "jade_beads",
    "珠子": "jade_beads",
    "珠链": "jade_beads",
    "项链": "jade_beads",
    "蛋面": "jade_cabochon",
    "戒面": "jade_cabochon",
    "鸽子蛋": "jade_cabochon",
    "吊坠": "jade_pendant",
    "挂件": "jade_pendant",
    "坠子": "jade_pendant",
    "戒指": "jade_ring",
    "戒托": "jade_ring",
    "牌子": "jade_pendant",
    "龙牌": "jade_pendant",
    "山水牌": "jade_pendant",
    "无事牌": "jade_pendant",
    "平安扣": "pingan_kou",
    "扣子": "pingan_kou",
    "摆件": "jade_ornament",
    "把件": "jade_ornament",
    "手把件": "jade_ornament",
}

THEME_TO_CLASS = {
    "观音": "guanyin",
    "观世音": "guanyin",
    "佛公": "buddha",
    "弥勒佛": "buddha",
    "笑佛": "buddha",
    "如意": "ruyi",
    "如意头": "ruyi",
    "叶子": "leaf",
    "树叶": "leaf",
    "金枝玉叶": "leaf",
    "山水": "landscape",
    "山水牌": "landscape",
    "貔貅": "pixiu",
    "皮丘": "pixiu",
    "葫芦": "gourd",
    "福禄": "gourd",
    "财神": "caishen",
    "龙牌": "dragon_plaque",
    "龙": "dragon_plaque",
}

CLASS_TO_ID = {name: index for index, name in enumerate(JADE_YOLO_CLASS_NAMES)}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
LABEL_EXTENSIONS = {".txt"}


def get_jade_training_status(
    *,
    feedback_path: Path = DEFAULT_FEEDBACK_PATH,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    model_path: Path = DEFAULT_MODEL_PATH,
) -> dict[str, Any]:
    records = read_feedback_records(feedback_path)
    review_counts = feedback_review_counts(records)
    usable_records = [
        record
        for record in records
        if is_feedback_record_yolo_dataset_eligible(record)
    ]
    weak_live_records = [record for record in usable_records if record.get("source") == "live-frame-weak-label"]
    requires_manual_box_records = [
        record
        for record in records
        if is_feedback_record_training_eligible(record)
        and class_names_from_feedback(record)
        and resolve_feedback_image(record)
        and feedback_record_requires_manual_box(record)
    ]
    whole_image_box_records = [
        record
        for record in usable_records
        if feedback_record_box_mode(record) == "whole-image"
    ]
    manual_box_records = [
        record
        for record in usable_records
        if feedback_record_box_mode(record) == "manual-box"
    ]
    return {
        "status": "ok",
        "feedback": {
            "path": str(feedback_path),
            "exists": feedback_path.exists(),
            "records": len(records),
            **review_counts,
            "usable_for_yolo": len(usable_records),
            "weak_live_usable": len(weak_live_records),
            "requires_manual_box": len(requires_manual_box_records),
            "whole_image_box": len(whole_image_box_records),
            "manual_box": len(manual_box_records),
        },
        "dataset": {
            "root": str(dataset_root),
            "yaml": str(dataset_root / "dataset.yaml"),
            "yaml_exists": (dataset_root / "dataset.yaml").exists(),
            "images": count_split_files(dataset_root, "images"),
            "labels": count_split_files(dataset_root, "labels"),
            "class_counts": dataset_class_counts(dataset_root),
            "classes": JADE_YOLO_CLASS_NAMES,
        },
        "model": {
            "path": str(model_path),
            "exists": model_path.exists(),
            "size": model_path.stat().st_size if model_path.exists() else 0,
        },
        "workflow": [
            "collect_sample_feedback",
            "build_weak_yolo_dataset",
            "train_jade_yolo_pt",
            "set_JLAO_YOLO_MODEL",
        ],
    }


def build_jade_feedback_dataset(
    *,
    feedback_path: Path = DEFAULT_FEEDBACK_PATH,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    split: str = "train",
    val_every: int = 5,
    write_yaml: bool = True,
) -> dict[str, Any]:
    if split not in {"train", "val"}:
        raise ValueError("split must be train or val")
    if not feedback_path.exists():
        return {
            "status": "missing-feedback",
            "feedback_path": str(feedback_path),
            "records": 0,
            "written": 0,
            "skipped": 0,
            "missing_image": 0,
            "no_class": 0,
            "skipped_unreviewed_or_rejected": 0,
            "whole_image_box": 0,
        }

    ensure_dataset_dirs(dataset_root)
    if write_yaml:
        dataset_yaml_root = dataset_root.relative_to(WORKSPACE_DIR) if dataset_root.is_relative_to(WORKSPACE_DIR) else dataset_root
        (dataset_root / "dataset.yaml").write_text(build_jade_dataset_yaml(dataset_yaml_root), encoding="utf-8")

    stats = {
        "status": "ok",
        "feedback_path": str(feedback_path),
        "dataset_root": str(dataset_root),
        "records": 0,
        "written": 0,
        "skipped": 0,
        "missing_image": 0,
        "no_class": 0,
        "requires_manual_box": 0,
        "skipped_unreviewed_or_rejected": 0,
        "whole_image_box": 0,
        "manual_box": 0,
    }
    for record_index, record in enumerate(read_feedback_records(feedback_path), start=1):
        stats["records"] += 1
        if not is_feedback_record_training_eligible(record):
            stats["skipped"] += 1
            stats["skipped_unreviewed_or_rejected"] += 1
            continue
        class_names = class_names_from_feedback(record)
        if not class_names:
            stats["skipped"] += 1
            stats["no_class"] += 1
            continue
        if feedback_record_requires_manual_box(record):
            stats["skipped"] += 1
            stats["requires_manual_box"] += 1
            continue

        source_image = resolve_feedback_image(record)
        if source_image is None or not source_image.exists():
            stats["skipped"] += 1
            stats["missing_image"] += 1
            continue

        target_split = split
        if val_every and val_every > 0 and record_index % val_every == 0:
            target_split = "val"

        target_stem = safe_stem(record.get("id") or f"jade-feedback-{record_index}")
        target_image = dataset_root / "images" / target_split / f"{target_stem}{source_image.suffix or '.jpg'}"
        target_label = dataset_root / "labels" / target_split / f"{target_stem}.txt"
        shutil.copy2(source_image, target_image)
        target_label.write_text(build_label_text(source_image, record, class_names), encoding="utf-8")
        if feedback_record_box_mode(record) == "whole-image":
            stats["whole_image_box"] += 1
        if feedback_record_box_mode(record) == "manual-box":
            stats["manual_box"] += 1
        stats["written"] += 1
    return stats


def auto_prepare_validation_split(
    *,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    val_ratio: float = 0.2,
) -> dict[str, Any]:
    ensure_dataset_dirs(dataset_root)
    train_labels_dir = dataset_root / "labels" / "train"
    val_labels_dir = dataset_root / "labels" / "val"
    train_images_dir = dataset_root / "images" / "train"
    val_images_dir = dataset_root / "images" / "val"
    train_labels = sorted([path for path in train_labels_dir.glob("*.txt") if path.is_file()], key=lambda path: path.name)
    val_labels = sorted([path for path in val_labels_dir.glob("*.txt") if path.is_file()], key=lambda path: path.name)

    result = {
        "status": "noop",
        "reason": "",
        "moved": 0,
        "skipped": 0,
        "train_labels_before": len(train_labels),
        "val_labels_before": len(val_labels),
        "train_labels_after": len(train_labels),
        "val_labels_after": len(val_labels),
    }
    if val_labels:
        result["reason"] = "val already has labels"
        return result
    if len(train_labels) < 2:
        result["reason"] = "not enough train labels to split"
        return result

    target_val_count = max(1, round(len(train_labels) * max(0.05, min(0.5, val_ratio))))
    for label_path in train_labels[-target_val_count:]:
        image_path = find_dataset_image_for_label(train_images_dir, label_path.stem)
        if image_path is None:
            result["skipped"] += 1
            continue
        target_label = unique_dataset_path(val_labels_dir / label_path.name)
        target_image = unique_dataset_path(val_images_dir / image_path.name)
        shutil.move(str(label_path), str(target_label))
        shutil.move(str(image_path), str(target_image))
        result["moved"] += 1

    result["status"] = "updated" if result["moved"] else "noop"
    result["reason"] = "moved train samples to val" if result["moved"] else "no train label had a matching image"
    result["train_labels_after"] = count_split_files(dataset_root, "labels")["train"]
    result["val_labels_after"] = count_split_files(dataset_root, "labels")["val"]
    return result


def find_dataset_image_for_label(images_dir: Path, stem: str) -> Path | None:
    for suffix in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
        candidate = images_dir / f"{stem}{suffix}"
        if candidate.exists():
            return candidate
    matches = sorted([path for path in images_dir.glob(f"{stem}.*") if path.is_file()], key=lambda path: path.name)
    return matches[0] if matches else None


def unique_dataset_path(path: Path) -> Path:
    if not path.exists():
        return path
    index = 1
    while True:
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def ensure_dataset_dirs(dataset_root: Path) -> None:
    for relative in [
        "images/train",
        "images/val",
        "images/test",
        "labels/train",
        "labels/val",
        "labels/test",
    ]:
        (dataset_root / relative).mkdir(parents=True, exist_ok=True)


def read_feedback_records(feedback_path: Path) -> list[dict[str, Any]]:
    if not feedback_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in feedback_path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        try:
            records.append(json.loads(cleaned))
        except json.JSONDecodeError:
            continue
    return records


def is_feedback_record_training_eligible(record: dict[str, Any]) -> bool:
    if bool(record.get("needs_review", False)):
        return False
    if str(record.get("review_status") or "").strip() == "rejected":
        return False
    return True


def is_feedback_record_yolo_dataset_eligible(record: dict[str, Any]) -> bool:
    if not is_feedback_record_training_eligible(record):
        return False
    if feedback_record_requires_manual_box(record):
        return False
    if not class_names_from_feedback(record):
        return False
    image = resolve_feedback_image(record)
    return bool(image and image.exists())


def feedback_record_requires_manual_box(record: dict[str, Any]) -> bool:
    training = record.get("training") if isinstance(record.get("training"), dict) else {}
    if feedback_record_box_mode(record) == "manual-box" and valid_manual_yolo_boxes(record):
        return False
    if feedback_record_box_mode(record) == "whole-image" and str(training.get("box_confirmed_by") or "") == "human":
        return False
    if bool(training.get("requires_manual_box", False)):
        return True
    if str(record.get("source") or "") == "live-frame-weak-label":
        return True
    return False


def feedback_record_box_mode(record: dict[str, Any]) -> str:
    training = record.get("training") if isinstance(record.get("training"), dict) else {}
    return str(training.get("box_mode") or "").strip()


def feedback_review_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    result = {
        "eligible_records": 0,
        "pending_review": 0,
        "rejected": 0,
        "approved": 0,
    }
    for record in records:
        review_status = str(record.get("review_status") or "").strip()
        if bool(record.get("needs_review", False)):
            result["pending_review"] += 1
        if review_status == "rejected":
            result["rejected"] += 1
        if review_status == "approved":
            result["approved"] += 1
        if is_feedback_record_training_eligible(record):
            result["eligible_records"] += 1
    return result


def count_split_files(dataset_root: Path, group: str) -> dict[str, int]:
    result: dict[str, int] = {}
    allowed_extensions = IMAGE_EXTENSIONS if group == "images" else LABEL_EXTENSIONS
    for split in ["train", "val", "test"]:
        path = dataset_root / group / split
        result[split] = (
            len([item for item in path.glob("*") if item.is_file() and item.suffix.lower() in allowed_extensions])
            if path.exists()
            else 0
        )
    return result


def dataset_class_counts(dataset_root: Path) -> dict[str, int]:
    counts = {name: 0 for name in JADE_YOLO_CLASS_NAMES}
    for split in ["train", "val", "test"]:
        labels_dir = dataset_root / "labels" / split
        if not labels_dir.exists():
            continue
        for label_path in labels_dir.glob("*.txt"):
            for raw_line in label_path.read_text(encoding="utf-8", errors="replace").splitlines():
                parts = raw_line.strip().split()
                if not parts:
                    continue
                try:
                    class_id = int(parts[0])
                except ValueError:
                    continue
                if 0 <= class_id < len(JADE_YOLO_CLASS_NAMES):
                    counts[JADE_YOLO_CLASS_NAMES[class_id]] += 1
    return {name: count for name, count in counts.items() if count > 0}


def class_names_from_feedback(record: dict[str, Any]) -> list[str]:
    corrected = record.get("corrected") or {}
    normalized = normalize_corrected_training_attributes(corrected)
    candidates = [
        class_name_from_value(normalized.get("style"), STYLE_TO_CLASS),
        class_name_from_value(normalized.get("theme"), THEME_TO_CLASS),
    ]
    training = record.get("training") if isinstance(record.get("training"), dict) else {}
    candidates.extend(
        class_name
        for class_name in (training.get("suggested_classes") or [])
        if isinstance(class_name, str) and class_name in CLASS_TO_ID
    )
    for box in training.get("yolo_boxes") or []:
        if isinstance(box, dict):
            class_name = str(box.get("class_name") or "").strip()
            if class_name in CLASS_TO_ID:
                candidates.append(class_name)
    unique: list[str] = []
    for class_name in candidates:
        if class_name and class_name not in unique:
            unique.append(class_name)
    return unique


def normalize_corrected_training_attributes(corrected: dict[str, Any]) -> dict[str, str]:
    style = normalize_training_label(corrected.get("style"))
    theme = normalize_training_label(corrected.get("theme"))
    if style in {"牌子", "牌坠", "小挂件"}:
        style = "挂件"
    elif style in {"龙牌", "山水牌", "无事牌"}:
        if not theme:
            theme = {"龙牌": "龙", "山水牌": "山水", "无事牌": "无事牌"}[style]
        style = "挂件"
    elif style in {"观音", "佛公", "叶子", "如意", "葫芦", "福瓜", "貔貅"}:
        if not theme:
            theme = style
        style = "挂件"
    if theme == "龙牌":
        theme = "龙"
    elif theme == "山水牌":
        theme = "山水"
    elif theme == "平安无事牌":
        theme = "无事牌"
    return {"style": style, "theme": theme}


def class_name_from_value(value: Any, mapping: dict[str, str]) -> str:
    text = normalize_training_label(value)
    if not text:
        return ""
    for alias, class_name in mapping.items():
        if alias in text:
            return class_name
    if text in CLASS_TO_ID:
        return text
    return ""


def normalize_training_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        repaired = text.encode("gbk").decode("utf-8")
    except UnicodeError:
        repaired = text
    return repaired if any("\u4e00" <= char <= "\u9fff" for char in repaired) else text


def resolve_feedback_image(record: dict[str, Any]) -> Path | None:
    evidence = record.get("evidence") or {}
    input_payload = record.get("input") or {}
    candidates: list[Any] = []
    candidates.extend(evidence.get("images") or [])
    candidates.append(input_payload.get("image"))
    for candidate in candidates:
        path = resolve_image_reference(candidate)
        if path is not None:
            return path
    return None


def resolve_image_reference(raw: Any) -> Path | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith("/uploads/"):
        return WORKSPACE_DIR / text.lstrip("/")
    path = Path(text)
    if path.is_absolute():
        return path
    return WORKSPACE_DIR / path


def build_label_text(source_image: Path, record: dict[str, Any], class_names: list[str]) -> str:
    detections = ((record.get("evidence") or {}).get("detections") or [])
    image_size = read_image_size(source_image)
    lines: list[str] = []
    manual_boxes = valid_manual_yolo_boxes(record)
    for box in manual_boxes:
        class_name = str(box.get("class_name") or "")
        if class_name not in CLASS_TO_ID:
            continue
        lines.append(
            f"{CLASS_TO_ID[class_name]} "
            f"{float(box['x_center']):.6f} {float(box['y_center']):.6f} "
            f"{float(box['width']):.6f} {float(box['height']):.6f}"
        )
    if lines:
        return "\n".join(lines) + "\n"
    for class_name in class_names:
        class_id = CLASS_TO_ID[class_name]
        box = best_box_for_class(class_name, detections, image_size) or (0.5, 0.5, 1.0, 1.0)
        lines.append(f"{class_id} {box[0]:.6f} {box[1]:.6f} {box[2]:.6f} {box[3]:.6f}")
    return "\n".join(lines) + "\n"


def valid_manual_yolo_boxes(record: dict[str, Any]) -> list[dict[str, Any]]:
    training = record.get("training") if isinstance(record.get("training"), dict) else {}
    boxes = training.get("yolo_boxes")
    if not isinstance(boxes, list):
        return []
    valid: list[dict[str, Any]] = []
    for box in boxes:
        if not isinstance(box, dict):
            continue
        class_name = str(box.get("class_name") or "")
        if class_name not in CLASS_TO_ID:
            continue
        try:
            x_center = float(box.get("x_center"))
            y_center = float(box.get("y_center"))
            width = float(box.get("width"))
            height = float(box.get("height"))
        except (TypeError, ValueError):
            continue
        if width <= 0 or height <= 0:
            continue
        valid.append(
            {
                "class_name": class_name,
                "x_center": clamp01(x_center),
                "y_center": clamp01(y_center),
                "width": clamp01(width),
                "height": clamp01(height),
            }
        )
    return valid


def read_image_size(source_image: Path) -> tuple[int, int] | None:
    try:
        with Image.open(source_image) as image:
            return image.size
    except Exception:
        return None


def best_box_for_class(
    class_name: str,
    detections: list[dict[str, Any]],
    image_size: tuple[int, int] | None,
) -> tuple[float, float, float, float] | None:
    for detection in detections:
        label = str(detection.get("label") or "")
        if label != class_name:
            continue
        box = detection.get("box")
        if not isinstance(box, list) or len(box) != 4:
            continue
        return xyxy_to_yolo_box(box, image_size)
    return None


def xyxy_to_yolo_box(box: list[Any], image_size: tuple[int, int] | None) -> tuple[float, float, float, float] | None:
    try:
        x1, y1, x2, y2 = [float(value) for value in box]
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    if image_size is None:
        return None
    image_width, image_height = image_size
    if image_width <= 0 or image_height <= 0:
        return None
    center_x = clamp01(((x1 + x2) / 2) / image_width)
    center_y = clamp01(((y1 + y2) / 2) / image_height)
    width = clamp01((x2 - x1) / image_width)
    height = clamp01((y2 - y1) / image_height)
    return center_x, center_y, width, height


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def safe_stem(raw: Any) -> str:
    text = str(raw or "jade-feedback").strip()
    allowed = []
    for char in text:
        allowed.append(char if char.isalnum() or char in ("-", "_") else "-")
    return "".join(allowed).strip("-") or "jade-feedback"


