from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ATTRIBUTES = ("color", "water", "style", "theme")


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


def split_flags(value: str) -> list[str]:
    return [item.strip() for item in value.replace("；", ";").replace(",", ";").split(";") if item.strip()]


def corrected_attributes(record: dict[str, Any]) -> dict[str, str]:
    return {
        attribute: value_from(record, (f"corrected_{attribute}", f"actual_{attribute}", f"expected_{attribute}", attribute))
        for attribute in ATTRIBUTES
    }


def predicted_attributes(record: dict[str, Any]) -> dict[str, str]:
    return {
        attribute: value_from(record, (f"predicted_{attribute}", f"original_{attribute}", f"model_{attribute}"))
        for attribute in ATTRIBUTES
    }


def feedback_record(record: dict[str, Any], *, source: str = "review_queue") -> dict[str, Any]:
    batch_id = value_from(record, ("batch_id",))
    review_reasons = split_flags(value_from(record, ("review_reasons",)))
    review_flags = split_flags(value_from(record, ("review_flags",)))
    evidence_texts = [f"source={source}"]
    if batch_id:
        evidence_texts.append(f"batch_id={batch_id}")
    if review_reasons:
        evidence_texts.append("review_reasons=" + ";".join(review_reasons))
    return {
        "input": {
            "image_path": value_from(record, ("image_path", "image", "path")),
            "text": value_from(record, ("text", "context_text", "description", "title", "name")),
            "batch_id": batch_id,
        },
        "prediction": predicted_attributes(record),
        "corrected": corrected_attributes(record),
        "review": {
            "index": value_from(record, ("index",)),
            "reasons": review_reasons,
            "flags": review_flags,
            "notes": value_from(record, ("notes", "review_note")),
        },
        "evidence_texts": evidence_texts,
    }


def convert_records(
    records: list[dict[str, Any]],
    *,
    require_complete: bool = False,
    source: str = "review_queue",
) -> dict[str, Any]:
    converted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        feedback = feedback_record(record, source=source)
        missing = [attribute for attribute in ATTRIBUTES if not feedback["corrected"].get(attribute)]
        if missing and require_complete:
            skipped.append({"index": index, "missing": missing})
            continue
        converted.append(feedback)
    return {"records": converted, "skipped": skipped}


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert reviewed jade queue rows into feedback JSONL.")
    parser.add_argument("--review-queue", required=True, type=Path, help="Reviewed CSV, JSON, or JSONL queue.")
    parser.add_argument("--output", required=True, type=Path, help="Output feedback JSONL path.")
    parser.add_argument("--require-complete", action="store_true", help="Skip rows missing any corrected attribute.")
    parser.add_argument("--source", default="review_queue", help="Source label written to evidence_texts.")
    parser.add_argument("--pretty-summary", action="store_true", help="Pretty-print JSON conversion summary.")
    args = parser.parse_args()

    result = convert_records(load_records(args.review_queue), require_complete=args.require_complete, source=args.source)
    write_jsonl(args.output, result["records"])
    summary = {"written": len(result["records"]), "skipped": result["skipped"], "output": str(args.output)}
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty_summary else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
