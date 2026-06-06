from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ATTRIBUTES = ("color", "water", "style", "theme")
KEY_FIELDS = ("image_path", "image", "path", "text", "title", "name")


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


def record_key(record: dict[str, Any]) -> str:
    parts = [str(record.get(key, "")).strip() for key in KEY_FIELDS if str(record.get(key, "")).strip()]
    if parts:
        return "|".join(parts)
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


def has_complete_labels(record: dict[str, Any]) -> bool:
    return all(str(record.get(attribute, "")).strip() for attribute in ATTRIBUTES)


def split_records(
    records: list[dict[str, Any]],
    *,
    eval_ratio: float = 0.2,
    salt: str = "jade-v1",
    require_complete: bool = False,
) -> dict[str, Any]:
    train: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for index, record in enumerate(records):
        if require_complete and not has_complete_labels(record):
            skipped.append({"index": index, "reason": "incomplete_labels"})
            continue
        digest = hashlib.sha256(f"{salt}|{record_key(record)}".encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF
        row = dict(record)
        row["split"] = "eval" if bucket < eval_ratio else "train"
        if row["split"] == "eval":
            eval_rows.append(row)
        else:
            train.append(row)

    return {
        "train": train,
        "eval": eval_rows,
        "skipped": skipped,
        "summary": {
            "input_count": len(records),
            "train_count": len(train),
            "eval_count": len(eval_rows),
            "skipped_count": len(skipped),
            "eval_ratio": eval_ratio,
            "salt": salt,
            "require_complete": require_complete,
        },
    }


def fieldnames_for(records: list[dict[str, Any]]) -> list[str]:
    fieldnames: list[str] = []
    for record in records:
        for key in record:
            if key not in fieldnames:
                fieldnames.append(key)
    if "split" not in fieldnames:
        fieldnames.append("split")
    return fieldnames


def write_csv(path: Path, records: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def main() -> int:
    parser = argparse.ArgumentParser(description="Split labeled jade manifest into stable train/eval CSV files.")
    parser.add_argument("--manifest", required=True, type=Path, help="CSV, JSON, or JSONL labeled manifest.")
    parser.add_argument("--train-output", required=True, type=Path, help="Output train CSV path.")
    parser.add_argument("--eval-output", required=True, type=Path, help="Output eval CSV path.")
    parser.add_argument("--eval-ratio", type=float, default=0.2, help="Stable hash ratio assigned to eval.")
    parser.add_argument("--salt", default="jade-v1", help="Stable split salt.")
    parser.add_argument("--require-complete", action="store_true", help="Skip rows missing color/water/style/theme.")
    parser.add_argument("--pretty-summary", action="store_true", help="Pretty-print JSON summary.")
    args = parser.parse_args()

    result = split_records(
        load_records(args.manifest),
        eval_ratio=args.eval_ratio,
        salt=args.salt,
        require_complete=args.require_complete,
    )
    fieldnames = fieldnames_for(result["train"] + result["eval"])
    write_csv(args.train_output, result["train"], fieldnames)
    write_csv(args.eval_output, result["eval"], fieldnames)
    print(json.dumps(result["summary"] | {"skipped": result["skipped"]}, ensure_ascii=False, indent=2 if args.pretty_summary else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
