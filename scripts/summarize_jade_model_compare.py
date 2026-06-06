from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
METRIC_KEYS = ["color", "color_family", "color_detail", "color_pattern", "water", "style", "theme"]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize jade VLM model comparison JSON reports.")
    parser.add_argument("--inputs", nargs="+", required=True, type=Path, help="Diagnosis JSON files from summarize_jade_color_control_run.py.")
    parser.add_argument("--output-json", type=Path, default=ROOT / "tmp" / "jade-model-compare-summary.json")
    parser.add_argument("--output-csv", type=Path, default=ROOT / "tmp" / "jade-model-compare-summary.csv")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    rows = [summary_row(resolve_path(path)) for path in args.inputs]
    payload = {
        "status": "ok",
        "rows": rows,
        "best_by_metric": best_by_metric(rows),
        "outputs": {
            "json": str(resolve_path(args.output_json)),
            "csv": str(resolve_path(args.output_csv)),
        },
    }

    write_csv(resolve_path(args.output_csv), rows)
    resolve_path(args.output_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def summary_row(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics = payload.get("metrics") if isinstance(payload, dict) else {}
    failure_buckets = payload.get("failure_buckets") if isinstance(payload, dict) else {}
    confusions = payload.get("confusions") if isinstance(payload, dict) else {}
    row: dict[str, Any] = {
        "model": model_from_path(path),
        "report": str(path),
        "rows": payload.get("rows", ""),
        "all_color_layers_ok": clean((failure_buckets or {}).get("all_color_layers_ok")),
        "model_color_family_miss": clean((failure_buckets or {}).get("model_color_family_miss")),
        "fine_color_detail_miss": clean((failure_buckets or {}).get("fine_color_detail_miss")),
        "color_pattern_miss": clean((failure_buckets or {}).get("color_pattern_miss")),
        "generation_quality_issue": clean((failure_buckets or {}).get("generation_quality_issue")),
    }
    for key in METRIC_KEYS:
        metric = (metrics or {}).get(key) or {}
        row[f"{key}_accuracy"] = clean(metric.get("accuracy"))
        row[f"{key}_correct"] = clean(metric.get("correct"))
        row[f"{key}_total"] = clean(metric.get("total"))
        row[f"{key}_top_confusion"] = top_confusion((confusions or {}).get(key))
    return row


def best_by_metric(rows: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in METRIC_KEYS:
        best_model = ""
        best_score = -1.0
        for row in rows:
            try:
                score = float(row.get(f"{key}_accuracy") or -1)
            except (TypeError, ValueError):
                score = -1.0
            if score > best_score:
                best_score = score
                best_model = str(row.get("model") or "")
        result[key] = best_model
    return result


def model_from_path(path: Path) -> str:
    stem = path.stem
    prefixes = ["jade-color-control-diagnosis-", "jade-live-color-stress-diagnosis-"]
    for prefix in prefixes:
        if stem.startswith(prefix):
            return stem[len(prefix) :]
    return stem


def top_confusion(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return ""
    best_key = ""
    best_count = -1
    for key, count in value.items():
        try:
            numeric = int(count)
        except (TypeError, ValueError):
            numeric = 0
        if numeric > best_count:
            best_key = str(key)
            best_count = numeric
    return f"{best_key} ({best_count})" if best_key else ""


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def clean(value: Any) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
