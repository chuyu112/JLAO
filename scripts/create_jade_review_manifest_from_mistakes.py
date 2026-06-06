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
    "review_note",
]
ATTRIBUTE_FIELDS = ["color", "water", "style", "theme"]


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a review manifest draft from jade evaluation mistakes CSV.")
    parser.add_argument("--mistakes", type=Path, default=ROOT / "data" / "jade_eval_mistakes.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "jade_review_manifest.csv")
    args = parser.parse_args()

    mistakes_path = resolve_path(args.mistakes)
    output_path = resolve_path(args.output)
    if not mistakes_path.exists():
        print(json.dumps({"status": "missing-mistakes", "mistakes": str(mistakes_path)}, ensure_ascii=False))
        return 2

    mistakes = load_mistakes(mistakes_path)
    rows = review_rows(mistakes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(
        json.dumps(
            {
                "status": "ok",
                "mistakes": str(mistakes_path),
                "output": str(output_path),
                "rows": len(rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_mistakes(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def review_rows(mistakes: list[dict[str, Any]]) -> list[dict[str, str]]:
    by_image: dict[str, dict[str, Any]] = {}
    for mistake in mistakes:
        image = clean(mistake.get("image"))
        if not image:
            continue
        row = by_image.setdefault(
            image,
            {
                "image": image,
                "color": "",
                "water": "",
                "style": "",
                "theme": "",
                "text": "",
                "class_name": "",
                "x_center": "",
                "y_center": "",
                "width": "",
                "height": "",
                "notes": [],
            },
        )
        field = clean(mistake.get("field"))
        if field in ATTRIBUTE_FIELDS and not row[field]:
            row[field] = clean(mistake.get("expected") or mistake.get("raw_expected"))
        row["notes"].append(
            "{mode}.{field}: expected={expected}, predicted={predicted}".format(
                mode=clean(mistake.get("mode")),
                field=field,
                expected=clean(mistake.get("expected")),
                predicted=clean(mistake.get("predicted")) or "<missing>",
            )
        )

    result: list[dict[str, str]] = []
    for row in by_image.values():
        classes = class_names_from_feedback(
            {
                "corrected": {
                    "style": row["style"],
                    "theme": row["theme"],
                }
            }
        )
        result.append(
            {
                "image": row["image"],
                "color": row["color"],
                "water": row["water"],
                "style": row["style"],
                "theme": row["theme"],
                "text": row["text"],
                "class_name": ",".join(classes) or row["class_name"],
                "x_center": row["x_center"],
                "y_center": row["y_center"],
                "width": row["width"],
                "height": row["height"],
                "review_note": "；".join(row["notes"]),
            }
        )
    return sorted(result, key=lambda item: item["image"].lower())


def clean(value: Any) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
