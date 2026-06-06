from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


IDENTITY_FIELDS = ("image_path", "image", "path", "text", "title", "name")


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


def normalized_identity(record: dict[str, Any]) -> str:
    parts = []
    for field in IDENTITY_FIELDS:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip().replace("\\", "/").lower())
        elif value is not None and str(value).strip():
            parts.append(str(value).strip().replace("\\", "/").lower())
    if parts:
        return "|".join(parts)
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


def duplicate_keys(records: list[dict[str, Any]]) -> dict[str, list[int]]:
    seen: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        key = normalized_identity(record)
        seen.setdefault(key, []).append(index)
    return {key: indexes for key, indexes in seen.items() if len(indexes) > 1}


def inspect_integrity(train_records: list[dict[str, Any]], eval_records: list[dict[str, Any]]) -> dict[str, Any]:
    train_keys = {normalized_identity(record): index for index, record in enumerate(train_records)}
    eval_keys = {normalized_identity(record): index for index, record in enumerate(eval_records)}
    overlap = sorted(set(train_keys) & set(eval_keys))
    train_duplicates = duplicate_keys(train_records)
    eval_duplicates = duplicate_keys(eval_records)

    issues: list[dict[str, Any]] = []
    if overlap:
        issues.append(
            {
                "message": "train/eval overlap",
                "count": len(overlap),
                "keys": overlap[:50],
            }
        )
    if train_duplicates:
        issues.append(
            {
                "message": "duplicate train rows",
                "count": len(train_duplicates),
                "keys": list(train_duplicates)[:50],
            }
        )
    if eval_duplicates:
        issues.append(
            {
                "message": "duplicate eval rows",
                "count": len(eval_duplicates),
                "keys": list(eval_duplicates)[:50],
            }
        )

    return {
        "status": "ok" if not issues else "failed",
        "train_count": len(train_records),
        "eval_count": len(eval_records),
        "overlap_count": len(overlap),
        "train_duplicate_count": len(train_duplicates),
        "eval_duplicate_count": len(eval_duplicates),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check jade train/eval manifest split integrity.")
    parser.add_argument("--train", required=True, type=Path, help="Train CSV, JSON, or JSONL manifest.")
    parser.add_argument("--eval", required=True, type=Path, help="Eval CSV, JSON, or JSONL manifest.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload = inspect_integrity(load_records(args.train), load_records(args.eval))
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
