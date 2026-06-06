from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ATTRIBUTES = ("color", "water", "style", "theme")
FIELDNAMES = [
    "index",
    "image_path",
    "text",
    "color",
    "water",
    "style",
    "theme",
    "confidence",
    "review_reasons",
    "review_flags",
    "batch_id",
]


def load_payload(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def response_records(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("results", "items", "data", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return [payload]


def nested_dicts(record: Any) -> list[dict[str, Any]]:
    if not isinstance(record, dict):
        return []
    values: list[dict[str, Any]] = [record]
    for key in ("result", "analysis", "attributes", "jade", "prediction", "input"):
        nested = record.get(key)
        if isinstance(nested, dict):
            values.append(nested)
    return values


def first_value(record: Any, keys: tuple[str, ...], *, default: Any = "") -> Any:
    for candidate in nested_dicts(record):
        for key in keys:
            value = candidate.get(key)
            if value not in (None, ""):
                return value
    return default


def analysis_payload(record: Any) -> dict[str, Any]:
    for candidate in nested_dicts(record):
        if any(attribute in candidate for attribute in ATTRIBUTES):
            return candidate
        nested = candidate.get("attributes")
        if isinstance(nested, dict) and any(attribute in nested for attribute in ATTRIBUTES):
            return nested
    return {}


def normalize_flags(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.replace("；", ";").replace(",", ";").split(";") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [str(key) for key, enabled in value.items() if enabled]
    return [str(value)]


def review_reasons(record: Any, *, min_confidence: float) -> list[str]:
    analysis = analysis_payload(record)
    reasons: list[str] = []
    missing = [attribute for attribute in ATTRIBUTES if not str(analysis.get(attribute, "")).strip()]
    if missing:
        reasons.append("missing_" + ",".join(missing))

    confidence = first_value(record, ("confidence",), default=None)
    if isinstance(confidence, str):
        try:
            confidence = float(confidence)
        except ValueError:
            reasons.append("invalid_confidence")
            confidence = None
    if isinstance(confidence, (int, float)) and confidence < min_confidence:
        reasons.append("low_confidence")

    flags = normalize_flags(first_value(record, ("review_flags",), default=[]))
    if flags:
        reasons.append("review_flags")
    return reasons


def queue_rows(records: list[Any], *, min_confidence: float = 0.65, include_all: bool = False) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, record in enumerate(records):
        analysis = analysis_payload(record)
        reasons = review_reasons(record, min_confidence=min_confidence)
        if not include_all and not reasons:
            continue
        flags = normalize_flags(first_value(record, ("review_flags",), default=[]))
        confidence = first_value(record, ("confidence",), default="")
        rows.append(
            {
                "index": str(index),
                "image_path": str(first_value(record, ("image_path", "image", "path"), default="")),
                "text": str(first_value(record, ("text", "context_text", "description", "title", "name"), default="")),
                "color": str(analysis.get("color", "") or ""),
                "water": str(analysis.get("water", "") or ""),
                "style": str(analysis.get("style", "") or ""),
                "theme": str(analysis.get("theme", "") or ""),
                "confidence": str(confidence if confidence is not None else ""),
                "review_reasons": ";".join(reasons),
                "review_flags": ";".join(flags),
                "batch_id": str(first_value(record, ("batch_id",), default="")),
            }
        )
    return rows


def write_queue(output: Path, rows: list[dict[str, str]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a jade human-review queue CSV from saved batch API response JSON.")
    parser.add_argument("--response", required=True, type=Path, help="Saved JSON response from jade batch recognition API.")
    parser.add_argument("--output", required=True, type=Path, help="Output review queue CSV path.")
    parser.add_argument("--min-confidence", type=float, default=0.65, help="Rows below this confidence are queued.")
    parser.add_argument("--include-all", action="store_true", help="Include all rows, even without review reasons.")
    args = parser.parse_args()

    rows = queue_rows(response_records(load_payload(args.response)), min_confidence=args.min_confidence, include_all=args.include_all)
    write_queue(args.output, rows)
    print(f"wrote {len(rows)} jade review rows to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
