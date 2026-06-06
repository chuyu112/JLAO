from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ATTRIBUTES = ("color", "water", "style", "theme")
FIELDNAMES = [
    "index",
    "image_path",
    "text",
    "predicted_color",
    "predicted_water",
    "predicted_style",
    "predicted_theme",
    "color",
    "water",
    "style",
    "theme",
    "error_attributes",
    "review_reasons",
    "batch_id",
]


def load_records(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    if suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                value = json.loads(stripped)
                if isinstance(value, dict):
                    rows.append(value)
        return rows
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


def expected_value(record: dict[str, Any], attribute: str) -> str:
    return value_from(record, (f"expected_{attribute}", f"corrected_{attribute}", f"actual_{attribute}", f"label_{attribute}"))


def predicted_value(record: dict[str, Any], attribute: str) -> str:
    return value_from(record, (f"predicted_{attribute}", attribute, f"model_{attribute}"))


def error_attributes(record: dict[str, Any], *, include_missing_expected: bool = False) -> list[str]:
    errors: list[str] = []
    for attribute in ATTRIBUTES:
        expected = expected_value(record, attribute)
        predicted = predicted_value(record, attribute)
        if not expected and not include_missing_expected:
            continue
        if expected != predicted:
            errors.append(attribute)
    return errors


def queue_rows(records: list[dict[str, Any]], *, include_missing_expected: bool = False) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, record in enumerate(records):
        errors = error_attributes(record, include_missing_expected=include_missing_expected)
        if not errors:
            continue
        row = {
            "index": str(index),
            "image_path": value_from(record, ("image_path", "image", "path")),
            "text": value_from(record, ("text", "context_text", "description", "title", "name")),
            "predicted_color": predicted_value(record, "color"),
            "predicted_water": predicted_value(record, "water"),
            "predicted_style": predicted_value(record, "style"),
            "predicted_theme": predicted_value(record, "theme"),
            "color": expected_value(record, "color"),
            "water": expected_value(record, "water"),
            "style": expected_value(record, "style"),
            "theme": expected_value(record, "theme"),
            "error_attributes": ";".join(errors),
            "review_reasons": "prediction_mismatch",
            "batch_id": value_from(record, ("batch_id",)),
        }
        rows.append(row)
    return rows


def write_queue(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create jade review queue CSV from prediction mismatches.")
    parser.add_argument("--predictions", required=True, type=Path, help="Prediction CSV, JSON, or JSONL.")
    parser.add_argument("--output", required=True, type=Path, help="Output review queue CSV.")
    parser.add_argument("--include-missing-expected", action="store_true", help="Queue rows missing expected labels.")
    args = parser.parse_args()

    rows = queue_rows(load_records(args.predictions), include_missing_expected=args.include_missing_expected)
    write_queue(args.output, rows)
    print(f"wrote {len(rows)} jade prediction-error review rows to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
