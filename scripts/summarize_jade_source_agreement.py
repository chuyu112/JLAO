from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ATTRIBUTES = ("color", "water", "style", "theme")
SOURCE_CONTAINER_KEYS = ("sources", "source_attributes", "signals", "evidence", "modalities")
KNOWN_SOURCE_KEYS = ("text", "image", "vlm", "yolo", "heuristic", "vision", "ocr")


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
        for key in ("results", "items", "data", "records"):
            nested = value.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
        return [value]
    return []


def nested_dicts(record: dict[str, Any]) -> list[dict[str, Any]]:
    values = [record]
    for key in ("result", "analysis", "jade", "prediction", "attributes"):
        nested = record.get(key)
        if isinstance(nested, dict):
            values.append(nested)
    return values


def attributes_from(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    direct = {attribute: str(payload.get(attribute, "")).strip() for attribute in ATTRIBUTES if str(payload.get(attribute, "")).strip()}
    if direct:
        return direct
    nested = payload.get("attributes")
    if isinstance(nested, dict):
        return {
            attribute: str(nested.get(attribute, "")).strip()
            for attribute in ATTRIBUTES
            if str(nested.get(attribute, "")).strip()
        }
    return {}


def final_attributes(record: dict[str, Any]) -> dict[str, str]:
    for candidate in nested_dicts(record):
        attrs = attributes_from(candidate)
        if attrs:
            return attrs
    return {}


def source_blocks(record: dict[str, Any]) -> dict[str, dict[str, str]]:
    blocks: dict[str, dict[str, str]] = {}
    for candidate in nested_dicts(record):
        for source_key in KNOWN_SOURCE_KEYS:
            nested = candidate.get(source_key)
            attrs = attributes_from(nested)
            if attrs:
                blocks[source_key] = attrs
        for container_key in SOURCE_CONTAINER_KEYS:
            container = candidate.get(container_key)
            if isinstance(container, dict):
                for source_name, source_payload in container.items():
                    attrs = attributes_from(source_payload)
                    if attrs:
                        blocks[str(source_name)] = attrs
            elif isinstance(container, list):
                for index, source_payload in enumerate(container):
                    if not isinstance(source_payload, dict):
                        continue
                    source_name = str(source_payload.get("source") or source_payload.get("name") or f"{container_key}_{index}")
                    attrs = attributes_from(source_payload)
                    if attrs:
                        blocks[source_name] = attrs
    return blocks


def summarize_agreement(records: list[dict[str, Any]], *, max_examples: int = 20) -> dict[str, Any]:
    source_counts: Counter[str] = Counter()
    attribute_conflicts: Counter[str] = Counter()
    source_conflicts: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []

    for index, record in enumerate(records):
        final = final_attributes(record)
        sources = source_blocks(record)
        for source_name in sources:
            source_counts[source_name] += 1
        row_conflicts: list[dict[str, str]] = []
        for source_name, attrs in sources.items():
            for attribute, source_value in attrs.items():
                final_value = final.get(attribute, "")
                if final_value and source_value and final_value != source_value:
                    attribute_conflicts[attribute] += 1
                    source_conflicts[source_name] += 1
                    row_conflicts.append(
                        {
                            "source": source_name,
                            "attribute": attribute,
                            "source_value": source_value,
                            "final_value": final_value,
                        }
                    )
        if row_conflicts and len(examples) < max_examples:
            examples.append(
                {
                    "index": index,
                    "image_path": str(record.get("image_path") or record.get("image") or record.get("path") or ""),
                    "final": final,
                    "conflicts": row_conflicts,
                }
            )

    return {
        "row_count": len(records),
        "source_counts": dict(source_counts.most_common()),
        "attribute_conflicts": dict(attribute_conflicts.most_common()),
        "source_conflicts": dict(source_conflicts.most_common()),
        "conflict_examples": examples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize source/final agreement in jade multimodal recognition responses.")
    parser.add_argument("--response", required=True, type=Path, help="Saved API response CSV, JSON, or JSONL.")
    parser.add_argument("--max-examples", type=int, default=20, help="Maximum conflict examples to keep.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload = summarize_agreement(load_records(args.response), max_examples=args.max_examples)
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
