from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ATTRIBUTES = ("color", "water", "style", "theme")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if isinstance(value, dict):
                value["_line_number"] = line_number
                records.append(value)
    return records


def assistant_json(record: dict[str, Any]) -> dict[str, Any]:
    messages = record.get("messages")
    if not isinstance(messages, list):
        return {}
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if isinstance(content, str):
            try:
                value = json.loads(content)
            except json.JSONDecodeError:
                return {}
            return value if isinstance(value, dict) else {}
        if isinstance(content, dict):
            return content
    return {}


def has_user_image_message(record: dict[str, Any]) -> bool:
    messages = record.get("messages")
    if not isinstance(messages, list):
        return False
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, list):
            return any(isinstance(item, dict) and item.get("type") == "image" and item.get("image") for item in content)
    return False


def inspect_records(records: list[dict[str, Any]], *, require_complete: bool = True) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    for index, record in enumerate(records):
        line_number = record.get("_line_number", index + 1)
        image = record.get("image")
        answer = assistant_json(record)
        missing = [attribute for attribute in ATTRIBUTES if not str(answer.get(attribute, "")).strip()]
        if not isinstance(image, str) or not image.strip():
            issues.append({"index": index, "line": line_number, "message": "missing image"})
        if not has_user_image_message(record):
            issues.append({"index": index, "line": line_number, "message": "missing user image content"})
        if not answer:
            issues.append({"index": index, "line": line_number, "message": "missing assistant JSON answer"})
        if require_complete and missing:
            issues.append({"index": index, "line": line_number, "message": "missing assistant attributes", "fields": missing})
        summaries.append(
            {
                "index": index,
                "line": line_number,
                "image": image,
                "attributes": {attribute: answer.get(attribute) for attribute in ATTRIBUTES},
            }
        )

    return {
        "status": "ok" if not issues else "failed",
        "count": len(records),
        "require_complete": require_complete,
        "issues": issues,
        "records": summaries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check jade VLM training JSONL contract.")
    parser.add_argument("--input", required=True, type=Path, help="VLM training JSONL path.")
    parser.add_argument("--allow-incomplete", action="store_true", help="Allow incomplete assistant attributes.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload = inspect_records(load_jsonl(args.input), require_complete=not args.allow_incomplete)
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
