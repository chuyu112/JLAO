from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEEDBACK = ROOT / "data" / "jade_feedback.jsonl"
ATTRIBUTES = ("color", "water", "style", "theme")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check jade feedback JSONL readiness for review/training loop.")
    parser.add_argument("--feedback", type=Path, default=DEFAULT_FEEDBACK, help="Feedback JSONL path.")
    parser.add_argument("--batch-id", default="", help="Optional batch_id filter.")
    parser.add_argument("--min-records", type=int, default=1, help="Minimum matching records required.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    feedback_path = resolve_path(args.feedback)
    if not feedback_path.exists():
        print_json({"status": "missing-feedback", "feedback": str(feedback_path)}, pretty=args.pretty)
        return 2

    records = load_jsonl(feedback_path)
    if args.batch_id:
        records = [record for record in records if feedback_batch_id(record) == args.batch_id]
    row_results = [inspect_record(index, record) for index, record in enumerate(records, start=1)]
    complete_rows = [row for row in row_results if not row["missing_corrected_attributes"]]
    yolo_ready_rows = [row for row in row_results if row["has_box"] and row["has_image"]]
    missing_batch_rows = [row for row in row_results if not row["batch_id"]]
    blocking_reasons: list[str] = []
    if len(row_results) < args.min_records:
        blocking_reasons.append("too-few-records")
    if not complete_rows:
        blocking_reasons.append("no-complete-corrected-attribute-records")
    if missing_batch_rows:
        blocking_reasons.append("rows-missing-batch-id")

    payload = {
        "status": "ready" if not blocking_reasons else "blocked",
        "feedback": str(feedback_path),
        "batch_id": args.batch_id,
        "count": len(row_results),
        "complete_attribute_rows": len(complete_rows),
        "yolo_ready_rows": len(yolo_ready_rows),
        "missing_batch_rows": len(missing_batch_rows),
        "required_attributes": list(ATTRIBUTES),
        "blocking_reasons": blocking_reasons,
        "rows": row_results,
    }
    print_json(payload, pretty=args.pretty)
    return 0 if not blocking_reasons else 1


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            cleaned = line.strip()
            if not cleaned:
                continue
            try:
                value = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                rows.append({"_line": line_number, "_error": str(exc)})
                continue
            if isinstance(value, dict):
                rows.append(value)
    return rows


def inspect_record(index: int, record: dict[str, Any]) -> dict[str, Any]:
    corrected = corrected_attributes(record)
    prediction = predicted_attributes(record)
    input_payload = record.get("input") if isinstance(record.get("input"), dict) else {}
    box = record.get("box") if isinstance(record.get("box"), dict) else record.get("bbox")
    missing_corrected = [key for key in ATTRIBUTES if not corrected.get(key)]
    return {
        "row": index,
        "batch_id": feedback_batch_id(record),
        "has_image": bool(clean(input_payload.get("image") or record.get("image"))),
        "has_text": bool(clean(input_payload.get("text") or record.get("text"))),
        "has_box": bool(box),
        "corrected": corrected,
        "prediction": prediction,
        "missing_corrected_attributes": missing_corrected,
        "error": clean(record.get("_error")),
    }


def corrected_attributes(record: dict[str, Any]) -> dict[str, str]:
    payload = first_dict(record, ("corrected", "corrected_attributes", "expected", "actual"))
    return {
        key: first_value(payload, (key, f"corrected_{key}", f"expected_{key}", f"actual_{key}"))
        or first_value(record, (f"corrected_{key}", f"expected_{key}", f"actual_{key}"))
        for key in ATTRIBUTES
    }


def predicted_attributes(record: dict[str, Any]) -> dict[str, str]:
    payload = first_dict(record, ("prediction", "predicted", "analysis"))
    return {
        key: first_value(payload, (key, f"predicted_{key}"))
        or first_value(record, (f"predicted_{key}",))
        for key in ATTRIBUTES
    }


def feedback_batch_id(record: dict[str, Any]) -> str:
    input_payload = record.get("input") if isinstance(record.get("input"), dict) else {}
    batch_id = clean(record.get("batch_id") or input_payload.get("batch_id"))
    if batch_id:
        return batch_id
    evidence_texts = record.get("evidence_texts")
    if isinstance(evidence_texts, list):
        for item in evidence_texts:
            text = clean(item)
            if text.startswith("batch_id="):
                return text.split("=", 1)[1].strip()
    return ""


def first_dict(record: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    for key in keys:
        value = record.get(key)
        if isinstance(value, dict):
            return value
    return record


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
