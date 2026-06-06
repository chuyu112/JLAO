from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODES = ["image", "text", "fused"]
FIELDS = ["color", "water", "style", "theme"]
FIELD_LABELS = {
    "color": "颜色",
    "water": "种水",
    "style": "样式",
    "theme": "题材",
}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Markdown summary from jade evaluation reports.")
    parser.add_argument("--baseline", type=Path, default=ROOT / "data" / "jade_eval_baseline.json")
    parser.add_argument("--after", type=Path, default=ROOT / "data" / "jade_eval_after_train.json")
    parser.add_argument("--comparison", type=Path, default=ROOT / "data" / "jade_eval_comparison.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "jade_eval_summary.md")
    args = parser.parse_args()

    baseline = load_optional_json(resolve_path(args.baseline))
    after = load_optional_json(resolve_path(args.after))
    comparison = load_optional_json(resolve_path(args.comparison))
    output_path = resolve_path(args.output)
    markdown = build_markdown(baseline, after, comparison)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"wrote {output_path}")
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"_missing": True, "_path": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"_invalid": True, "_path": str(path), "_error": str(exc)}
    return payload if isinstance(payload, dict) else {"_invalid": True, "_path": str(path)}


def build_markdown(baseline: dict[str, Any], after: dict[str, Any], comparison: dict[str, Any]) -> str:
    lines: list[str] = [
        "# 翡翠多模态识别评估摘要",
        "",
        "## 报告状态",
        "",
        f"- baseline: {status_text(baseline)}",
        f"- after_train: {status_text(after)}",
        f"- comparison: {status_text(comparison)}",
        "",
        "## 准确率对比",
        "",
        "| 模式 | 字段 | 训练前 | 训练后 | 变化 | 方向 |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    comp = comparison.get("comparison") if isinstance(comparison.get("comparison"), dict) else {}
    for mode in MODES:
        for field in FIELDS:
            metric = ((comp.get(mode) or {}).get(field) or {})
            lines.append(
                "| {mode} | {field} | {before} | {after} | {delta} | {direction} |".format(
                    mode=mode,
                    field=FIELD_LABELS[field],
                    before=format_percent(metric.get("baseline_accuracy")),
                    after=format_percent(metric.get("after_accuracy")),
                    delta=format_delta(metric.get("delta")),
                    direction=metric.get("direction") or "unknown",
                )
            )

    lines.extend(["", "## Gate", ""])
    gate = comparison.get("gate") if isinstance(comparison.get("gate"), dict) else {}
    lines.append(f"- status: {gate.get('status', 'unknown')}")
    failures = gate.get("failures") if isinstance(gate.get("failures"), list) else []
    if failures:
        for failure in failures:
            lines.append(f"- failure: `{json.dumps(failure, ensure_ascii=False)}`")
    else:
        lines.append("- failures: none")

    lines.extend(["", "## 常见误判方向", ""])
    add_confusion_section(lines, "训练前", baseline)
    add_confusion_section(lines, "训练后", after)
    lines.append("")
    return "\n".join(lines)


def add_confusion_section(lines: list[str], title: str, report: dict[str, Any]) -> None:
    lines.append(f"### {title}")
    lines.append("")
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    for mode in MODES:
        lines.append(f"#### {mode}")
        for field in FIELDS:
            confusion = (((metrics.get(mode) or {}).get(field) or {}).get("confusion") or {})
            top = top_confusions(confusion, limit=5)
            if not top:
                lines.append(f"- {FIELD_LABELS[field]}: none")
                continue
            rendered = "；".join(f"{expected} -> {predicted}: {count}" for expected, predicted, count in top)
            lines.append(f"- {FIELD_LABELS[field]}: {rendered}")
        lines.append("")


def top_confusions(confusion: Any, *, limit: int) -> list[tuple[str, str, int]]:
    if not isinstance(confusion, dict):
        return []
    rows: list[tuple[str, str, int]] = []
    for expected, predictions in confusion.items():
        if not isinstance(predictions, dict):
            continue
        for predicted, count in predictions.items():
            if str(expected) == str(predicted):
                continue
            try:
                rows.append((str(expected), str(predicted), int(count)))
            except (TypeError, ValueError):
                continue
    return sorted(rows, key=lambda item: item[2], reverse=True)[:limit]


def status_text(report: dict[str, Any]) -> str:
    if report.get("_missing"):
        return f"missing ({report.get('_path')})"
    if report.get("_invalid"):
        return f"invalid ({report.get('_path')})"
    return f"ok rows={report.get('rows', 'unknown')}"


def format_percent(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "-"


def format_delta(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value) * 100:+.1f}%"
    except (TypeError, ValueError):
        return "-"


if __name__ == "__main__":
    raise SystemExit(main())
