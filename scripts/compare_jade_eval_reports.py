from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODES = ["image", "text", "fused"]
FIELDS = ["color", "water", "style", "theme"]


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare jade baseline and after-training evaluation reports.")
    parser.add_argument("--baseline", type=Path, default=ROOT / "data" / "jade_eval_baseline.json")
    parser.add_argument("--after", type=Path, default=ROOT / "data" / "jade_eval_after_train.json")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON comparison output path.")
    parser.add_argument("--fail-on-regression", action="store_true", help="Exit nonzero if any comparable metric regressed.")
    parser.add_argument("--min-fused-color", type=float, default=None)
    parser.add_argument("--min-fused-water", type=float, default=None)
    parser.add_argument("--min-fused-style", type=float, default=None)
    parser.add_argument("--min-fused-theme", type=float, default=None)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    baseline_path = resolve_path(args.baseline)
    after_path = resolve_path(args.after)
    if not baseline_path.exists():
        print(json.dumps({"status": "missing-baseline", "baseline": str(baseline_path)}, ensure_ascii=False))
        return 2
    if not after_path.exists():
        print(json.dumps({"status": "missing-after", "after": str(after_path)}, ensure_ascii=False))
        return 2

    baseline = load_json(baseline_path)
    after = load_json(after_path)
    comparison = compare_metrics(baseline.get("metrics") or {}, after.get("metrics") or {})
    gate = gate_result(comparison, args)
    payload = {
        "status": "ok",
        "baseline": str(baseline_path),
        "after": str(after_path),
        "rows": {
            "baseline": baseline.get("rows"),
            "after": after.get("rows"),
        },
        "comparison": comparison,
        "gate": gate,
    }

    output_text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output is not None:
        output_path = resolve_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_text)
    return 0 if gate["status"] == "pass" else 3


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def compare_metrics(baseline: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for mode in MODES:
        result[mode] = {}
        for field in FIELDS:
            before_accuracy = metric_accuracy(baseline, mode, field)
            after_accuracy = metric_accuracy(after, mode, field)
            delta = None
            if before_accuracy is not None and after_accuracy is not None:
                delta = round(after_accuracy - before_accuracy, 4)
            result[mode][field] = {
                "baseline_accuracy": before_accuracy,
                "after_accuracy": after_accuracy,
                "delta": delta,
                "direction": direction(delta),
            }
    return result


def metric_accuracy(metrics: dict[str, Any], mode: str, field: str) -> float | None:
    value = ((metrics.get(mode) or {}).get(field) or {}).get("accuracy")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def direction(delta: float | None) -> str:
    if delta is None:
        return "unknown"
    if delta > 0:
        return "improved"
    if delta < 0:
        return "regressed"
    return "unchanged"


def gate_result(comparison: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    if args.fail_on_regression:
        for mode, fields in comparison.items():
            for field, metric in fields.items():
                if metric.get("direction") == "regressed":
                    failures.append({"type": "regression", "mode": mode, "field": field, "delta": metric.get("delta")})

    thresholds = {
        "color": args.min_fused_color,
        "water": args.min_fused_water,
        "style": args.min_fused_style,
        "theme": args.min_fused_theme,
    }
    fused = comparison.get("fused") or {}
    for field, minimum in thresholds.items():
        if minimum is None:
            continue
        accuracy = (fused.get(field) or {}).get("after_accuracy")
        if accuracy is None or float(accuracy) < float(minimum):
            failures.append(
                {
                    "type": "below-threshold",
                    "mode": "fused",
                    "field": field,
                    "after_accuracy": accuracy,
                    "minimum": minimum,
                }
            )
    return {
        "status": "fail" if failures else "pass",
        "failures": failures,
    }


if __name__ == "__main__":
    raise SystemExit(main())
