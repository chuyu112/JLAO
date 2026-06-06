from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_batch_trace_service import feedback_record_batch_id  # noqa: E402
from app.services.jade_training_service import DEFAULT_FEEDBACK_PATH, class_names_from_feedback, resolve_feedback_image  # noqa: E402


FIELDS = [
    "image",
    "color",
    "water",
    "style",
    "theme",
    "text",
    "class_name",
    "x_center",
    "y_center",
    "width",
    "height",
    "batch_id",
    "feedback_id",
    "source",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export approved jade feedback JSONL records into a training manifest CSV.")
    parser.add_argument("--feedback", type=Path, default=DEFAULT_FEEDBACK_PATH)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "jade_feedback_manifest.csv")
    parser.add_argument("--batch-id", default="", help="Only export feedback records matching this batch ID.")
    parser.add_argument("--include-pending", action="store_true", help="Include rows still marked needs_review/pending.")
    parser.add_argument("--include-missing-image", action="store_true", help="Include rows whose image cannot be resolved.")
    args = parser.parse_args()

    feedback_path = resolve_path(args.feedback)
    output_path = resolve_path(args.output)
    records = read_feedback_records(feedback_path)
    rows: list[dict[str, Any]] = []
    skipped = {
        "batch": 0,
        "review": 0,
        "missing_image": 0,
        "no_class": 0,
    }

    for record in records:
        if args.batch_id.strip() and feedback_record_batch_id(record) != args.batch_id.strip():
            skipped["batch"] += 1
            continue
        if should_skip_review(record, args.include_pending):
            skipped["review"] += 1
            continue
        image_path = resolve_feedback_image(record)
        if image_path is None and not args.include_missing_image:
            skipped["missing_image"] += 1
            continue
        classes = class_names_from_feedback(record)
        boxes = valid_boxes(record)
        if not classes and not boxes:
            skipped["no_class"] += 1
            continue
        rows.extend(record_rows(record, image_path, classes, boxes))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "status": "ok",
        "feedback": str(feedback_path),
        "output": str(output_path),
        "batch_id": args.batch_id.strip(),
        "records": len(records),
        "rows": len(rows),
        "skipped": skipped,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def read_feedback_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(payload)
    return records


def should_skip_review(record: dict[str, Any], include_pending: bool) -> bool:
    if include_pending:
        return False
    if bool(record.get("needs_review", False)):
        return True
    return str(record.get("review_status") or "").strip() in {"pending", "rejected"}


def valid_boxes(record: dict[str, Any]) -> list[dict[str, Any]]:
    training = record.get("training") if isinstance(record.get("training"), dict) else {}
    boxes = training.get("yolo_boxes")
    if not isinstance(boxes, list):
        return []
    result: list[dict[str, Any]] = []
    for box in boxes:
        if not isinstance(box, dict):
            continue
        class_name = clean(box.get("class_name"))
        try:
            x_center = float(box.get("x_center"))
            y_center = float(box.get("y_center"))
            width = float(box.get("width"))
            height = float(box.get("height"))
        except (TypeError, ValueError):
            continue
        if class_name and 0 <= x_center <= 1 and 0 <= y_center <= 1 and 0 < width <= 1 and 0 < height <= 1:
            result.append(
                {
                    "class_name": class_name,
                    "x_center": x_center,
                    "y_center": y_center,
                    "width": width,
                    "height": height,
                }
            )
    return result


def record_rows(
    record: dict[str, Any],
    image_path: Path | None,
    classes: list[str],
    boxes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    corrected = record.get("corrected") if isinstance(record.get("corrected"), dict) else {}
    evidence = record.get("evidence") if isinstance(record.get("evidence"), dict) else {}
    input_payload = record.get("input") if isinstance(record.get("input"), dict) else {}
    text = "\n".join(str(item).strip() for item in evidence.get("texts") or [] if str(item).strip())
    if not text:
        text = clean(input_payload.get("text"))
    common = {
        "image": str(image_path or ""),
        "color": clean(corrected.get("color")),
        "water": clean(corrected.get("water")),
        "style": clean(corrected.get("style")),
        "theme": clean(corrected.get("theme")),
        "text": text,
        "batch_id": feedback_record_batch_id(record),
        "feedback_id": clean(record.get("id")),
        "source": clean(record.get("source")),
    }
    if boxes:
        return [
            {
                **common,
                "class_name": clean(box.get("class_name")),
                "x_center": box["x_center"],
                "y_center": box["y_center"],
                "width": box["width"],
                "height": box["height"],
            }
            for box in boxes
        ]
    return [
        {
            **common,
            "class_name": ",".join(classes),
            "x_center": "",
            "y_center": "",
            "width": "",
            "height": "",
        }
    ]


def clean(value: Any) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
