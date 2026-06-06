from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ATTRIBUTES = ("color", "water", "style", "theme")


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


def expected_value(record: dict[str, Any], attribute: str) -> str:
    return value_from(record, (f"expected_{attribute}", f"corrected_{attribute}", f"actual_{attribute}", f"label_{attribute}"))


def predicted_value(record: dict[str, Any], attribute: str) -> str:
    return value_from(record, (f"predicted_{attribute}", attribute, f"model_{attribute}"))


def row_identity(record: dict[str, Any]) -> str:
    return value_from(record, ("image_path", "image", "path", "sku", "id", "name", "title"))


def summarize_errors(records: list[dict[str, Any]], *, max_examples: int = 20) -> dict[str, Any]:
    per_attribute: dict[str, Any] = {}
    all_errors: list[dict[str, Any]] = []

    for attribute in ATTRIBUTES:
        confusion: Counter[tuple[str, str]] = Counter()
        missing_expected = 0
        missing_predicted = 0
        correct = 0
        compared = 0
        examples: list[dict[str, Any]] = []

        for index, record in enumerate(records):
            expected = expected_value(record, attribute)
            predicted = predicted_value(record, attribute)
            if not expected:
                missing_expected += 1
                continue
            if not predicted:
                missing_predicted += 1
                confusion[(expected, "")] += 1
                compared += 1
                error = {
                    "index": index,
                    "identity": row_identity(record),
                    "attribute": attribute,
                    "expected": expected,
                    "predicted": "",
                }
                all_errors.append(error)
                if len(examples) < max_examples:
                    examples.append(error)
                continue
            compared += 1
            if expected == predicted:
                correct += 1
                continue
            confusion[(expected, predicted)] += 1
            error = {
                "index": index,
                "identity": row_identity(record),
                "attribute": attribute,
                "expected": expected,
                "predicted": predicted,
            }
            all_errors.append(error)
            if len(examples) < max_examples:
                examples.append(error)

        per_attribute[attribute] = {
            "compared": compared,
            "correct": correct,
            "error_count": compared - correct,
            "accuracy": (correct / compared) if compared else 0.0,
            "missing_expected": missing_expected,
            "missing_predicted": missing_predicted,
            "confusions": [
                {"expected": expected, "predicted": predicted, "count": count}
                for (expected, predicted), count in confusion.most_common()
            ],
            "examples": examples,
        }

    return {
        "row_count": len(records),
        "attributes": per_attribute,
        "total_errors": len(all_errors),
        "error_examples": all_errors[:max_examples],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize jade prediction errors by color/water/style/theme.")
    parser.add_argument("--predictions", required=True, type=Path, help="Prediction CSV, JSON, or JSONL.")
    parser.add_argument("--max-examples", type=int, default=20, help="Maximum examples retained per report section.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload = summarize_errors(load_records(args.predictions), max_examples=args.max_examples)
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
