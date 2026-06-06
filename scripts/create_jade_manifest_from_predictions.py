from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_training_service import class_names_from_feedback  # noqa: E402


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
    "review_note",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert jade prediction CSV into a reviewable training manifest.")
    parser.add_argument("--predictions", required=True, type=Path, help="CSV created by predict_jade_manifest.py.")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "jade_review_manifest_from_predictions.csv")
    parser.add_argument("--prefer-expected", action="store_true", help="Prefer expected_* columns when they exist.")
    parser.add_argument("--whole-image-box", action="store_true", help="Fill a whole-image YOLO box for single-class rows.")
    args = parser.parse_args()

    predictions_path = resolve_path(args.predictions)
    output_path = resolve_path(args.output)
    rows = load_prediction_rows(predictions_path)
    manifest_rows = [
        prediction_to_manifest_row(row, prefer_expected=args.prefer_expected, whole_image_box=args.whole_image_box)
        for row in rows
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(
        f"wrote {len(manifest_rows)} rows to {output_path}; "
        "review and correct labels/boxes before import or training"
    )
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_prediction_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"predictions file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def prediction_to_manifest_row(row: dict[str, Any], *, prefer_expected: bool, whole_image_box: bool) -> dict[str, str]:
    attrs = {
        "color": choose_value(row, "color", prefer_expected=prefer_expected),
        "water": choose_value(row, "water", prefer_expected=prefer_expected),
        "style": choose_value(row, "style", prefer_expected=prefer_expected),
        "theme": choose_value(row, "theme", prefer_expected=prefer_expected),
    }
    class_names = class_names_from_feedback({"corrected": {"style": attrs["style"], "theme": attrs["theme"]}})
    single_class = len(class_names) == 1
    box = {
        "x_center": "0.5" if whole_image_box and single_class else "",
        "y_center": "0.5" if whole_image_box and single_class else "",
        "width": "0.85" if whole_image_box and single_class else "",
        "height": "0.85" if whole_image_box and single_class else "",
    }
    note_parts = [
        "generated-from-predictions",
        f"prediction_row={clean(row.get('row'))}",
        f"batch_id={clean(row.get('batch_id'))}",
        f"confidence={clean(row.get('confidence'))}",
    ]
    if clean(row.get("error")):
        note_parts.append(f"error={clean(row.get('error'))}")
    if len(class_names) > 1 and not whole_image_box:
        note_parts.append("manual-box-required-for-multi-class")
    return {
        "image": clean(row.get("image")),
        "color": attrs["color"],
        "water": attrs["water"],
        "style": attrs["style"],
        "theme": attrs["theme"],
        "text": clean(row.get("text")),
        "class_name": "|".join(class_names),
        **box,
        "batch_id": clean(row.get("batch_id")),
        "review_note": "; ".join(part for part in note_parts if part),
    }


def choose_value(row: dict[str, Any], key: str, *, prefer_expected: bool) -> str:
    corrected = clean(row.get(f"corrected_{key}"))
    expected = clean(row.get(f"expected_{key}"))
    predicted = clean(row.get(f"predicted_{key}"))
    if corrected:
        return corrected
    if prefer_expected and expected:
        return expected
    return predicted or expected


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


if __name__ == "__main__":
    raise SystemExit(main())
