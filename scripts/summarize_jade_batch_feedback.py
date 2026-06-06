from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_batch_feedback_summary_service import ATTRIBUTES, summarize_jade_batch_feedback  # noqa: E402
from app.services.jade_batch_trace_service import feedback_record_matches_batch  # noqa: E402
from app.services.jade_training_service import DEFAULT_FEEDBACK_PATH, read_feedback_records  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize saved jade feedback records for a recognition batch ID.")
    parser.add_argument("--batch-id", required=True, help="Recognition batch ID to query.")
    parser.add_argument("--feedback", type=Path, default=DEFAULT_FEEDBACK_PATH)
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    batch_id = args.batch_id.strip()
    if not batch_id:
        print("--batch-id is required", file=sys.stderr)
        return 2

    feedback_path = resolve_path(args.feedback)
    records = read_feedback_records(feedback_path)
    matched = [record for record in records if feedback_record_matches_batch(record, batch_id)]
    payload = summarize(batch_id=batch_id, feedback_path=feedback_path, records=matched)
    output_text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output_path = resolve_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text + "\n", encoding="utf-8")
    print(output_text)
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def summarize(*, batch_id: str, feedback_path: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    summary = summarize_jade_batch_feedback(records)
    items = []
    for record in records:
        corrected = as_dict(record.get("corrected"))
        training = as_dict(record.get("training"))
        items.append(
            {
                "id": clean(record.get("id")),
                "created_at": clean(record.get("created_at")),
                "source": clean(record.get("source")) or "unknown",
                "corrected": {key: clean(corrected.get(key)) for key in ATTRIBUTES},
                "confidence": to_float(record.get("confidence")),
                "training": training,
            }
        )
    return {
        "status": "ok",
        "batch_id": batch_id,
        "feedback_path": str(feedback_path),
        "count": len(records),
        **summary,
        "records": items,
    }


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
