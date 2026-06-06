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

from app.services.jade_multimodal_service import JadeAnalysis, analyze_jade_text, merge_jade_analysis  # noqa: E402
from app.services.jade_vlm_service import parse_vlm_attributes  # noqa: E402
from app.services.jade_yolo_service import jade_attributes_from_yolo_label  # noqa: E402


ATTRIBUTES = ("color", "water", "style", "theme")
DEFAULT_EXAMPLES = ROOT / "data" / "jade_recognition_examples.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check offline jade recognition parser/fusion examples.")
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES, help="JSONL examples file.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    examples_path = resolve_path(args.examples)
    if not examples_path.exists():
        print(json.dumps({"status": "missing-examples", "examples": str(examples_path)}, ensure_ascii=False))
        return 2

    records = [check_example(record) for record in load_jsonl(examples_path)]
    failed = [record for record in records if not record["ok"]]
    payload = {
        "status": "ok" if not failed else "failed",
        "examples": str(examples_path),
        "count": len(records),
        "passed": len(records) - len(failed),
        "failed": len(failed),
        "records": records,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 1 if failed else 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            cleaned = line.strip()
            if not cleaned:
                continue
            try:
                value = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                records.append({"id": f"line-{line_number}", "source": "invalid-json", "error": str(exc)})
                continue
            if isinstance(value, dict):
                records.append(value)
    return records


def check_example(record: dict[str, Any]) -> dict[str, Any]:
    example_id = str(record.get("id") or "")
    source = str(record.get("source") or "")
    expected = normalize_attributes(record.get("expected") or {})
    if source == "invalid-json":
        return {
            "id": example_id,
            "source": source,
            "ok": False,
            "expected": expected,
            "actual": {},
            "error": str(record.get("error") or "invalid JSONL record"),
        }
    try:
        actual = recognize_example(record)
        mismatches = {
            key: {"expected": expected.get(key, ""), "actual": actual.get(key, "")}
            for key in ATTRIBUTES
            if expected.get(key, "") and actual.get(key, "") != expected.get(key, "")
        }
        return {
            "id": example_id,
            "source": source,
            "ok": not mismatches,
            "expected": expected,
            "actual": actual,
            "mismatches": mismatches,
        }
    except Exception as exc:
        return {
            "id": example_id,
            "source": source,
            "ok": False,
            "expected": expected,
            "actual": {},
            "error": str(exc),
        }


def recognize_example(record: dict[str, Any]) -> dict[str, str]:
    source = str(record.get("source") or "")
    input_payload = record.get("input") or {}
    if not isinstance(input_payload, dict):
        input_payload = {}
    if source == "text":
        return analysis_attributes(analyze_jade_text(str(input_payload.get("text") or ""), use_feedback_learning=False))
    if source == "vlm":
        return normalize_attributes(parse_vlm_attributes(str(input_payload.get("raw_text") or "")))
    if source == "yolo":
        style, theme = jade_attributes_from_yolo_label(str(input_payload.get("label") or ""))
        return normalize_attributes({"style": style, "theme": theme})
    if source == "fusion":
        text_attrs = normalize_attributes(input_payload.get("text_attributes") or {})
        raw_image_attrs = input_payload.get("image_attributes") or {}
        image_attrs = normalize_attributes(raw_image_attrs)
        yolo_label = str(
            input_payload.get("label")
            or (raw_image_attrs.get("label") if isinstance(raw_image_attrs, dict) else "")
            or ""
        )
        merged = merge_jade_analysis(
            JadeAnalysis(
                color=text_attrs.get("color", ""),
                water=text_attrs.get("water", ""),
                style=text_attrs.get("style", ""),
                theme=text_attrs.get("theme", ""),
                evidence_texts=["offline-example-text"] if any(text_attrs.values()) else [],
                signals={"attribute_sources": attribute_sources(text_attrs, "offline-text")},
            ),
            JadeAnalysis(
                color=image_attrs.get("color", ""),
                water=image_attrs.get("water", ""),
                style=image_attrs.get("style", ""),
                theme=image_attrs.get("theme", ""),
                evidence_image_paths=["offline-example-image"] if any(image_attrs.values()) else [],
                detections=[{"label": yolo_label, "confidence": 1.0}]
                if yolo_label
                else [],
                signals={"attribute_sources": attribute_sources(image_attrs, "offline-image")},
            ),
            use_feedback_learning=False,
        )
        return analysis_attributes(merged)
    return {}


def normalize_attributes(values: Any) -> dict[str, str]:
    source = values if isinstance(values, dict) else {}
    return {key: str(source.get(key) or "").strip() for key in ATTRIBUTES}


def analysis_attributes(analysis: JadeAnalysis) -> dict[str, str]:
    return {key: str(getattr(analysis, key, "") or "").strip() for key in ATTRIBUTES}


def attribute_sources(values: dict[str, str], source: str) -> dict[str, dict[str, str]]:
    return {
        key: {"source": source, "method": "offline-example", "value": value}
        for key, value in values.items()
        if key in ATTRIBUTES and value
    }


if __name__ == "__main__":
    raise SystemExit(main())
