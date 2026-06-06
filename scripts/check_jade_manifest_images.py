from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


IMAGE_KEYS = ("image_path", "image", "path")


def load_records(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    if suffix == ".jsonl":
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                value = json.loads(stripped)
                if isinstance(value, dict):
                    records.append(value)
        return records
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("records", "items", "data", "results"):
            nested = value.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
        return [value]
    return []


def image_path_from(record: dict[str, Any]) -> str:
    for key in IMAGE_KEYS:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and not isinstance(value, (dict, list, tuple)) and str(value).strip():
            return str(value).strip()
    nested = record.get("input")
    if isinstance(nested, dict):
        return image_path_from(nested)
    return ""


def resolve_image(path_text: str, *, base_dir: Path | None = None) -> Path:
    path = Path(path_text)
    if path.is_absolute() or base_dir is None:
        return path
    return base_dir / path


def inspect_images(records: list[dict[str, Any]], *, base_dir: Path | None = None) -> dict[str, Any]:
    missing: list[dict[str, Any]] = []
    present: list[dict[str, Any]] = []
    empty: list[dict[str, Any]] = []

    for index, record in enumerate(records):
        image_text = image_path_from(record)
        if not image_text:
            empty.append({"index": index, "message": "missing image path"})
            continue
        resolved = resolve_image(image_text, base_dir=base_dir)
        item = {"index": index, "image_path": image_text, "resolved_path": str(resolved)}
        if resolved.is_file():
            present.append(item)
        else:
            missing.append(item)

    issues: list[dict[str, Any]] = []
    if empty:
        issues.append({"message": "rows without image path", "count": len(empty), "rows": empty[:50]})
    if missing:
        issues.append({"message": "image files not found", "count": len(missing), "rows": missing[:50]})

    return {
        "status": "ok" if not issues else "failed",
        "row_count": len(records),
        "present_count": len(present),
        "missing_count": len(missing),
        "empty_count": len(empty),
        "base_dir": str(base_dir) if base_dir is not None else "",
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that jade manifest image paths exist on disk.")
    parser.add_argument("--manifest", required=True, type=Path, help="CSV, JSON, or JSONL manifest.")
    parser.add_argument("--base-dir", type=Path, help="Base directory for relative image paths.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload = inspect_images(load_records(args.manifest), base_dir=args.base_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
