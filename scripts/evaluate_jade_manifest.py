from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_multimodal_service import (  # noqa: E402
    JADE_COLORS,
    JADE_STYLES,
    JADE_THEMES,
    JADE_WATERS,
    analyze_jade_image,
    analyze_jade_text,
    merge_jade_analysis,
)
from app.services.jade_yolo_service import get_yolo_runtime_status  # noqa: E402


ATTRIBUTE_KEYS = ["color", "water", "style", "theme"]
EVALUATION_MODES = ["image", "text", "fused"]
ATTRIBUTE_CATALOGS = {
    "color": JADE_COLORS,
    "water": JADE_WATERS,
    "style": JADE_STYLES,
    "theme": JADE_THEMES,
}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate jade multimodal recognition against a CSV, JSON, or JSONL manifest."
    )
    parser.add_argument("--manifest", required=True, type=Path, help="Manifest with image/text/color/water/style/theme fields.")
    parser.add_argument("--limit", type=int, default=0, help="Evaluate at most N rows.")
    parser.add_argument("--mode", choices=["image", "text", "fused", "all"], default="fused")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON report output path.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument("--include-rows", action="store_true", help="Include per-row prediction details.")
    args = parser.parse_args()

    manifest = resolve_path(args.manifest)
    if not manifest.exists():
        print(f"manifest not found: {manifest}", file=sys.stderr)
        return 2

    rows = load_manifest_rows(manifest)
    if args.limit > 0:
        rows = rows[: args.limit]

    modes = EVALUATION_MODES if args.mode == "all" else [args.mode]
    summaries = {mode: new_summary() for mode in modes}
    details: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        result = evaluate_row(row, manifest.parent, index, modes)
        for mode in modes:
            update_summary(summaries[mode], result["modes"][mode])
        if args.include_rows:
            details.append(result)

    payload: dict[str, Any] = {
        "status": "ok",
        "manifest": str(manifest),
        "rows": len(rows),
        "runtime": {
            "yolo": get_yolo_runtime_status(),
        },
        "mode": args.mode,
        "metrics": {
            mode: finalize_summary(summary)
            for mode, summary in summaries.items()
        },
    }
    if args.include_rows:
        payload["results"] = details

    output_text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output is not None:
        output_path = resolve_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_text)
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_manifest_rows(manifest: Path) -> list[dict[str, Any]]:
    suffix = manifest.suffix.lower()
    if suffix == ".csv":
        with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        with manifest.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                text = line.strip()
                if text:
                    rows.append(json.loads(text))
        return rows
    with manifest.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        samples = payload.get("samples") or payload.get("records") or []
        return samples if isinstance(samples, list) else []
    return payload if isinstance(payload, list) else []


def evaluate_row(row: dict[str, Any], base_dir: Path, index: int, modes: list[str]) -> dict[str, Any]:
    raw_expected = {key: clean(row.get(key)) for key in ATTRIBUTE_KEYS}
    expected = {key: canonical_attribute(key, raw_expected[key]) for key in ATTRIBUTE_KEYS}
    image_path = resolve_row_image(row, base_dir)
    text = clean(row.get("text") or row.get("notes") or row.get("description"))

    analyses = []
    errors: list[str] = []
    if image_path:
        if image_path.exists():
            image_analysis = analyze_jade_image(image_path, context_text=text)
            analyses.append(image_analysis)
        else:
            errors.append(f"image not found: {image_path}")
    if text:
        text_analysis = analyze_jade_text(text)
        analyses.append(text_analysis)

    mode_results: dict[str, dict[str, Any]] = {}
    for mode in modes:
        if mode == "image":
            analysis = image_analysis if image_path and image_path.exists() else None
        elif mode == "text":
            analysis = text_analysis if text else None
        else:
            analysis = merge_jade_analysis(*analyses) if len(analyses) > 1 else analyses[0] if analyses else None
        mode_results[mode] = result_for_analysis(analysis, expected)
    if not analyses and not errors:
        errors.append("row has no image or text")

    return {
        "index": index,
        "image": str(image_path) if image_path else "",
        "expected": expected,
        "raw_expected": raw_expected,
        "modes": mode_results,
        "errors": errors,
    }


def result_for_analysis(analysis: Any | None, expected: dict[str, str]) -> dict[str, Any]:
    if analysis is None:
        predicted = {key: "" for key in ATTRIBUTE_KEYS}
        confidence = 0.0
        signals = {}
    else:
        predicted = {
            "color": analysis.color,
            "water": analysis.water,
            "style": analysis.style,
            "theme": analysis.theme,
        }
        confidence = analysis.confidence
        signals = analysis.signals
    matches = {
        key: bool(expected[key]) and normalize(expected[key]) == normalize(predicted.get(key, ""))
        for key in ATTRIBUTE_KEYS
    }
    return {
        "expected_context": expected,
        "predicted": predicted,
        "matches": matches,
        "confidence": confidence,
        "signals": signals,
    }


def resolve_row_image(row: dict[str, Any], base_dir: Path) -> Path | None:
    raw = clean(row.get("image") or row.get("path") or row.get("filename") or row.get("file"))
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else (base_dir / path).resolve()


def new_summary() -> dict[str, dict[str, int]]:
    return {
        key: {
            "expected": 0,
            "correct": 0,
            "missing_prediction": 0,
            "confusion": {},
        }
        for key in ATTRIBUTE_KEYS
    }


def update_summary(summary: dict[str, dict[str, int]], row_result: dict[str, Any]) -> None:
    expected = row_result.get("expected_context") or {}
    if not expected:
        raise ValueError("row_result must include expected_context")
    predicted = row_result["predicted"]
    matches = row_result["matches"]
    for key in ATTRIBUTE_KEYS:
        if not expected.get(key):
            continue
        summary[key]["expected"] += 1
        if matches.get(key):
            summary[key]["correct"] += 1
        if not predicted.get(key):
            summary[key]["missing_prediction"] += 1
        expected_value = normalize(expected.get(key))
        predicted_value = normalize(predicted.get(key)) or "<missing>"
        confusion = summary[key].setdefault("confusion", {})
        if expected_value not in confusion:
            confusion[expected_value] = {}
        confusion[expected_value][predicted_value] = int(confusion[expected_value].get(predicted_value, 0)) + 1


def finalize_summary(summary: dict[str, dict[str, int]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key, counts in summary.items():
        expected = counts["expected"]
        correct = counts["correct"]
        result[key] = {
            **counts,
            "accuracy": round(correct / expected, 4) if expected else None,
        }
    return result


def clean(value: Any) -> str:
    return str(value or "").strip()


def normalize(value: Any) -> str:
    return clean(value).replace(" ", "").replace("\t", "")


def canonical_attribute(key: str, value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    catalog = ATTRIBUTE_CATALOGS.get(key, {})
    if text in catalog:
        return text
    for canonical, aliases in catalog.items():
        if any(alias and alias in text for alias in aliases):
            return canonical
    return text


if __name__ == "__main__":
    raise SystemExit(main())
