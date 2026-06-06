from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_training_config import JADE_YOLO_CLASS_DESCRIPTIONS, JADE_YOLO_CLASS_NAMES  # noqa: E402
from app.services.jade_training_service import STYLE_TO_CLASS, THEME_TO_CLASS  # noqa: E402


FIELDS = ["id", "class_name", "label", "kind", "manifest_values"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the jade YOLO class reference CSV from current backend config.")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "jade_yolo_class_reference.csv")
    args = parser.parse_args()

    output_path = resolve_path(args.output)
    rows = [
        {
            "id": index,
            "class_name": class_name,
            "label": display_label(class_name),
            "kind": class_kind(class_name),
            "manifest_values": ";".join(manifest_values(class_name)),
        }
        for index, class_name in enumerate(JADE_YOLO_CLASS_NAMES)
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} classes to {output_path}")
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def display_label(class_name: str) -> str:
    values = manifest_values(class_name)
    if values:
        return values[0]
    description = JADE_YOLO_CLASS_DESCRIPTIONS.get(class_name, class_name)
    return description.split("/")[0].strip()


def class_kind(class_name: str) -> str:
    if any(value == class_name for value in STYLE_TO_CLASS.values()):
        return "style"
    if any(value == class_name for value in THEME_TO_CLASS.values()):
        return "theme"
    return "unknown"


def manifest_values(class_name: str) -> list[str]:
    values: list[str] = []
    for alias, mapped_class in {**STYLE_TO_CLASS, **THEME_TO_CLASS}.items():
        if mapped_class == class_name and alias not in values:
            values.append(alias)
    return values


if __name__ == "__main__":
    raise SystemExit(main())
