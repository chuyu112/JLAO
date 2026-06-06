from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ATTRIBUTES = ("color", "water", "style", "theme")
DEFAULT_PROMPT = (
    "请识别这件翡翠的颜色、种水、样式和题材。"
    "只返回 JSON，字段为 color、water、style、theme。"
)


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


def value_from(record: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and not isinstance(value, (dict, list, tuple)) and str(value).strip():
            return str(value).strip()
    return ""


def attributes_from(record: dict[str, Any]) -> dict[str, str]:
    return {
        "color": value_from(record, ("color", "expected_color", "corrected_color", "actual_color", "label_color")),
        "water": value_from(record, ("water", "expected_water", "corrected_water", "actual_water", "label_water")),
        "style": value_from(record, ("style", "expected_style", "corrected_style", "actual_style", "label_style")),
        "theme": value_from(record, ("theme", "expected_theme", "corrected_theme", "actual_theme", "label_theme")),
    }


def image_path_from(record: dict[str, Any]) -> str:
    return value_from(record, ("image_path", "image", "path"))


def make_training_record(record: dict[str, Any], *, prompt: str = DEFAULT_PROMPT) -> dict[str, Any]:
    image_path = image_path_from(record)
    attributes = attributes_from(record)
    context_text = value_from(record, ("text", "context_text", "description", "title", "name"))
    user_text = prompt if not context_text else f"{prompt}\n补充文本：{context_text}"
    return {
        "image": image_path,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image_path},
                    {"type": "text", "text": user_text},
                ],
            },
            {
                "role": "assistant",
                "content": json.dumps(attributes, ensure_ascii=False, sort_keys=True),
            },
        ],
        "attributes": attributes,
        "batch_id": value_from(record, ("batch_id",)),
    }


def convert_records(
    records: list[dict[str, Any]],
    *,
    prompt: str = DEFAULT_PROMPT,
    require_complete: bool = True,
) -> dict[str, Any]:
    converted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        image_path = image_path_from(record)
        attributes = attributes_from(record)
        missing = [attribute for attribute in ATTRIBUTES if not attributes.get(attribute)]
        if not image_path:
            skipped.append({"index": index, "reason": "missing_image_path"})
            continue
        if missing and require_complete:
            skipped.append({"index": index, "reason": "missing_attributes", "missing": missing})
            continue
        converted.append(make_training_record(record, prompt=prompt))
    return {"records": converted, "skipped": skipped}


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create VLM training JSONL from labeled jade image manifest.")
    parser.add_argument("--manifest", required=True, type=Path, help="CSV, JSON, or JSONL labeled manifest.")
    parser.add_argument("--output", required=True, type=Path, help="Output VLM training JSONL path.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="User prompt written into each training sample.")
    parser.add_argument("--allow-incomplete", action="store_true", help="Keep rows with incomplete labels.")
    parser.add_argument("--pretty-summary", action="store_true", help="Pretty-print conversion summary.")
    args = parser.parse_args()

    result = convert_records(load_records(args.manifest), prompt=args.prompt, require_complete=not args.allow_incomplete)
    write_jsonl(args.output, result["records"])
    summary = {"written": len(result["records"]), "skipped": result["skipped"], "output": str(args.output)}
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty_summary else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
