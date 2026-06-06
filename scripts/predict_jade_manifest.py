from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_multimodal_service import analyze_jade_image, analyze_jade_text, merge_jade_analysis  # noqa: E402
from app.services.jade_review_flags_service import jade_analysis_review_flags  # noqa: E402
from app.services.jade_yolo_service import get_yolo_runtime_status  # noqa: E402


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


OUTPUT_FIELDS = [
    "row",
    "batch_id",
    "vlm_model",
    "image",
    "text",
    "expected_color",
    "expected_color_family",
    "expected_color_detail",
    "expected_color_pattern",
    "expected_water",
    "expected_style",
    "expected_theme",
    "predicted_name",
    "predicted_color",
    "predicted_color_family",
    "predicted_color_detail",
    "predicted_color_pattern",
    "predicted_opencv_pattern_candidate",
    "predicted_opencv_pattern_reason",
    "predicted_vlm_color_signal",
    "predicted_subject_colors_json",
    "predicted_frame_colors_json",
    "predicted_subject_roi_json",
    "predicted_water",
    "predicted_water_detail",
    "predicted_water_texture",
    "predicted_style",
    "predicted_theme",
    "predicted_size",
    "predicted_price",
    "confidence",
    "review_flags",
    "detections_json",
    "signals_json",
    "error",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run jade multimodal prediction for every row in a manifest.")
    parser.add_argument("--manifest", required=True, type=Path, help="CSV, JSON, or JSONL manifest with image/text columns.")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "jade_manifest_predictions.csv")
    parser.add_argument("--offset", type=int, default=0, help="Rows to skip before processing.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max rows to process.")
    parser.add_argument("--batch-id", default="", help="Optional trace ID shared by chunked prediction runs.")
    parser.add_argument("--pretty", action="store_true", help="Print JSON summary to stdout.")
    args = parser.parse_args()
    if args.offset < 0:
        print("--offset must be >= 0", file=sys.stderr)
        return 2

    manifest_path = resolve_path(args.manifest)
    batch_id = args.batch_id.strip() or f"jade-predict-{uuid.uuid4().hex[:12]}"
    rows = load_rows(manifest_path)
    if args.offset > 0:
        rows = rows[args.offset :]
    if args.limit > 0:
        rows = rows[: args.limit]

    predictions = [
        predict_row(args.offset + index, row, batch_id=batch_id)
        for index, row in enumerate(rows, start=1)
    ]
    output_path = resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(output_path, predictions)

    summary = {
        "status": "ok",
        "manifest": str(manifest_path),
        "output": str(output_path),
        "batch_id": batch_id,
        "offset": args.offset,
        "limit": args.limit,
        "rows": len(predictions),
        "errors": sum(1 for item in predictions if item.get("error")),
        "review_summary": review_flag_counts(predictions),
        "runtime": {"yolo": get_yolo_runtime_status()},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if summary["errors"] == 0 else 1


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            return [dict(row) for row in csv.DictReader(file)]
    if suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            items = data.get("items") or data.get("rows") or []
            if isinstance(items, list):
                return [row for row in items if isinstance(row, dict)]
    raise ValueError(f"unsupported manifest format: {path.suffix}")


def predict_row(index: int, row: dict[str, Any], *, batch_id: str) -> dict[str, Any]:
    output = {
        "row": index,
        "batch_id": batch_id,
        "vlm_model": clean(os.getenv("JLAO_VLM_HTTP_MODEL") or os.getenv("JLAO_VLM_MODEL")),
        "image": clean(row.get("image")),
        "text": clean(row.get("text")),
        "expected_color": first_clean(row, "expected_color", "color"),
        "expected_color_family": first_clean(row, "expected_color_family", "color_family"),
        "expected_color_detail": first_clean(row, "expected_color_detail", "color_detail"),
        "expected_color_pattern": first_clean(row, "expected_color_pattern", "color_pattern"),
        "expected_water": first_clean(row, "expected_water", "water"),
        "expected_style": first_clean(row, "expected_style", "style"),
        "expected_theme": first_clean(row, "expected_theme", "theme"),
        "predicted_name": "",
        "predicted_color": "",
        "predicted_color_family": "",
        "predicted_color_detail": "",
        "predicted_color_pattern": "",
        "predicted_opencv_pattern_candidate": "",
        "predicted_opencv_pattern_reason": "",
        "predicted_vlm_color_signal": "",
        "predicted_subject_colors_json": "[]",
        "predicted_frame_colors_json": "[]",
        "predicted_subject_roi_json": "{}",
        "predicted_water": "",
        "predicted_water_detail": "",
        "predicted_water_texture": "",
        "predicted_style": "",
        "predicted_theme": "",
        "predicted_size": "",
        "predicted_price": "",
        "confidence": "",
        "review_flags": "",
        "detections_json": "[]",
        "signals_json": "{}",
        "error": "",
    }
    try:
        analyses = []
        image = output["image"]
        text = output["text"]
        if image:
            image_path = resolve_path(Path(image))
            if not image_path.exists():
                raise FileNotFoundError(f"image not found: {image_path}")
            analyses.append(analyze_jade_image(image_path, context_text=text))
        if text:
            analyses.append(analyze_jade_text(text))
        if not analyses:
            raise ValueError("row has neither image nor text")

        analysis = merge_jade_analysis(*analyses) if len(analyses) > 1 else analyses[0]
        color_analysis = analysis.signals.get("color_analysis") if isinstance(analysis.signals, dict) else {}
        if not isinstance(color_analysis, dict):
            color_analysis = {}
        water_analysis = analysis.signals.get("water_analysis") if isinstance(analysis.signals, dict) else {}
        if not isinstance(water_analysis, dict):
            water_analysis = {}
        output.update(
            {
                "predicted_name": analysis.full_name(),
                "predicted_color": analysis.color,
                "predicted_color_family": clean(color_analysis.get("family")),
                "predicted_color_detail": clean(color_analysis.get("detail")),
                "predicted_color_pattern": clean(color_analysis.get("pattern")),
                "predicted_opencv_pattern_candidate": clean(color_analysis.get("opencv_pattern_candidate")),
                "predicted_opencv_pattern_reason": clean(color_analysis.get("opencv_pattern_reason")),
                "predicted_vlm_color_signal": clean_bool(color_analysis.get("vlm_color_signal")),
                "predicted_subject_colors_json": json.dumps(color_analysis.get("opencv_subject_colors") or [], ensure_ascii=False),
                "predicted_frame_colors_json": json.dumps(color_analysis.get("opencv_frame_colors") or [], ensure_ascii=False),
                "predicted_subject_roi_json": json.dumps(color_analysis.get("opencv_subject_roi") or {}, ensure_ascii=False),
                "predicted_water": analysis.water,
                "predicted_water_detail": first_clean(water_analysis, "detail", "raw"),
                "predicted_water_texture": clean(water_analysis.get("texture")),
                "predicted_style": analysis.style,
                "predicted_theme": analysis.theme,
                "predicted_size": analysis.size,
                "predicted_price": analysis.price,
                "confidence": analysis.confidence,
                "review_flags": "; ".join(jade_analysis_review_flags(analysis)),
                "detections_json": json.dumps(analysis.detections, ensure_ascii=False),
                "signals_json": json.dumps(analysis.signals, ensure_ascii=False),
            }
        )
    except Exception as exc:  # noqa: BLE001
        output["error"] = str(exc)
    return output


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def first_clean(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = clean(row.get(key))
        if value:
            return value
    return ""


def clean_bool(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    text = clean(value).lower()
    if text in {"true", "false"}:
        return text
    return clean(value)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def review_flag_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        flags = str(row.get("review_flags") or "").split(";")
        for flag in flags:
            key = flag.strip()
            if key:
                counts[key] = counts.get(key, 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
