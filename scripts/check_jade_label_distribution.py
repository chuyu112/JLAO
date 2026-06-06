from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ATTRIBUTES = ("color", "water", "style", "theme")
ALIASES = {
    "color": ("color", "expected_color", "corrected_color", "actual_color", "label_color"),
    "water": ("water", "expected_water", "corrected_water", "actual_water", "label_water"),
    "style": ("style", "expected_style", "corrected_style", "actual_style", "label_style"),
    "theme": ("theme", "expected_theme", "corrected_theme", "actual_theme", "label_theme"),
}


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
                if stripped:
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


def pick_label(record: dict[str, Any], attribute: str) -> str:
    candidates: list[Any] = [record]
    for key in ("labels", "expected", "corrected", "actual", "attributes"):
        nested = record.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for key in ALIASES[attribute]:
            value = candidate.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if value is not None and not isinstance(value, (dict, list, tuple)):
                return str(value).strip()
    return ""


def inspect_distribution(
    records: list[dict[str, Any]],
    *,
    min_labeled: int = 1,
    min_distinct_per_attribute: int = 1,
) -> dict[str, Any]:
    distributions: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, Any]] = []

    for attribute in ATTRIBUTES:
        counter = Counter(pick_label(record, attribute) for record in records)
        counter.pop("", None)
        labeled_count = sum(counter.values())
        distinct_count = len(counter)
        distributions[attribute] = {
            "labeled_count": labeled_count,
            "distinct_count": distinct_count,
            "values": dict(counter.most_common()),
        }
        if labeled_count < min_labeled:
            issues.append(
                {
                    "attribute": attribute,
                    "message": "not enough labeled rows",
                    "required": min_labeled,
                    "actual": labeled_count,
                }
            )
        if distinct_count < min_distinct_per_attribute:
            issues.append(
                {
                    "attribute": attribute,
                    "message": "not enough distinct labels",
                    "required": min_distinct_per_attribute,
                    "actual": distinct_count,
                }
            )

    complete_rows = sum(1 for record in records if all(pick_label(record, attribute) for attribute in ATTRIBUTES))
    return {
        "status": "ok" if not issues else "failed",
        "row_count": len(records),
        "complete_rows": complete_rows,
        "min_labeled": min_labeled,
        "min_distinct_per_attribute": min_distinct_per_attribute,
        "distributions": distributions,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check labeled jade manifest distribution for color/water/style/theme.")
    parser.add_argument("--manifest", required=True, type=Path, help="CSV, JSON, or JSONL labeled manifest.")
    parser.add_argument("--min-labeled", type=int, default=1, help="Minimum labeled rows required for each attribute.")
    parser.add_argument(
        "--min-distinct-per-attribute",
        type=int,
        default=1,
        help="Minimum distinct label values required for each attribute.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload = inspect_distribution(
        load_records(args.manifest),
        min_labeled=args.min_labeled,
        min_distinct_per_attribute=args.min_distinct_per_attribute,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
