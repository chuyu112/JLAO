from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.jade_training_service import (
    DEFAULT_FEEDBACK_PATH,
    CLASS_TO_ID,
    STYLE_TO_CLASS,
    THEME_TO_CLASS,
    class_name_from_value,
    class_names_from_feedback,
    is_feedback_record_training_eligible,
    is_feedback_record_yolo_dataset_eligible,
    read_feedback_records,
    resolve_feedback_image,
)
from app.services.jade_feedback_learning_service import clean_attribute_value
from app.services.jade_training_config import JADE_YOLO_CLASS_NAMES


WORKSPACE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_EXPORT_DIR = WORKSPACE_DIR / "data" / "jade_annotation_export"
DEFAULT_EXPORT_ZIP = WORKSPACE_DIR / "uploads" / "jade-annotation-export.zip"
DEFAULT_IMPORT_DIR = WORKSPACE_DIR / "data" / "jade_annotation_import"
DEFAULT_DATASET_ROOT = WORKSPACE_DIR / "data" / "jade_yolo"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
ANNOTATION_ATTRIBUTE_KEYS = ["color", "water", "style", "theme", "craft"]


def get_jade_annotation_tasks(
    *,
    feedback_path: Path = DEFAULT_FEEDBACK_PATH,
    limit: int = 80,
) -> dict[str, Any]:
    records = read_feedback_records(feedback_path)
    tasks: list[dict[str, Any]] = []
    class_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    missing_image = 0
    no_class = 0
    pending_review = 0
    rejected = 0

    for record in reversed(records):
        if len(tasks) >= max(1, min(500, limit)):
            break
        corrected = record.get("corrected") or {}
        source = str(record.get("source") or "unknown")
        review_status = str(record.get("review_status") or "")
        if review_status == "rejected":
            rejected += 1
            continue
        if bool(record.get("needs_review", False)):
            pending_review += 1
        source_counts[source] = source_counts.get(source, 0) + 1
        class_names = class_names_from_feedback(record)
        needs_review = bool(record.get("needs_review", False))
        if not class_names:
            no_class += 1
        image_path = resolve_feedback_image(record)
        if image_path is None or not image_path.exists():
            missing_image += 1
            continue
        for class_name in class_names:
            class_counts[class_name] = class_counts.get(class_name, 0) + 1
        tasks.append(
            {
                "id": record.get("id", ""),
                "created_at": record.get("created_at", ""),
                "image": to_public_image_path(image_path),
                "image_path": str(image_path),
                "text": str((record.get("input") or {}).get("text") or "")[:300],
                "corrected": {
                    "color": str(corrected.get("color") or ""),
                    "water": str(corrected.get("water") or ""),
                    "style": str(corrected.get("style") or ""),
                    "theme": str(corrected.get("theme") or ""),
                    "craft": str(corrected.get("craft") or ""),
                },
                "classes": class_names,
                "needs_manual_class": not bool(class_names),
                "source": source,
                "attribute_sources": record.get("attribute_sources") or {},
                "needs_review": needs_review,
                "review_reason": str(record.get("review_reason") or ""),
                "review_status": review_status,
                "confidence": float(record.get("confidence") or 0),
                "training": record.get("training") or {
                    "suggested_classes": class_names,
                    "yolo_ready": bool(class_names),
                    "requires_manual_box": True,
                },
                "status": "needs-review" if needs_review else ("needs-class-and-box" if not class_names else "needs-box-label"),
            }
        )

    return {
        "status": "ok",
        "feedback_path": str(feedback_path),
        "records": len(records),
        "tasks": tasks,
        "task_count": len(tasks),
        "class_counts": class_counts,
        "source_counts": source_counts,
        "missing_image": missing_image,
        "no_class": no_class,
        "pending_review": pending_review,
        "rejected": rejected,
        "instruction": "Draw one YOLO box per suggested class, then save labels as YOLO txt.",
    }


def build_jade_annotation_export(
    *,
    feedback_path: Path = DEFAULT_FEEDBACK_PATH,
    export_dir: Path = DEFAULT_EXPORT_DIR,
    limit: int = 80,
) -> dict[str, Any]:
    payload = get_jade_annotation_tasks(feedback_path=feedback_path, limit=limit)
    tasks = [task for task in payload["tasks"] if not task.get("needs_review")]
    images_dir = export_dir / "images"
    labels_dir = export_dir / "labels_suggested"
    if export_dir.exists():
        shutil.rmtree(export_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    manifest_tasks: list[dict[str, Any]] = []
    copied = 0
    for index, task in enumerate(tasks, start=1):
        source = Path(task["image_path"])
        if not source.exists():
            continue
        stem = f"jade-task-{index:04d}"
        suffix = source.suffix or ".jpg"
        image_name = f"{stem}{suffix}"
        label_name = f"{stem}.txt"
        shutil.copy2(source, images_dir / image_name)
        (labels_dir / label_name).write_text(build_suggested_label_text(task["classes"]), encoding="utf-8")
        copied += 1
        manifest_tasks.append(
            {
                **task,
                "export_image": f"images/{image_name}",
                "suggested_label": f"labels_suggested/{label_name}",
                "note": "labels_suggested uses weak full-image boxes; refine to true object boxes during annotation.",
            }
        )

    manifest = {
        "status": "ok",
        "instruction": "Use images for precise YOLO box annotation. labels_suggested is only a weak class and box reference.",
        "classes": [{"id": index, "name": name} for index, name in enumerate(JADE_YOLO_CLASS_NAMES)],
        "tasks": manifest_tasks,
    }
    (export_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (export_dir / "classes.txt").write_text("\n".join(JADE_YOLO_CLASS_NAMES) + "\n", encoding="utf-8")
    DEFAULT_EXPORT_ZIP.parent.mkdir(parents=True, exist_ok=True)
    if DEFAULT_EXPORT_ZIP.exists():
        DEFAULT_EXPORT_ZIP.unlink()
    shutil.make_archive(str(DEFAULT_EXPORT_ZIP.with_suffix("")), "zip", export_dir)
    return {
        "status": "ok",
        "export_dir": str(export_dir),
        "zip_path": str(DEFAULT_EXPORT_ZIP),
        "zip_url": "/uploads/jade-annotation-export.zip",
        "manifest": str(export_dir / "manifest.json"),
        "classes": str(export_dir / "classes.txt"),
        "images_dir": str(images_dir),
        "labels_suggested_dir": str(labels_dir),
        "task_count": len(tasks),
        "copied": copied,
        "class_counts": payload["class_counts"],
    }


def apply_human_review_sources(record: dict[str, Any], corrected: dict[str, Any], *, method: str = "human-review") -> None:
    sources = record.get("attribute_sources") if isinstance(record.get("attribute_sources"), dict) else {}
    updated_sources = dict(sources)
    previous = record.get("predicted") if isinstance(record.get("predicted"), dict) else {}
    for key in ANNOTATION_ATTRIBUTE_KEYS:
        value = str((corrected or {}).get(key) or "").strip()
        if not value:
            continue
        updated_sources[key] = {
            "source": "live-frame-correction",
            "method": method,
            "value": value,
            "from": str(previous.get(key) or ""),
        }
    record["attribute_sources"] = updated_sources


def class_attributes_from_yolo_classes(class_names: list[str]) -> dict[str, str]:
    updates: dict[str, str] = {}
    style_by_class = {
        "jade_bangle": "手镯",
        "jade_beads": "珠串",
        "jade_necklace": "珠链",
        "jade_cabochon": "蛋面",
        "jade_ring": "戒指",
        "jade_pendant": "吊坠",
        "jade_plaque": "吊坠",
        "pingan_kou": "吊坠",
        "jade_ornament": "摆件",
        "jade_earring": "耳饰",
    }
    theme_by_class = {
        "pingan_kou": "平安扣",
        "guanyin": "观音",
        "buddha": "佛公",
        "ruyi": "如意",
        "leaf": "叶子",
        "landscape": "山水",
        "pixiu": "貔貅",
        "gourd": "葫芦",
        "caishen": "财神",
        "dragon_plaque": "龙牌",
        "fu_gua": "福瓜",
        "fu_dou": "福豆",
    }
    for class_name in class_names:
        if class_name in style_by_class and not updates.get("style"):
            updates["style"] = style_by_class[class_name]
        if class_name in theme_by_class and not updates.get("theme"):
            updates["theme"] = theme_by_class[class_name]
    return updates


def review_jade_annotation_task(
    feedback_id: str,
    action: str,
    corrected: dict[str, Any] | None = None,
    *,
    feedback_path: Path = DEFAULT_FEEDBACK_PATH,
) -> dict[str, Any]:
    normalized_action = action.strip().lower()
    if normalized_action not in {"approve", "reject"}:
        raise ValueError("action must be approve or reject")
    if not feedback_id.strip():
        raise ValueError("feedback_id is required")
    records = read_feedback_records(feedback_path)
    if not records:
        raise FileNotFoundError(f"feedback file not found or empty: {feedback_path}")

    updated_record: dict[str, Any] | None = None
    now = datetime.now(timezone.utc).isoformat()
    for record in records:
        if str(record.get("id") or "") != feedback_id:
            continue
        if normalized_action == "approve":
            merged_corrected = dict(record.get("corrected") or {})
            human_updates: dict[str, Any] = {}
            for key in ANNOTATION_ATTRIBUTE_KEYS:
                value = clean_attribute_value(key, (corrected or {}).get(key))
                if value:
                    merged_corrected[key] = value
                    human_updates[key] = value
            record["corrected"] = merged_corrected
            apply_human_review_sources(record, human_updates)
            record["needs_review"] = False
            record["review_status"] = "approved"
            record["reviewed_at"] = now
        else:
            record["needs_review"] = False
            record["review_status"] = "rejected"
            negative_reason = clean_negative_reason((corrected or {}).get("negative_reason"))
            record["negative_sample"] = True
            record["negative_reason"] = negative_reason
            record["review_reason"] = f"no-labelable-object:{negative_reason}" if negative_reason else "no-labelable-object"
            record["rejected_at"] = now
        updated_record = record
        break
    if updated_record is None:
        raise KeyError(f"feedback task not found: {feedback_id}")

    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = feedback_path.with_suffix(feedback_path.suffix + ".tmp")
    temp_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(feedback_path)
    return {
        "status": "ok",
        "id": feedback_id,
        "action": normalized_action,
        "review_status": updated_record.get("review_status", ""),
        "corrected": updated_record.get("corrected") or {},
        "training_eligible": is_feedback_record_training_eligible(updated_record),
    }


def approve_jade_annotation_whole_image_box(
    feedback_id: str,
    corrected: dict[str, Any] | None = None,
    *,
    feedback_path: Path = DEFAULT_FEEDBACK_PATH,
) -> dict[str, Any]:
    if not feedback_id.strip():
        raise ValueError("feedback_id is required")
    records = read_feedback_records(feedback_path)
    if not records:
        raise FileNotFoundError(f"feedback file not found or empty: {feedback_path}")

    updated_record: dict[str, Any] | None = None
    now = datetime.now(timezone.utc).isoformat()
    for record in records:
        if str(record.get("id") or "") != feedback_id:
            continue
        merged_corrected = dict(record.get("corrected") or {})
        human_updates: dict[str, Any] = {}
        for key in ANNOTATION_ATTRIBUTE_KEYS:
            value = clean_attribute_value(key, (corrected or {}).get(key))
            if value:
                merged_corrected[key] = value
                human_updates[key] = value
        record["corrected"] = merged_corrected
        apply_human_review_sources(record, human_updates)
        suggested_classes = class_names_from_feedback(record)
        if not suggested_classes:
            raise ValueError("样本缺少样式/题材类别，不能进入 YOLO 训练")
        if resolve_feedback_image(record) is None:
            raise ValueError("样本缺少图片，不能进入 YOLO 训练")
        training = record.get("training") if isinstance(record.get("training"), dict) else {}
        record["training"] = {
            **training,
            "suggested_classes": suggested_classes,
            "yolo_ready": True,
            "requires_manual_box": False,
            "box_mode": "whole-image",
            "box_confirmed_by": "human",
        }
        record["needs_review"] = False
        record["review_status"] = "approved"
        record["review_reason"] = "approve-and-whole-image-box"
        record["reviewed_at"] = now
        updated_record = record
        break
    if updated_record is None:
        raise KeyError(f"feedback task not found: {feedback_id}")

    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = feedback_path.with_suffix(feedback_path.suffix + ".tmp")
    temp_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(feedback_path)
    return {
        "status": "ok",
        "id": feedback_id,
        "review_status": updated_record.get("review_status", ""),
        "corrected": updated_record.get("corrected") or {},
        "training": updated_record.get("training") or {},
        "training_eligible": is_feedback_record_yolo_dataset_eligible(updated_record),
    }


def confirm_jade_annotation_whole_image_box(
    feedback_id: str,
    *,
    feedback_path: Path = DEFAULT_FEEDBACK_PATH,
) -> dict[str, Any]:
    if not feedback_id.strip():
        raise ValueError("feedback_id is required")
    records = read_feedback_records(feedback_path)
    if not records:
        raise FileNotFoundError(f"feedback file not found or empty: {feedback_path}")

    updated_record: dict[str, Any] | None = None
    now = datetime.now(timezone.utc).isoformat()
    for record in records:
        if str(record.get("id") or "") != feedback_id:
            continue
        suggested_classes = class_names_from_feedback(record)
        if not suggested_classes:
            raise ValueError("样本缺少样式/题材类别或图片，不能进入 YOLO 训练")
        if resolve_feedback_image(record) is None:
            raise ValueError("样本缺少样式/题材类别或图片，不能进入 YOLO 训练")
        training = record.get("training") if isinstance(record.get("training"), dict) else {}
        record["training"] = {
            **training,
            "suggested_classes": suggested_classes,
            "yolo_ready": True,
            "requires_manual_box": False,
            "box_mode": "whole-image",
            "box_confirmed_by": "human",
        }
        record["needs_review"] = False
        record["review_status"] = "approved"
        record["review_reason"] = "whole-image-box-confirmed"
        record["reviewed_at"] = now
        updated_record = record
        break
    if updated_record is None:
        raise KeyError(f"feedback task not found: {feedback_id}")

    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = feedback_path.with_suffix(feedback_path.suffix + ".tmp")
    temp_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(feedback_path)
    return {
        "status": "ok",
        "id": feedback_id,
        "review_status": updated_record.get("review_status", ""),
        "training": updated_record.get("training") or {},
        "training_eligible": is_feedback_record_yolo_dataset_eligible(updated_record),
    }


def save_jade_annotation_boxes(
    feedback_id: str,
    boxes: list[dict[str, Any]],
    *,
    feedback_path: Path = DEFAULT_FEEDBACK_PATH,
) -> dict[str, Any]:
    if not feedback_id.strip():
        raise ValueError("feedback_id is required")
    normalized_boxes = normalize_yolo_boxes(boxes)
    if not normalized_boxes:
        raise ValueError("请至少画一个有效主体框")
    records = read_feedback_records(feedback_path)
    if not records:
        raise FileNotFoundError(f"feedback file not found or empty: {feedback_path}")

    updated_record: dict[str, Any] | None = None
    now = datetime.now(timezone.utc).isoformat()
    for record in records:
        if str(record.get("id") or "") != feedback_id:
            continue
        if resolve_feedback_image(record) is None:
            raise ValueError("样本缺少图片，不能进入 YOLO 训练")
        suggested_classes = class_names_from_feedback(record)
        for box in normalized_boxes:
            if box["class_name"] not in suggested_classes:
                suggested_classes.append(box["class_name"])
        class_attribute_updates = class_attributes_from_yolo_classes(suggested_classes)
        if class_attribute_updates:
            merged_corrected = dict(record.get("corrected") or {})
            for key, value in class_attribute_updates.items():
                if value:
                    merged_corrected[key] = value
            record["corrected"] = merged_corrected
            apply_human_review_sources(record, class_attribute_updates, method="manual-yolo-box")
        training = record.get("training") if isinstance(record.get("training"), dict) else {}
        record["training"] = {
            **training,
            "suggested_classes": suggested_classes,
            "yolo_ready": True,
            "requires_manual_box": False,
            "box_mode": "manual-box",
            "box_confirmed_by": "human",
            "yolo_boxes": normalized_boxes,
        }
        record["needs_review"] = False
        record["review_status"] = "approved"
        record["review_reason"] = "manual-yolo-box-confirmed"
        record["reviewed_at"] = now
        updated_record = record
        break
    if updated_record is None:
        raise KeyError(f"feedback task not found: {feedback_id}")

    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = feedback_path.with_suffix(feedback_path.suffix + ".tmp")
    temp_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(feedback_path)
    return {
        "status": "ok",
        "id": feedback_id,
        "review_status": updated_record.get("review_status", ""),
        "training": updated_record.get("training") or {},
        "training_eligible": is_feedback_record_yolo_dataset_eligible(updated_record),
    }


def normalize_yolo_boxes(boxes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw_box in boxes[:20]:
        if not isinstance(raw_box, dict):
            continue
        class_name = normalize_box_class_name(raw_box.get("class_name") or raw_box.get("label"))
        if not class_name:
            continue
        try:
            x_center = float(raw_box.get("x_center"))
            y_center = float(raw_box.get("y_center"))
            width = float(raw_box.get("width"))
            height = float(raw_box.get("height"))
        except (TypeError, ValueError):
            continue
        if not all(0.0 <= value <= 1.0 for value in [x_center, y_center, width, height]):
            continue
        if width < 0.03 or height < 0.03:
            continue
        if width > 0.98 or height > 0.98:
            continue
        if width * height < 0.01 or width * height > 0.92:
            continue
        if x_center - width / 2 < 0 or x_center + width / 2 > 1:
            continue
        if y_center - height / 2 < 0 or y_center + height / 2 > 1:
            continue
        normalized.append(
            {
                "class_name": class_name,
                "x_center": round(x_center, 6),
                "y_center": round(y_center, 6),
                "width": round(width, 6),
                "height": round(height, 6),
            }
        )
    return normalized


def normalize_box_class_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text in CLASS_TO_ID:
        return text
    return (
        class_name_from_value(text, STYLE_TO_CLASS)
        or class_name_from_value(text, THEME_TO_CLASS)
        or ""
    )


def clean_negative_reason(value: Any) -> str:
    text = str(value or "").strip()
    allowed = {
        "图里没有翡翠",
        "画面太糊看不清",
        "主体太小",
        "主体被遮挡",
        "被手遮挡",
        "被字幕/弹幕遮挡",
        "只有包装/证书/桌面",
        "多件货混在一起",
        "无法确定主商品",
        "颜色无法100%判断",
        "种水无法100%判断",
        "款式无法100%判断",
        "题材无法100%判断",
        "工艺无法100%判断",
        "图片重复",
        "截图异常/黑屏/花屏",
        "非翡翠商品",
    }
    return text if text in allowed else ""


def import_jade_annotation_zip(
    zip_path: Path,
    *,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    import_dir: Path = DEFAULT_IMPORT_DIR,
    split: str = "auto",
    auto_val_ratio: float = 0.2,
) -> dict[str, Any]:
    if split not in {"auto", "train", "val", "test"}:
        raise ValueError("split must be auto, train, val, or test")
    if not zip_path.exists():
        raise FileNotFoundError(f"zip not found: {zip_path}")
    if auto_val_ratio <= 0 or auto_val_ratio >= 1:
        raise ValueError("auto_val_ratio must be between 0 and 1")

    if import_dir.exists():
        shutil.rmtree(import_dir)
    import_dir.mkdir(parents=True, exist_ok=True)
    safe_extract_zip(zip_path, import_dir)

    image_files = find_files(import_dir, IMAGE_SUFFIXES)
    label_files = find_files(import_dir, {".txt"})

    copied_images = 0
    copied_labels = 0
    unmatched_labels = 0
    invalid_labels: list[dict[str, Any]] = []
    label_by_stem = {path.stem: path for path in label_files}
    valid_label_by_image: dict[Path, Path] = {}
    for image in image_files:
        label = label_by_stem.get(image.stem)
        if label is None:
            continue
        validation_errors = validate_yolo_label_file(label)
        if validation_errors:
            invalid_labels.append({"label": str(label), "errors": validation_errors})
            continue
        valid_label_by_image[image] = label

    auto_split_by_image = build_auto_split_map(list(valid_label_by_image), auto_val_ratio=auto_val_ratio)
    per_split = {
        name: {"images": 0, "labels": 0}
        for name in ["train", "val", "test"]
    }
    for image in image_files:
        target_split = auto_split_by_image.get(image, "train") if split == "auto" else split
        target_images = dataset_root / "images" / target_split
        target_labels = dataset_root / "labels" / target_split
        target_images.mkdir(parents=True, exist_ok=True)
        target_labels.mkdir(parents=True, exist_ok=True)

        target_name = unique_target_name(target_images, image.name)
        shutil.copy2(image, target_images / target_name)
        copied_images += 1
        per_split[target_split]["images"] += 1
        label = valid_label_by_image.get(image)
        if label is None:
            continue
        label_target_name = f"{Path(target_name).stem}.txt"
        shutil.copy2(label, target_labels / label_target_name)
        copied_labels += 1
        per_split[target_split]["labels"] += 1

    image_stems = {path.stem for path in image_files}
    for label in label_files:
        if label.stem not in image_stems:
            unmatched_labels += 1

    return {
        "status": "ok",
        "split": split,
        "auto_val_ratio": auto_val_ratio,
        "per_split": per_split,
        "dataset_root": str(dataset_root),
        "images_dir": str(dataset_root / "images" / split) if split != "auto" else str(dataset_root / "images"),
        "labels_dir": str(dataset_root / "labels" / split) if split != "auto" else str(dataset_root / "labels"),
        "source_zip": str(zip_path),
        "found_images": len(image_files),
        "found_labels": len(label_files),
        "copied_images": copied_images,
        "copied_labels": copied_labels,
        "unmatched_labels": unmatched_labels,
        "invalid_labels": invalid_labels,
        "invalid_label_count": len(invalid_labels),
    }


def build_auto_split_map(image_files: list[Path], *, auto_val_ratio: float) -> dict[Path, str]:
    if len(image_files) < 2:
        return {image: "train" for image in image_files}
    val_interval = max(2, round(1 / auto_val_ratio))
    split_by_image: dict[Path, str] = {}
    has_val = False
    for index, image in enumerate(image_files, start=1):
        is_val = index % val_interval == 0
        if is_val:
            has_val = True
        split_by_image[image] = "val" if is_val else "train"
    if not has_val:
        split_by_image[image_files[-1]] = "val"
    return split_by_image


def safe_extract_zip(zip_path: Path, target_dir: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_path = target_dir / member.filename
            resolved = member_path.resolve()
            if not str(resolved).startswith(str(target_dir.resolve())):
                raise ValueError(f"unsafe zip path: {member.filename}")
        archive.extractall(target_dir)


def find_files(root: Path, suffixes: set[str]) -> list[Path]:
    return sorted(
        [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes and not path.name.startswith(".")
        ],
        key=lambda path: str(path.relative_to(root)).lower(),
    )


def unique_target_name(directory: Path, filename: str) -> str:
    candidate = Path(filename)
    stem = candidate.stem
    suffix = candidate.suffix
    name = candidate.name
    index = 1
    while (directory / name).exists():
        name = f"{stem}-{index}{suffix}"
        index += 1
    return name


def validate_yolo_label_file(label_path: Path) -> list[str]:
    errors: list[str] = []
    lines = label_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not any(line.strip() for line in lines):
        return ["标签文件为空"]
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            errors.append(f"Line {line_number} is not a 5-column YOLO label")
            continue
        try:
            class_id = int(parts[0])
            values = [float(value) for value in parts[1:]]
        except ValueError:
            errors.append(f"Line {line_number} contains non-numeric values")
            continue
        if class_id < 0 or class_id >= len(JADE_YOLO_CLASS_NAMES):
            errors.append(f"Line {line_number} class ID is out of range: {class_id}")
        for value in values:
            if value < 0 or value > 1:
                errors.append(f"Line {line_number} coordinate is outside 0-1: {value}")
        if values[2] <= 0 or values[3] <= 0:
            errors.append(f"Line {line_number} width and height must be greater than 0")
    return errors


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def build_suggested_label_text(class_names: list[str]) -> str:
    lines: list[str] = []
    for class_name in class_names:
        if class_name not in JADE_YOLO_CLASS_NAMES:
            continue
        class_id = JADE_YOLO_CLASS_NAMES.index(class_name)
        lines.append(f"{class_id} 0.500000 0.500000 1.000000 1.000000")
    return "\n".join(lines) + ("\n" if lines else "")


def suggested_classes(corrected: dict[str, Any]) -> list[str]:
    candidates = [
        class_name_from_value(corrected.get("style"), STYLE_TO_CLASS),
        class_name_from_value(corrected.get("theme"), THEME_TO_CLASS),
    ]
    unique: list[str] = []
    for class_name in candidates:
        if class_name and class_name not in unique:
            unique.append(class_name)
    return unique


def to_public_image_path(image_path: Path) -> str:
    parts = image_path.parts
    if "uploads" in parts:
        index = parts.index("uploads")
        return "/" + "/".join(parts[index:])
    return str(image_path)
