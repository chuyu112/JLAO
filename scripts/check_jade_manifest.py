from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_training_config import JADE_YOLO_CLASS_NAMES  # noqa: E402
from app.services.jade_multimodal_service import JADE_COLORS, JADE_STYLES, JADE_THEMES, JADE_WATERS  # noqa: E402
from app.services.jade_training_service import IMAGE_EXTENSIONS, class_names_from_feedback  # noqa: E402


ATTRIBUTE_KEYS = ["color", "water", "style", "theme"]
CLASS_SET = set(JADE_YOLO_CLASS_NAMES)
ATTRIBUTE_CATALOGS = {
    "color": JADE_COLORS,
    "water": JADE_WATERS,
    "style": JADE_STYLES,
    "theme": JADE_THEMES,
}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a jade training manifest before import/train.")
    parser.add_argument("--manifest", required=True, type=Path, help="CSV, JSON, or JSONL jade sample manifest.")
    parser.add_argument("--min-train-labels", type=int, default=10)
    parser.add_argument("--min-val-labels", type=int, default=2)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    manifest = resolve_path(args.manifest)
    if not manifest.exists():
        print(json.dumps({"status": "missing-manifest", "manifest": str(manifest)}, ensure_ascii=False))
        return 2

    rows = load_manifest_rows(manifest)
    report = inspect_rows(rows, manifest.parent, args)
    print(json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if report["status"] == "ok" else 2


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


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


def inspect_rows(rows: list[dict[str, Any]], base_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    attribute_counts: dict[str, Counter[str]] = {key: Counter() for key in ATTRIBUTE_KEYS}
    existing_images = 0
    rows_with_training_class = 0
    trainable_rows = 0
    rows_requiring_manual_box = 0

    for index, row in enumerate(rows, start=1):
        image_path = resolve_row_image(row, base_dir)
        if image_path is None:
            issues.append({"index": index, "type": "missing-image-field"})
        elif not image_path.exists():
            issues.append({"index": index, "type": "image-not-found", "image": str(image_path)})
        elif image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            issues.append({"index": index, "type": "unsupported-image-extension", "image": str(image_path)})
        else:
            existing_images += 1

        for key in ATTRIBUTE_KEYS:
            value = clean(row.get(key))
            if value:
                attribute_counts[key][value] += 1
                canonical = canonical_attribute(key, value)
                if canonical:
                    if canonical != value:
                        issues.append({"index": index, "type": f"noncanonical-{key}", key: value, "suggested": canonical})
                else:
                    issues.append({"index": index, "type": f"unknown-{key}", key: value})

        row_classes = parse_classes(row)
        unknown_classes = [class_name for class_name in row_classes if class_name not in CLASS_SET]
        has_box = has_manual_box(row)
        needs_manual_box = len(row_classes) > 1 and not has_box
        if row_classes:
            rows_with_training_class += 1
        if needs_manual_box:
            rows_requiring_manual_box += 1
            issues.append({"index": index, "type": "multi-class-without-manual-box", "classes": row_classes})
        if row_classes and not unknown_classes and not needs_manual_box:
            trainable_rows += 1
        for class_name in row_classes:
            if class_name not in CLASS_SET:
                issues.append({"index": index, "type": "unknown-class-name", "class_name": class_name})
            else:
                class_counts[class_name] += 1

    estimated_val = max(1, round(trainable_rows * max(0.05, min(0.5, args.val_ratio)))) if trainable_rows else 0
    estimated_train = max(0, trainable_rows - estimated_val)
    missing_train = max(0, args.min_train_labels - estimated_train)
    missing_val = max(0, args.min_val_labels - estimated_val)
    blocking = [
        issue
        for issue in issues
        if issue["type"] in {
            "missing-image-field",
            "image-not-found",
            "unsupported-image-extension",
            "unknown-class-name",
            "unknown-color",
            "unknown-water",
            "unknown-style",
            "unknown-theme",
            "multi-class-without-manual-box",
        }
    ]
    if missing_train:
        blocking.append({"type": "not-enough-estimated-train-labels", "missing": missing_train})
    if missing_val:
        blocking.append({"type": "not-enough-estimated-val-labels", "missing": missing_val})

    return {
        "status": "ok" if not blocking else "needs-fix",
        "rows": len(rows),
        "images_existing": existing_images,
        "rows_with_training_class": rows_with_training_class,
        "trainable_rows": trainable_rows,
        "rows_requiring_manual_box": rows_requiring_manual_box,
        "estimated_after_auto_val": {
            "train_labels": estimated_train,
            "val_labels": estimated_val,
            "missing_train_labels": missing_train,
            "missing_val_labels": missing_val,
        },
        "attribute_counts": {key: dict(counter) for key, counter in attribute_counts.items()},
        "class_counts": dict(class_counts),
        "available_classes": JADE_YOLO_CLASS_NAMES,
        "available_attributes": {
            key: sorted(values)
            for key, values in ATTRIBUTE_CATALOGS.items()
        },
        "issue_count": len(issues),
        "blocking_issue_count": len(blocking),
        "issues": issues[:100],
    }


def resolve_row_image(row: dict[str, Any], base_dir: Path) -> Path | None:
    raw = clean(row.get("image") or row.get("path") or row.get("filename") or row.get("file"))
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else (base_dir / path).resolve()


def parse_classes(row: dict[str, Any]) -> list[str]:
    raw = clean(row.get("class_name") or row.get("class") or row.get("yolo_class") or row.get("class_names"))
    result: list[str] = []
    for item in raw.replace(";", ",").replace("|", ",").split(","):
        class_name = item.strip()
        if class_name and class_name not in result:
            result.append(class_name)
    inferred = class_names_from_feedback(
        {
            "corrected": {
                "style": clean(row.get("style")),
                "theme": clean(row.get("theme")),
            },
            "training": {
                "suggested_classes": [class_name for class_name in result if class_name in CLASS_SET],
            },
        }
    )
    for class_name in inferred:
        if class_name not in result:
            result.append(class_name)
    return result


def has_manual_box(row: dict[str, Any]) -> bool:
    return all(clean(row.get(key)) for key in ["x_center", "y_center", "width", "height"])


def clean(value: Any) -> str:
    return str(value or "").strip()


def canonical_attribute(key: str, value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    if text in ATTRIBUTE_CATALOGS[key]:
        return text
    for canonical, aliases in ATTRIBUTE_CATALOGS[key].items():
        if any(alias and alias in text for alias in aliases):
            return canonical
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
