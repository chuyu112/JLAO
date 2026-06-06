from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_training_service import class_names_from_feedback  # noqa: E402


FIELDS = [
    "priority",
    "reasons",
    "row",
    "batch_id",
    "image",
    "text",
    "confidence",
    "review_flags",
    "predicted_color",
    "predicted_water",
    "predicted_style",
    "predicted_theme",
    "expected_color",
    "expected_water",
    "expected_style",
    "expected_theme",
    "class_name",
    "recommended_action",
    "error",
]


ATTRIBUTE_KEYS = ["color", "water", "style", "theme"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Select high-priority jade prediction rows for human review.")
    parser.add_argument("--predictions", required=True, type=Path, help="CSV created by predict_jade_manifest.py.")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "jade_review_queue.csv")
    parser.add_argument("--confidence-threshold", type=float, default=0.45)
    parser.add_argument("--limit", type=int, default=120, help="Maximum rows to write; 0 means all.")
    args = parser.parse_args()

    predictions_path = resolve_path(args.predictions)
    output_path = resolve_path(args.output)
    rows = load_prediction_rows(predictions_path)
    selected = [score_row(row, confidence_threshold=args.confidence_threshold) for row in rows]
    selected = [row for row in selected if int(row["priority"]) > 0]
    selected.sort(key=lambda row: (-int(row["priority"]), clean(row.get("row")), clean(row.get("image"))))
    if args.limit > 0:
        selected = selected[: args.limit]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(selected)

    print(f"wrote {len(selected)} review rows to {output_path}")
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_prediction_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"predictions file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def score_row(row: dict[str, Any], *, confidence_threshold: float) -> dict[str, str]:
    reasons: list[str] = []
    priority = 0
    confidence = parse_float(row.get("confidence"))
    predicted = {key: clean(row.get(f"predicted_{key}")) for key in ATTRIBUTE_KEYS}
    expected = {key: clean(row.get(f"expected_{key}")) for key in ATTRIBUTE_KEYS}
    error = clean(row.get("error"))
    review_flags = parse_flags(row.get("review_flags"))

    if error:
        priority += 100
        reasons.append("prediction-error")
    if "low-confidence" in review_flags or confidence < confidence_threshold:
        priority += 40
        reasons.append("low-confidence")
    missing = [key for key, value in predicted.items() if not value]
    if missing:
        priority += 12 * len(missing)
        reasons.append("missing-" + "|".join(missing))
    for flag in review_flags:
        if flag.startswith("missing-") and flag not in reasons:
            priority += 12
            reasons.append(flag)
        if flag in {"no-yolo-detections", "no-attribute-sources"}:
            priority += 10
            reasons.append(flag)
    conflicts = [
        key
        for key in ATTRIBUTE_KEYS
        if expected.get(key) and predicted.get(key) and expected[key] != predicted[key]
    ]
    if conflicts:
        priority += 18 * len(conflicts)
        reasons.append("expected-conflict-" + "|".join(conflicts))

    classes = class_names_from_feedback({"corrected": {"style": predicted["style"], "theme": predicted["theme"]}})
    if len(classes) > 1:
        priority += 30
        reasons.append("multi-class-needs-manual-box")
    elif not classes and (predicted["style"] or predicted["theme"]):
        priority += 16
        reasons.append("no-yolo-class")

    return {
        "priority": str(priority),
        "reasons": "; ".join(reasons),
        "row": clean(row.get("row")),
        "batch_id": clean(row.get("batch_id")),
        "image": clean(row.get("image")),
        "text": clean(row.get("text")),
        "confidence": str(confidence),
        "review_flags": "; ".join(review_flags),
        "predicted_color": predicted["color"],
        "predicted_water": predicted["water"],
        "predicted_style": predicted["style"],
        "predicted_theme": predicted["theme"],
        "expected_color": expected["color"],
        "expected_water": expected["water"],
        "expected_style": expected["style"],
        "expected_theme": expected["theme"],
        "class_name": "|".join(classes),
        "recommended_action": recommended_action(reasons),
        "error": error,
    }


def recommended_action(reasons: list[str]) -> str:
    joined = ";".join(reasons)
    if "prediction-error" in joined:
        return "check-image-path-or-runtime"
    if "multi-class-needs-manual-box" in joined:
        return "draw-manual-yolo-boxes"
    if "missing-" in joined or "expected-conflict-" in joined:
        return "review-attributes"
    if "low-confidence" in joined:
        return "confirm-or-correct-before-training"
    return "review"


def parse_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_flags(value: Any) -> list[str]:
    text = clean(value)
    if not text:
        return []
    if ";" in text:
        return [part.strip() for part in text.split(";") if part.strip()]
    return [text]


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


if __name__ == "__main__":
    raise SystemExit(main())
