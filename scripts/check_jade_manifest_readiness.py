from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTES = ("color", "water", "style", "theme")
IMAGE_KEYS = ("image", "image_path", "path")
ATTRIBUTE_KEYS = {
    "color": ("color", "expected_color", "corrected_color", "actual_color", "颜色"),
    "water": ("water", "expected_water", "corrected_water", "actual_water", "种水", "水头"),
    "style": ("style", "expected_style", "corrected_style", "actual_style", "样式", "器型"),
    "theme": ("theme", "expected_theme", "corrected_theme", "actual_theme", "题材", "主题"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether a jade image manifest is ready for evaluation/training.")
    parser.add_argument("--manifest", required=True, type=Path, help="CSV or JSONL manifest with image and jade labels.")
    parser.add_argument("--allow-missing-images", action="store_true", help="Do not fail when image files are missing.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    manifest_path = resolve_path(args.manifest)
    if not manifest_path.exists():
        print_json({"status": "missing-manifest", "manifest": str(manifest_path)}, pretty=args.pretty)
        return 2

    records = load_manifest(manifest_path)
    row_results = [check_row(index, row, manifest_path) for index, row in enumerate(records, start=1)]
    missing_images = [row for row in row_results if row["image"] and not row["image_exists"]]
    missing_required = [row for row in row_results if row["missing_attributes"]]
    no_image = [row for row in row_results if not row["image"]]
    ready_rows = [
        row
        for row in row_results
        if row["image"] and row["image_exists"] and not row["missing_attributes"]
    ]
    blocking_reasons: list[str] = []
    if not row_results:
        blocking_reasons.append("empty-manifest")
    if no_image:
        blocking_reasons.append("rows-missing-image")
    if missing_required:
        blocking_reasons.append("rows-missing-required-attributes")
    if missing_images and not args.allow_missing_images:
        blocking_reasons.append("rows-missing-image-files")

    payload = {
        "status": "ready" if not blocking_reasons else "blocked",
        "manifest": str(manifest_path),
        "count": len(row_results),
        "ready_rows": len(ready_rows),
        "missing_image_rows": len(no_image),
        "missing_image_files": len(missing_images),
        "missing_attribute_rows": len(missing_required),
        "required_attributes": list(ATTRIBUTES),
        "blocking_reasons": blocking_reasons,
        "rows": row_results,
    }
    print_json(payload, pretty=args.pretty)
    return 0 if not blocking_reasons else 1


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_manifest(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return load_jsonl(path)
    if suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict) and isinstance(value.get("rows"), list):
            return [row for row in value["rows"] if isinstance(row, dict)]
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            cleaned = line.strip()
            if not cleaned:
                continue
            try:
                value = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                rows.append({"_line": line_number, "_error": str(exc)})
                continue
            if isinstance(value, dict):
                rows.append(value)
    return rows


def check_row(index: int, row: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    image = first_value(row, IMAGE_KEYS)
    image_path = resolve_image_path(image, manifest_path.parent) if image else None
    attributes = {key: first_value(row, ATTRIBUTE_KEYS[key]) for key in ATTRIBUTES}
    missing_attributes = [key for key, value in attributes.items() if not value]
    return {
        "row": index,
        "image": image,
        "image_exists": bool(image_path and image_path.exists() and image_path.is_file()),
        "resolved_image": str(image_path) if image_path else "",
        "attributes": attributes,
        "missing_attributes": missing_attributes,
        "error": clean(row.get("_error")),
    }


def resolve_image_path(value: str, manifest_dir: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    manifest_relative = (manifest_dir / path).resolve()
    if manifest_relative.exists():
        return manifest_relative
    return (ROOT / path).resolve()


def first_value(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = clean(row.get(key))
        if value:
            return value
    return ""


def clean(value: Any) -> str:
    return str(value or "").strip()


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None))


if __name__ == "__main__":
    raise SystemExit(main())
