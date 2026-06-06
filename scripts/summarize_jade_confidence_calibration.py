from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
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


def confidence_value(record: dict[str, Any]) -> float | None:
    raw = value_from(record, ("confidence", "score", "model_confidence"))
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return max(0.0, min(1.0, value))


def bucket_label(confidence: float | None, *, bucket_size: float) -> str:
    if confidence is None:
        return "missing"
    lower = math.floor(confidence / bucket_size) * bucket_size
    upper = min(1.0, lower + bucket_size)
    return f"{lower:.2f}-{upper:.2f}"


def summarize_calibration(records: list[dict[str, Any]], *, bucket_size: float = 0.1) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "row_count": 0,
            "attribute_compared": {attribute: 0 for attribute in ATTRIBUTES},
            "attribute_correct": {attribute: 0 for attribute in ATTRIBUTES},
            "complete_compared": 0,
            "complete_correct": 0,
        }
    )
    missing_confidence = 0

    for record in records:
        confidence = confidence_value(record)
        if confidence is None:
            missing_confidence += 1
        label = bucket_label(confidence, bucket_size=bucket_size)
        bucket = buckets[label]
        bucket["row_count"] += 1

        complete_expected = True
        complete_predicted = True
        complete_correct = True
        for attribute in ATTRIBUTES:
            expected = expected_value(record, attribute)
            predicted = predicted_value(record, attribute)
            if not expected:
                complete_expected = False
                continue
            if not predicted:
                complete_predicted = False
                complete_correct = False
                bucket["attribute_compared"][attribute] += 1
                continue
            bucket["attribute_compared"][attribute] += 1
            if expected == predicted:
                bucket["attribute_correct"][attribute] += 1
            else:
                complete_correct = False

        if complete_expected and complete_predicted:
            bucket["complete_compared"] += 1
            if complete_correct:
                bucket["complete_correct"] += 1

    normalized_buckets: dict[str, Any] = {}
    for label, bucket in sorted(buckets.items()):
        attribute_accuracy = {}
        for attribute in ATTRIBUTES:
            compared = bucket["attribute_compared"][attribute]
            correct = bucket["attribute_correct"][attribute]
            attribute_accuracy[attribute] = correct / compared if compared else 0.0
        complete_compared = bucket["complete_compared"]
        complete_correct = bucket["complete_correct"]
        normalized_buckets[label] = {
            "row_count": bucket["row_count"],
            "attribute_compared": bucket["attribute_compared"],
            "attribute_correct": bucket["attribute_correct"],
            "attribute_accuracy": attribute_accuracy,
            "complete_compared": complete_compared,
            "complete_correct": complete_correct,
            "complete_accuracy": complete_correct / complete_compared if complete_compared else 0.0,
        }

    return {
        "row_count": len(records),
        "bucket_size": bucket_size,
        "missing_confidence": missing_confidence,
        "buckets": normalized_buckets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize jade prediction accuracy by confidence bucket.")
    parser.add_argument("--predictions", required=True, type=Path, help="Prediction CSV, JSON, or JSONL.")
    parser.add_argument("--bucket-size", type=float, default=0.1, help="Confidence bucket size, e.g. 0.1.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload = summarize_calibration(load_records(args.predictions), bucket_size=args.bucket_size)
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
