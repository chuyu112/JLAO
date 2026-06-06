from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_ATTRIBUTES = ("color", "water", "style", "theme")
REQUIRED_RESULT_FIELDS = ("confidence", "signals", "review_flags")


def load_response(path: Path) -> Any:
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


def analysis_payload(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    candidates: list[Any] = [record]
    for key in ("analysis", "result", "attributes", "jade", "prediction"):
        nested = record.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if any(key in candidate for key in REQUIRED_ATTRIBUTES):
            return candidate
        nested_attributes = candidate.get("attributes")
        if isinstance(nested_attributes, dict) and any(key in nested_attributes for key in REQUIRED_ATTRIBUTES):
            return nested_attributes
    return candidates[-1] if isinstance(candidates[-1], dict) else {}


def result_field_payload(record: Any, analysis: dict[str, Any]) -> dict[str, Any]:
    candidates: list[Any] = [record, analysis]
    if isinstance(record, dict):
        for key in ("result", "analysis", "attributes", "jade", "prediction"):
            nested = record.get(key)
            if isinstance(nested, dict):
                candidates.append(nested)
    for candidate in candidates:
        if isinstance(candidate, dict) and any(key in candidate for key in REQUIRED_RESULT_FIELDS):
            return candidate
    return record if isinstance(record, dict) else {}


def _has_value(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def inspect_response(payload: Any, *, require_all_attributes: bool = False) -> dict[str, Any]:
    records = response_records(payload)
    issues: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    if not records:
        issues.append({"scope": "response", "message": "response does not contain a recognizer result list"})

    for index, record in enumerate(records):
        analysis = analysis_payload(record)
        result_fields = result_field_payload(record, analysis)
        missing_fields = [key for key in REQUIRED_RESULT_FIELDS if key not in result_fields]

        missing_attributes = [key for key in REQUIRED_ATTRIBUTES if key not in analysis]
        empty_attributes = [key for key in REQUIRED_ATTRIBUTES if key in analysis and not _has_value(analysis, key)]

        if missing_fields:
            issues.append({"scope": f"result[{index}]", "message": "missing result fields", "fields": missing_fields})
        if missing_attributes:
            issues.append({"scope": f"result[{index}]", "message": "missing attribute keys", "fields": missing_attributes})
        if require_all_attributes and empty_attributes:
            issues.append({"scope": f"result[{index}]", "message": "empty required attributes", "fields": empty_attributes})

        confidence = None
        if isinstance(result_fields, dict):
            confidence = result_fields.get("confidence")
        if confidence is not None and not isinstance(confidence, (int, float)):
            issues.append({"scope": f"result[{index}]", "message": "confidence must be numeric"})

        summaries.append(
            {
                "index": index,
                "attributes": {key: analysis.get(key) for key in REQUIRED_ATTRIBUTES},
                "has_confidence": confidence is not None,
                "has_signals": isinstance(result_fields, dict) and "signals" in result_fields,
                "has_review_flags": isinstance(result_fields, dict) and "review_flags" in result_fields,
            }
        )

    return {
        "status": "ok" if not issues else "failed",
        "count": len(records),
        "require_all_attributes": require_all_attributes,
        "issues": issues,
        "results": summaries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check saved jade batch API JSON response contract.")
    parser.add_argument("--response", required=True, type=Path, help="Saved JSON response from jade batch recognition API.")
    parser.add_argument("--require-all-attributes", action="store_true", help="Fail when color/water/style/theme are empty.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload = inspect_response(load_response(args.response), require_all_attributes=args.require_all_attributes)
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
