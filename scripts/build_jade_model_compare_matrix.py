from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_FIELDS = [
    "filename",
    "expected_color",
    "expected_color_family",
    "expected_color_detail",
    "expected_color_pattern",
    "expected_water",
    "expected_style",
    "expected_theme",
]
MODEL_FIELDS = [
    "failure_bucket",
    "predicted_color",
    "predicted_color_family",
    "predicted_color_detail",
    "predicted_color_pattern",
    "predicted_water",
    "predicted_style",
    "predicted_theme",
    "predicted_opencv_pattern_candidate",
    "predicted_opencv_pattern_reason",
    "predicted_vlm_color_signal",
]
SCORE_FIELDS = ["color_family", "color_detail", "color_pattern", "water", "style", "theme"]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a row-level jade VLM model comparison matrix from diagnosis CSV files.")
    parser.add_argument("--inputs", nargs="+", required=True, type=Path, help="Diagnosis CSV files from summarize_jade_color_control_run.py.")
    parser.add_argument("--output", type=Path, default=ROOT / "tmp" / "jade-model-compare-matrix.csv")
    parser.add_argument("--output-json", type=Path, default=ROOT / "tmp" / "jade-model-compare-matrix.json")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    matrix: dict[str, dict[str, Any]] = {}
    model_slugs: list[str] = []
    for input_path in args.inputs:
        path = resolve_path(input_path)
        model = model_from_path(path)
        model_slugs.append(model)
        for row in read_csv(path):
            filename = clean(row.get("filename"))
            if not filename:
                continue
            target = matrix.setdefault(filename, {"filename": filename})
            for field in BASE_FIELDS[1:]:
                if not clean(target.get(field)):
                    target[field] = clean(row.get(field))
            target[f"{model}_vlm_model"] = clean(row.get("predicted_vlm_model")) or model
            for field in MODEL_FIELDS:
                target[f"{model}_{field}"] = clean(row.get(field))
            target[f"{model}_score"] = model_score(row)

    for target in matrix.values():
        apply_winner_fields(target, model_slugs)

    output_rows = [matrix[key] for key in sorted(matrix.keys())]
    fieldnames = build_fieldnames(model_slugs)
    write_csv(resolve_path(args.output), output_rows, fieldnames)
    payload = {
        "status": "ok",
        "rows": len(output_rows),
        "models": model_slugs,
        "output": str(resolve_path(args.output)),
    }
    resolve_path(args.output_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def build_fieldnames(models: list[str]) -> list[str]:
    fields = list(BASE_FIELDS)
    for model in models:
        fields.append(f"{model}_vlm_model")
        fields.extend(f"{model}_{field}" for field in MODEL_FIELDS)
        fields.append(f"{model}_score")
    fields.extend(["best_model", "best_score", "needs_review"])
    return fields


def model_score(row: dict[str, Any]) -> int:
    score = 0
    for field in SCORE_FIELDS:
        expected = clean(row.get(f"expected_{field}"))
        predicted = clean(row.get(f"predicted_{field}"))
        if expected and expected == predicted:
            score += 1
    return score


def apply_winner_fields(row: dict[str, Any], models: list[str]) -> None:
    best_models: list[str] = []
    best_score = -1
    scores: list[int] = []
    for model in models:
        try:
            score = int(row.get(f"{model}_score") or 0)
        except (TypeError, ValueError):
            score = 0
        scores.append(score)
        if score > best_score:
            best_score = score
            best_models = [model]
        elif score == best_score:
            best_models.append(model)
    row["best_model"] = ",".join(best_models)
    row["best_score"] = best_score if best_score >= 0 else ""
    row["needs_review"] = "1" if (best_score < len(SCORE_FIELDS) or len(set(scores)) > 1) else "0"


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


def model_from_path(path: Path) -> str:
    stem = path.stem
    prefixes = ["jade-color-control-diagnosis-", "jade-live-color-stress-diagnosis-"]
    for prefix in prefixes:
        if stem.startswith(prefix):
            return stem[len(prefix) :]
    return stem


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def clean(value: Any) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
