from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge chunked jade prediction CSV files.")
    parser.add_argument("--input", nargs="+", required=True, type=Path, help="Prediction CSV files to merge in order.")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "jade_manifest_predictions_merged.csv")
    parser.add_argument("--allow-duplicates", action="store_true", help="Keep duplicate row/image/text records.")
    args = parser.parse_args()

    output_path = resolve_path(args.output)
    fieldnames: list[str] = []
    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    skipped_duplicates = 0

    for input_path in args.input:
        path = resolve_path(input_path)
        rows, fields = read_csv(path)
        if not fieldnames:
            fieldnames = fields
        else:
            fieldnames = merge_fieldnames(fieldnames, fields)
        for row in rows:
            key = dedupe_key(row)
            if not args.allow_duplicates and key in seen:
                skipped_duplicates += 1
                continue
            seen.add(key)
            merged.append(row)

    if not fieldnames:
        raise ValueError("no prediction CSV rows found")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in merged:
            writer.writerow({field: row.get(field, "") for field in fieldnames})

    print(
        f"merged {len(merged)} rows to {output_path}; "
        f"skipped_duplicates={skipped_duplicates}"
    )
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"prediction CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def merge_fieldnames(existing: list[str], incoming: list[str]) -> list[str]:
    result = list(existing)
    for field in incoming:
        if field not in result:
            result.append(field)
    return result


def dedupe_key(row: dict[str, Any]) -> str:
    return "|".join([
        clean(row.get("row")),
        clean(row.get("image")),
        clean(row.get("text")),
    ])


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


if __name__ == "__main__":
    raise SystemExit(main())
