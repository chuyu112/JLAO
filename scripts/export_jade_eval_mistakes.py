from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODES = ["image", "text", "fused"]
FIELDS = ["color", "water", "style", "theme"]
OUTPUT_FIELDS = [
    "mode",
    "field",
    "index",
    "image",
    "expected",
    "predicted",
    "raw_expected",
    "confidence",
    "errors",
]


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export mistaken jade evaluation rows to CSV for review.")
    parser.add_argument("--report", type=Path, default=ROOT / "data" / "jade_eval_after_train.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "jade_eval_mistakes.csv")
    parser.add_argument("--mode", choices=["image", "text", "fused", "all"], default="all")
    parser.add_argument("--field", choices=["color", "water", "style", "theme", "all"], default="all")
    args = parser.parse_args()

    report_path = resolve_path(args.report)
    output_path = resolve_path(args.output)
    if not report_path.exists():
        print(json.dumps({"status": "missing-report", "report": str(report_path)}, ensure_ascii=False))
        return 2

    report = load_json(report_path)
    rows = mistake_rows(report, args.mode, args.field)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(
        json.dumps(
            {
                "status": "ok",
                "report": str(report_path),
                "output": str(output_path),
                "mistakes": len(rows),
                "requires_include_rows": not bool(report.get("results")),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def mistake_rows(report: dict[str, Any], mode_filter: str, field_filter: str) -> list[dict[str, Any]]:
    modes = MODES if mode_filter == "all" else [mode_filter]
    fields = FIELDS if field_filter == "all" else [field_filter]
    results = report.get("results") if isinstance(report.get("results"), list) else []
    rows: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        expected = result.get("expected") if isinstance(result.get("expected"), dict) else {}
        raw_expected = result.get("raw_expected") if isinstance(result.get("raw_expected"), dict) else {}
        mode_results = result.get("modes") if isinstance(result.get("modes"), dict) else {}
        for mode in modes:
            mode_result = mode_results.get(mode) if isinstance(mode_results.get(mode), dict) else {}
            predicted = mode_result.get("predicted") if isinstance(mode_result.get("predicted"), dict) else {}
            matches = mode_result.get("matches") if isinstance(mode_result.get("matches"), dict) else {}
            for field in fields:
                if not expected.get(field):
                    continue
                if bool(matches.get(field)):
                    continue
                rows.append(
                    {
                        "mode": mode,
                        "field": field,
                        "index": result.get("index", ""),
                        "image": result.get("image", ""),
                        "expected": expected.get(field, ""),
                        "predicted": predicted.get(field, ""),
                        "raw_expected": raw_expected.get(field, ""),
                        "confidence": mode_result.get("confidence", ""),
                        "errors": "; ".join(str(item) for item in (result.get("errors") or [])),
                    }
                )
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
