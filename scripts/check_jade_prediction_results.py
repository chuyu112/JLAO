from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTES = ("color", "water", "style", "theme")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check jade prediction CSV coverage and optional accuracy.")
    parser.add_argument("--predictions", required=True, type=Path, help="Prediction CSV path.")
    parser.add_argument("--min-coverage", type=float, default=0.80, help="Minimum non-empty prediction coverage per attribute.")
    parser.add_argument("--min-accuracy", type=float, default=0.0, help="Minimum exact-match accuracy per attribute when expected labels exist.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    predictions_path = resolve_path(args.predictions)
    if not predictions_path.exists():
        print_json({"status": "missing-predictions", "predictions": str(predictions_path)}, pretty=args.pretty)
        return 2

    rows = load_rows(predictions_path)
    summary = summarize(rows)
    blocking_reasons: list[str] = []
    if not rows:
        blocking_reasons.append("empty-predictions")
    for key, item in summary["attributes"].items():
        if item["coverage"] < args.min_coverage:
            blocking_reasons.append(f"low-{key}-coverage")
        if item["expected_count"] > 0 and item["accuracy"] < args.min_accuracy:
            blocking_reasons.append(f"low-{key}-accuracy")

    payload = {
        "status": "passed" if not blocking_reasons else "blocked",
        "predictions": str(predictions_path),
        "min_coverage": args.min_coverage,
        "min_accuracy": args.min_accuracy,
        "blocking_reasons": blocking_reasons,
        **summary,
    }
    print_json(payload, pretty=args.pretty)
    return 0 if not blocking_reasons else 1


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    attributes = {key: summarize_attribute(rows, key) for key in ATTRIBUTES}
    complete_predictions = 0
    complete_expected = 0
    for row in rows:
        if all(predicted_value(row, key) for key in ATTRIBUTES):
            complete_predictions += 1
        if all(expected_value(row, key) for key in ATTRIBUTES):
            complete_expected += 1
    return {
        "count": len(rows),
        "complete_prediction_rows": complete_predictions,
        "complete_expected_rows": complete_expected,
        "attributes": attributes,
    }


def summarize_attribute(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    predicted_count = 0
    expected_count = 0
    correct_count = 0
    mismatches: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        predicted = predicted_value(row, key)
        expected = expected_value(row, key)
        if predicted:
            predicted_count += 1
        if expected:
            expected_count += 1
            if predicted == expected:
                correct_count += 1
            elif len(mismatches) < 20:
                mismatches.append({"row": str(index), "expected": expected, "predicted": predicted})
    total = max(1, len(rows))
    return {
        "predicted_count": predicted_count,
        "expected_count": expected_count,
        "correct_count": correct_count,
        "coverage": round(predicted_count / total, 4),
        "accuracy": round(correct_count / expected_count, 4) if expected_count else 0.0,
        "mismatches": mismatches,
    }


def predicted_value(row: dict[str, Any], key: str) -> str:
    return first_value(row, (f"predicted_{key}", key, f"actual_{key}"))


def expected_value(row: dict[str, Any], key: str) -> str:
    return first_value(row, (f"expected_{key}", f"corrected_{key}", f"label_{key}"))


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
