from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIELDS = [
    "image",
    "batch_id",
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


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge jade manifest CSV files by image path.")
    parser.add_argument("--input", required=True, nargs="+", type=Path, help="Input manifest CSV files in priority order.")
    parser.add_argument("--output", required=True, type=Path, help="Merged manifest CSV output path.")
    args = parser.parse_args()

    merged: dict[str, dict[str, str]] = {}
    sources: dict[str, list[str]] = {}
    for input_path in args.input:
        path = resolve_path(input_path)
        if not path.exists():
            print(json.dumps({"status": "missing-input", "input": str(path)}, ensure_ascii=False))
            return 2
        for row in load_rows(path):
            image = clean(row.get("image"))
            if not image:
                continue
            key = image_key(image)
            existing = merged.setdefault(key, blank_row(image))
            merge_row(existing, row)
            sources.setdefault(key, []).append(str(path))

    output_path = resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for key in sorted(merged):
            writer.writerow(merged[key])

    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(output_path),
                "rows": len(merged),
                "inputs": [str(resolve_path(path)) for path in args.input],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def blank_row(image: str) -> dict[str, str]:
    row = {field: "" for field in FIELDS}
    row["image"] = image
    return row


def merge_row(target: dict[str, str], source: dict[str, Any]) -> None:
    for field in FIELDS:
        value = clean(source.get(field))
        if not value:
            continue
        if field == "review_note" and target.get(field):
            target[field] = f"{target[field]}；{value}"
        else:
            target[field] = value


def image_key(value: str) -> str:
    return value.strip().replace("\\", "/").lower()


def clean(value: Any) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
