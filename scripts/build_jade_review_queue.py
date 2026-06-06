from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a prioritized human review queue from a jade model compare matrix.")
    parser.add_argument("--matrix", type=Path, default=ROOT / "tmp" / "jade-model-compare-matrix.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "tmp" / "jade-review-queue.csv")
    parser.add_argument("--output-json", type=Path, default=ROOT / "tmp" / "jade-review-queue.json")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    rows = read_csv(resolve_path(args.matrix))
    models = model_slugs(rows)
    queue = [review_row(row, models) for row in rows if clean(row.get("needs_review")) == "1"]
    queue.sort(key=lambda row: (int(row["best_score"] or 0), -int(row["model_disagreement"] or 0), row["filename"]))
    if args.limit > 0:
        queue = queue[: args.limit]

    fieldnames = [
        "filename",
        "best_model",
        "best_score",
        "model_disagreement",
        "expected_color",
        "expected_color_family",
        "expected_color_detail",
        "expected_color_pattern",
        "expected_water",
        "expected_style",
        "expected_theme",
        "review_reason",
        "model_predictions",
    ]
    write_csv(resolve_path(args.output), queue, fieldnames)
    payload = {
        "status": "ok",
        "rows": len(queue),
        "models": models,
        "output": str(resolve_path(args.output)),
    }
    resolve_path(args.output_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def review_row(row: dict[str, Any], models: list[str]) -> dict[str, str]:
    predictions: dict[str, dict[str, str]] = {}
    score_values: list[int] = []
    reasons: list[str] = []
    expected = {
        "color": clean(row.get("expected_color")),
        "color_family": clean(row.get("expected_color_family")),
        "color_detail": clean(row.get("expected_color_detail")),
        "color_pattern": clean(row.get("expected_color_pattern")),
        "water": clean(row.get("expected_water")),
        "style": clean(row.get("expected_style")),
        "theme": clean(row.get("expected_theme")),
    }
    for model in models:
        score = int(clean(row.get(f"{model}_score")) or 0)
        score_values.append(score)
        predictions[model] = {
            "score": str(score),
            "failure_bucket": clean(row.get(f"{model}_failure_bucket")),
            "color": clean(row.get(f"{model}_predicted_color")),
            "family": clean(row.get(f"{model}_predicted_color_family")),
            "detail": clean(row.get(f"{model}_predicted_color_detail")),
            "pattern": clean(row.get(f"{model}_predicted_color_pattern")),
            "water": clean(row.get(f"{model}_predicted_water")),
            "style": clean(row.get(f"{model}_predicted_style")),
            "theme": clean(row.get(f"{model}_predicted_theme")),
        }
    if len(set(score_values)) > 1:
        reasons.append("model_score_disagreement")
    if min(score_values or [0]) <= 2:
        reasons.append("low_score")
    if expected["color_family"] and any(pred["family"] != expected["color_family"] for pred in predictions.values()):
        reasons.append("color_family_miss")
    if expected["water"] and any(pred["water"] != expected["water"] for pred in predictions.values()):
        reasons.append("water_miss")
    return {
        "filename": clean(row.get("filename")),
        "best_model": clean(row.get("best_model")),
        "best_score": clean(row.get("best_score")),
        "model_disagreement": "1" if len(set(score_values)) > 1 else "0",
        "expected_color": expected["color"],
        "expected_color_family": expected["color_family"],
        "expected_color_detail": expected["color_detail"],
        "expected_color_pattern": expected["color_pattern"],
        "expected_water": expected["water"],
        "expected_style": expected["style"],
        "expected_theme": expected["theme"],
        "review_reason": ";".join(reasons) or "needs_review",
        "model_predictions": json.dumps(predictions, ensure_ascii=False),
    }


def model_slugs(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return []
    result: list[str] = []
    for key in rows[0].keys():
        suffix = "_vlm_model"
        if key.endswith(suffix):
            result.append(key[: -len(suffix)])
    return result


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def clean(value: Any) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
