from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


TAXONOMY = {
    "color": {
        "帝王绿",
        "阳绿",
        "辣绿",
        "苹果绿",
        "豆绿",
        "绿色",
        "蓝水",
        "晴水",
        "油青",
        "紫罗兰",
        "春带彩",
        "白冰",
        "无色",
        "白底青",
        "飘花",
        "黄翡",
        "冰黄",
        "洒金",
        "墨翠",
        "红翡",
        "多彩",
    },
    "water": {
        "玻璃种",
        "高冰",
        "冰种",
        "冰胶",
        "起冰",
        "冰糯",
        "糯冰",
        "起胶",
        "糯化",
        "细糯",
        "糯种",
        "豆种",
    },
    "style": {
        "手镯",
        "珠串",
        "蛋面",
        "戒面",
        "戒指",
        "挂件",
        "吊坠",
        "平安扣",
        "摆件",
        "把件",
        "耳饰",
    },
    "theme": {
        "观音",
        "佛公",
        "如意",
        "叶子",
        "山水",
        "貔貅",
        "葫芦",
        "无事牌",
        "财神",
        "龙",
        "福瓜",
    },
}

ATTRIBUTE_PREFIXES = ("", "expected_", "predicted_", "corrected_", "actual_", "label_", "model_", "original_")


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


def candidate_payloads(record: dict[str, Any]) -> list[dict[str, Any]]:
    values = [record]
    for key in ("attributes", "analysis", "prediction", "corrected", "expected", "actual", "labels"):
        nested = record.get(key)
        if isinstance(nested, dict):
            values.append(nested)
    input_payload = record.get("input")
    if isinstance(input_payload, dict):
        values.append(input_payload)
    return values


def values_for(record: dict[str, Any], attribute: str) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    for payload in candidate_payloads(record):
        for prefix in ATTRIBUTE_PREFIXES:
            key = f"{prefix}{attribute}"
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                values.append((key, value.strip()))
            elif value is not None and not isinstance(value, (dict, list, tuple)) and str(value).strip():
                values.append((key, str(value).strip()))
    return values


def inspect_values(records: list[dict[str, Any]], *, allow_empty: bool = True) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    counts = {attribute: {} for attribute in TAXONOMY}

    for index, record in enumerate(records):
        for attribute, allowed in TAXONOMY.items():
            pairs = values_for(record, attribute)
            if not pairs and not allow_empty:
                issues.append({"index": index, "attribute": attribute, "message": "missing taxonomy value"})
                continue
            for key, value in pairs:
                counts[attribute][value] = counts[attribute].get(value, 0) + 1
                if value not in allowed:
                    issues.append(
                        {
                            "index": index,
                            "attribute": attribute,
                            "field": key,
                            "value": value,
                            "message": "value outside jade taxonomy",
                        }
                    )

    return {
        "status": "ok" if not issues else "failed",
        "row_count": len(records),
        "allow_empty": allow_empty,
        "counts": counts,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check jade color/water/style/theme values against the canonical taxonomy.")
    parser.add_argument("--input", required=True, type=Path, help="CSV, JSON, or JSONL manifest/prediction/feedback file.")
    parser.add_argument("--require-present", action="store_true", help="Fail when a row has no value for an attribute.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload = inspect_values(load_records(args.input), allow_empty=not args.require_present)
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
