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

ATTRIBUTE_KEYS = ["color", "water", "style", "theme"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert a jade review queue CSV into a reviewable training manifest.")
    parser.add_argument("--queue", required=True, type=Path, help="CSV created by select_jade_review_samples.py.")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "jade_review_queue_manifest.csv")
    parser.add_argument("--prefer-expected", action="store_true", help="Prefer expected_* labels when present.")
    parser.add_argument("--whole-image-box", action="store_true", help="Fill a whole-image YOLO box for single-class rows.")
    args = parser.parse_args()

    queue_path = resolve_path(args.queue)
    output_path = resolve_path(args.output)
    rows = load_rows(queue_path)
    manifest_rows = [
        queue_row_to_manifest(row, prefer_expected=args.prefer_expected, whole_image_box=args.whole_image_box)
        for row in rows
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"wrote {len(manifest_rows)} manifest rows to {output_path}; review before import")
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"review queue not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def queue_row_to_manifest(row: dict[str, Any], *, prefer_expected: bool, whole_image_box: bool) -> dict[str, str]:
    attrs = {
        key: choose_label(row, key, prefer_expected=prefer_expected)
        for key in ATTRIBUTE_KEYS
    }
    class_names = class_names_from_feedback({"corrected": {"style": attrs["style"], "theme": attrs["theme"]}})
    single_class = len(class_names) == 1
    box = {
        "x_center": "0.5" if whole_image_box and single_class else "",
        "y_center": "0.5" if whole_image_box and single_class else "",
        "width": "0.85" if whole_image_box and single_class else "",
        "height": "0.85" if whole_image_box and single_class else "",
    }
    note = "; ".join(
        part
        for part in [
            "generated-from-review-queue",
            f"priority={clean(row.get('priority'))}",
            f"batch_id={clean(row.get('batch_id'))}",
            f"reasons={clean(row.get('reasons'))}",
            f"review_flags={clean(row.get('review_flags'))}",
            f"recommended_action={clean(row.get('recommended_action'))}",
        ]
        if part and not part.endswith("=")
    )
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
        "review_note": note,
    }


def choose_label(row: dict[str, Any], key: str, *, prefer_expected: bool) -> str:
    expected = clean(row.get(f"expected_{key}"))
    predicted = clean(row.get(f"predicted_{key}"))
    if prefer_expected and expected:
        return expected
    return predicted or expected


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


if __name__ == "__main__":
    raise SystemExit(main())
