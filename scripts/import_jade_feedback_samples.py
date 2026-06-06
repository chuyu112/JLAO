from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


WORKSPACE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = WORKSPACE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_batch_feedback_summary_service import summarize_jade_batch_feedback  # noqa: E402
from app.services.jade_multimodal_service import JADE_COLORS, JADE_STYLES, JADE_THEMES, JADE_WATERS  # noqa: E402
from app.services.jade_training_service import (  # noqa: E402
    CLASS_TO_ID,
    DEFAULT_DATASET_ROOT,
    DEFAULT_FEEDBACK_PATH,
    IMAGE_EXTENSIONS,
    auto_prepare_validation_split,
    build_jade_feedback_dataset,
    class_names_from_feedback,
    count_split_files,
)


UPLOAD_DIR = WORKSPACE_DIR / "uploads" / "jade-samples"
ATTRIBUTE_KEYS = ["color", "water", "style", "theme"]
BOX_KEYS = ["class_name", "x_center", "y_center", "width", "height"]
ATTRIBUTE_CATALOGS = {
    "color": JADE_COLORS,
    "water": JADE_WATERS,
    "style": JADE_STYLES,
    "theme": JADE_THEMES,
}


parser = argparse.ArgumentParser(
    description=(
        "Import local jade images as human-approved feedback records for the "
        "multimodal jade recognizer and YOLO dataset builder."
    )
)
parser.add_argument("--image-dir", type=Path, help="Directory containing jade sample images.")
parser.add_argument("--manifest", type=Path, help="CSV, JSON, or JSONL manifest with image/color/water/style/theme fields.")
parser.add_argument("--feedback-path", type=Path, default=DEFAULT_FEEDBACK_PATH)
parser.add_argument("--text", default="", help="Optional shared presenter text / notes.")
parser.add_argument("--batch-id", default="", help="Optional shared recognition batch ID for traceability.")
parser.add_argument("--color", default="", help="Shared color label, e.g. 阳绿, 紫罗兰, 红翡.")
parser.add_argument("--water", default="", help="Shared water label, e.g. 冰种, 糯冰, 玻璃种.")
parser.add_argument("--style", default="", help="Shared style label, e.g. 手镯, 吊坠, 摆件.")
parser.add_argument("--theme", default="", help="Shared theme label, e.g. 佛公, 财神, 龙牌.")
parser.add_argument("--class-name", default="", help="Explicit YOLO class name, e.g. jade_bangle, caishen.")
parser.add_argument("--needs-review", action="store_true", help="Mark imported rows as pending review instead of approved.")
parser.add_argument(
    "--multi-whole-image",
    action="store_true",
    help="Allow multiple inferred classes to use whole-image boxes. Default requires manual boxes for multi-class rows.",
)
parser.add_argument("--no-copy", action="store_true", help="Reference original image paths instead of copying into uploads/jade-samples.")
parser.add_argument("--dry-run", action="store_true", help="Preview import stats without copying images, appending feedback, or building dataset.")
parser.add_argument("--allow-duplicates", action="store_true", help="Append records even when the same sample fingerprint already exists.")
parser.add_argument("--build-dataset", action="store_true", help="Run the existing dataset builder after importing records.")
parser.add_argument("--auto-val", action="store_true", help="After building the dataset, move a ratio of train labels into val.")
parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation split ratio used with --auto-val.")


_ARGS_HELP = """
Manifest columns / keys:
  image or path or filename   Required image path. Relative paths resolve from the manifest directory.
  color, water, style, theme  Human labels for multimodal attributes.
  text                        Optional per-row presenter text.
  batch_id                    Optional recognition batch ID for traceability.
  class_name                  Optional YOLO class override.
  x_center, y_center, width, height
                              Optional manual YOLO box in normalized coordinates.

Examples:
  python scripts/import_jade_feedback_samples.py --image-dir D:\\jade\\bangles --style 手镯 --color 阳绿 --water 冰种
  python scripts/import_jade_feedback_samples.py --manifest D:\\jade\\samples.csv --build-dataset --auto-val
"""


def _module_doc_hint() -> str:
    return _ARGS_HELP.strip()


def iter_image_rows(image_dir: Path, shared: dict[str, str]) -> Iterable[dict[str, str]]:
    for image_path in sorted(image_dir.iterdir(), key=lambda path: path.name):
        if image_path.is_file() and image_path.suffix.lower() in IMAGE_EXTENSIONS:
            row = dict(shared)
            row["image"] = str(image_path)
            yield row


def load_manifest_rows(manifest: Path) -> list[dict[str, Any]]:
    suffix = manifest.suffix.lower()
    if suffix == ".csv":
        with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        with manifest.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                text = line.strip()
                if text:
                    rows.append(json.loads(text))
        return rows
    with manifest.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        samples = payload.get("samples") or payload.get("records") or []
        return samples if isinstance(samples, list) else []
    return payload if isinstance(payload, list) else []


def row_value(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def resolve_source_image(row: dict[str, Any], base_dir: Path | None) -> Path:
    raw = row_value(row, "image", "path", "filename", "file")
    if not raw:
        raise ValueError("row is missing image/path/filename")
    path = Path(raw)
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    return path


def image_reference(source_image: Path, copy_image: bool) -> str:
    if not copy_image:
        return str(source_image)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / f"imported-{uuid.uuid4().hex[:12]}{source_image.suffix.lower() or '.jpg'}"
    shutil.copy2(source_image, target)
    return f"/uploads/jade-samples/{target.name}"


def explicit_classes(row: dict[str, Any], shared_class_name: str) -> list[str]:
    raw = row_value(row, "class_name", "class", "yolo_class", "class_names") or shared_class_name
    classes: list[str] = []
    for item in raw.replace(";", ",").replace("|", ",").split(","):
        class_name = item.strip()
        if class_name in CLASS_TO_ID and class_name not in classes:
            classes.append(class_name)
    return classes


def manual_box(row: dict[str, Any], classes: list[str]) -> dict[str, Any] | None:
    if not all(row_value(row, key) for key in BOX_KEYS[1:]):
        return None
    class_name = row_value(row, "class_name", "class", "yolo_class") or (classes[0] if classes else "")
    if class_name not in CLASS_TO_ID:
        return None
    try:
        box = {
            "class_name": class_name,
            "x_center": float(row_value(row, "x_center")),
            "y_center": float(row_value(row, "y_center")),
            "width": float(row_value(row, "width")),
            "height": float(row_value(row, "height")),
        }
    except ValueError:
        return None
    return box


def clean_corrected(row: dict[str, Any], shared: dict[str, str]) -> dict[str, str]:
    corrected: dict[str, str] = {}
    for key in ATTRIBUTE_KEYS:
        corrected[key] = canonical_attribute(key, row_value(row, key) or shared.get(key, ""))
    return corrected


def canonical_attribute(key: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    catalog = ATTRIBUTE_CATALOGS.get(key, {})
    if text in catalog:
        return text
    for canonical, aliases in catalog.items():
        if any(alias and alias in text for alias in aliases):
            return canonical
    return text


def build_record(row: dict[str, Any], args: argparse.Namespace, manifest_dir: Path | None) -> dict[str, Any]:
    source_image = resolve_source_image(row, manifest_dir)
    if not source_image.exists():
        raise FileNotFoundError(source_image)

    shared = {key: getattr(args, key) for key in ATTRIBUTE_KEYS}
    corrected = clean_corrected(row, shared)
    text = row_value(row, "text", "notes", "description") or args.text
    batch_id = row_value(row, "batch_id", "batch") or args.batch_id
    image_ref = image_reference(source_image, copy_image=not args.no_copy and not args.dry_run)
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": f"jade-import-{uuid.uuid4().hex[:12]}",
        "created_at": now,
        "input": {
            "image": image_ref,
            "text": text,
            "batch_id": batch_id,
            "source_filename": source_image.name,
            "import_source": str(source_image),
        },
        "predicted": {},
        "corrected": corrected,
        "evidence": {
            "images": [image_ref],
            "texts": [value for value in [text, f"batch_id={batch_id}" if batch_id else ""] if value],
            "detections": [],
        },
        "confidence": 0.99,
        "source": "local-import-human-label",
        "attribute_sources": {
            key: {
                "source": "local-import",
                "method": "manifest-human-label",
                "value": value,
            }
            for key, value in corrected.items()
            if value
        },
        "needs_review": bool(args.needs_review),
        "review_status": "pending" if args.needs_review else "approved",
    }
    classes = class_names_from_feedback(record)
    for class_name in explicit_classes(row, args.class_name):
        if class_name not in classes:
            classes.append(class_name)

    box = manual_box(row, classes)
    if box:
        training = {
            "suggested_classes": classes or [box["class_name"]],
            "yolo_ready": True,
            "requires_manual_box": False,
            "box_mode": "manual-box",
            "box_confirmed_by": "human",
            "yolo_boxes": [box],
        }
    else:
        whole_image_ready = bool(classes) and (len(classes) == 1 or bool(args.multi_whole_image))
        training = {
            "suggested_classes": classes,
            "yolo_ready": bool(classes),
            "requires_manual_box": bool(classes) and not whole_image_ready,
            "box_mode": "whole-image" if whole_image_ready else "",
            "box_confirmed_by": "human" if whole_image_ready else "",
        }
    record["training"] = training
    return record


def append_records(records: list[dict[str, Any]], feedback_path: Path) -> None:
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    with feedback_path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def existing_fingerprints(feedback_path: Path) -> set[str]:
    if not feedback_path.exists():
        return set()
    result: set[str] = set()
    with feedback_path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                record = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                result.add(record_fingerprint(record))
    return result


def record_fingerprint(record: dict[str, Any]) -> str:
    input_payload = record.get("input") if isinstance(record.get("input"), dict) else {}
    training = record.get("training") if isinstance(record.get("training"), dict) else {}
    corrected = record.get("corrected") if isinstance(record.get("corrected"), dict) else {}
    payload = {
        "import_source": str(input_payload.get("import_source") or input_payload.get("image") or "").strip().lower(),
        "corrected": {key: str(corrected.get(key) or "").strip() for key in ATTRIBUTE_KEYS},
        "suggested_classes": sorted(str(item) for item in (training.get("suggested_classes") or []) if str(item).strip()),
        "box_mode": str(training.get("box_mode") or "").strip(),
        "boxes": fingerprint_boxes(training.get("yolo_boxes") or []),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def fingerprint_boxes(boxes: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for box in boxes:
        if not isinstance(box, dict):
            continue
        try:
            result.append(
                {
                    "class_name": str(box.get("class_name") or "").strip(),
                    "x_center": round(float(box.get("x_center", 0)), 6),
                    "y_center": round(float(box.get("y_center", 0)), 6),
                    "width": round(float(box.get("width", 0)), 6),
                    "height": round(float(box.get("height", 0)), 6),
                }
            )
        except (TypeError, ValueError):
            continue
    return result


def main() -> int:
    args = parser.parse_args()
    if not args.image_dir and not args.manifest:
        parser.error("provide --image-dir or --manifest")
    if args.image_dir and args.manifest:
        parser.error("use only one of --image-dir or --manifest")

    shared = {key: getattr(args, key) for key in ATTRIBUTE_KEYS}
    manifest_dir: Path | None = None
    if args.image_dir:
        rows = list(iter_image_rows(args.image_dir, shared))
    else:
        manifest_dir = args.manifest.parent
        rows = load_manifest_rows(args.manifest)

    records: list[dict[str, Any]] = []
    skipped: list[str] = []
    skipped_duplicates = 0
    seen = existing_fingerprints(args.feedback_path) if not args.allow_duplicates else set()
    for row in rows:
        try:
            record = build_record(row, args, manifest_dir)
            fingerprint = record_fingerprint(record)
            if not args.allow_duplicates and fingerprint in seen:
                skipped_duplicates += 1
                continue
            seen.add(fingerprint)
            records.append(record)
        except (FileNotFoundError, ValueError) as exc:
            skipped.append(str(exc))

    if not args.dry_run:
        append_records(records, args.feedback_path)
    result: dict[str, Any] = {
        "status": "ok",
        "dry_run": bool(args.dry_run),
        "feedback_path": str(args.feedback_path),
        "imported": len(records),
        "skipped": len(skipped),
        "skipped_duplicates": skipped_duplicates,
        "skipped_reasons": skipped[:10],
        "ready_whole_image": sum(1 for record in records if record["training"].get("box_mode") == "whole-image"),
        "ready_manual_box": sum(1 for record in records if record["training"].get("box_mode") == "manual-box"),
        "requires_manual_box": sum(1 for record in records if record["training"].get("requires_manual_box")),
        "batch_counts": batch_counts(records),
        "batch_training_counts": batch_training_counts(records),
        "batch_readiness": batch_readiness(records),
        "help": _module_doc_hint(),
    }
    if args.build_dataset and not args.dry_run:
        result["dataset"] = build_jade_feedback_dataset(feedback_path=args.feedback_path, write_yaml=True)
        if args.auto_val:
            result["validation_split"] = auto_prepare_validation_split(val_ratio=args.val_ratio)
        image_counts = count_split_files(DEFAULT_DATASET_ROOT, "images")
        label_counts = count_split_files(DEFAULT_DATASET_ROOT, "labels")
        result["training_thresholds"] = {
            "min_train_labels": 10,
            "min_val_labels": 2,
            "train_labels": label_counts.get("train", 0),
            "val_labels": label_counts.get("val", 0),
            "train_images": image_counts.get("train", 0),
            "val_images": image_counts.get("val", 0),
            "missing_train_labels": max(0, 10 - int(label_counts.get("train", 0))),
            "missing_val_labels": max(0, 2 - int(label_counts.get("val", 0))),
        }
    elif args.build_dataset and args.dry_run:
        result["dataset"] = {"status": "skipped", "reason": "dry-run"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def batch_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return {batch_id: len(batch_records) for batch_id, batch_records in records_by_batch(records).items()}


def batch_training_counts(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    grouped = records_by_batch(records)
    result: dict[str, dict[str, int]] = {}
    for batch_id, batch_records in grouped.items():
        summary = summarize_jade_batch_feedback(batch_records)
        training_counts = summary["training_counts"]
        result[batch_id] = {
            "records": len(batch_records),
            "yolo_ready": int(training_counts.get("yolo_ready") or 0),
            "requires_manual_box": int(training_counts.get("requires_manual_box") or 0),
            "whole_image_box": int(training_counts.get("whole_image_box") or 0),
            "manual_box": int(training_counts.get("manual_box") or 0),
        }
    return result


def batch_readiness(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped = records_by_batch(records)
    result: dict[str, dict[str, Any]] = {}
    for batch_id, batch_records in grouped.items():
        summary = summarize_jade_batch_feedback(batch_records)
        result[batch_id] = summary["readiness"]
    return result


def records_by_batch(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        input_payload = record.get("input") if isinstance(record.get("input"), dict) else {}
        batch_id = str(input_payload.get("batch_id") or "").strip() or "(none)"
        grouped.setdefault(batch_id, []).append(record)
    return grouped


if __name__ == "__main__":
    raise SystemExit(main())
