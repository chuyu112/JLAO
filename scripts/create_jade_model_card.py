from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SPLITS = ["train", "val", "test"]
LABEL_EXTENSIONS = {".txt"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
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
    parser = argparse.ArgumentParser(description="Create a Markdown model card for the local jade YOLO model.")
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "jade-yolo.pt")
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "jade_yolo")
    parser.add_argument("--after", type=Path, default=ROOT / "data" / "jade_eval_after_train.json")
    parser.add_argument("--comparison", type=Path, default=ROOT / "data" / "jade_eval_comparison.json")
    parser.add_argument("--output", type=Path, default=ROOT / "models" / "jade-yolo-card.md")
    args = parser.parse_args()

    model = resolve_path(args.model)
    dataset = resolve_path(args.dataset)
    after = load_optional_json(resolve_path(args.after))
    comparison = load_optional_json(resolve_path(args.comparison))
    output = resolve_path(args.output)

    markdown = build_model_card(model, dataset, after, comparison)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    print(f"wrote {output}")
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


def build_model_card(model: Path, dataset: Path, after: dict[str, Any], comparison: dict[str, Any]) -> str:
    label_counts = split_counts(dataset, "labels", LABEL_EXTENSIONS)
    image_counts = split_counts(dataset, "images", IMAGE_EXTENSIONS)
    lines: list[str] = [
        "# 翡翠多模态识别模型卡",
        "",
        "## 模型文件",
        "",
        f"- path: `{model}`",
        f"- exists: `{str(model.exists()).lower()}`",
        f"- size_bytes: `{model.stat().st_size if model.exists() else 0}`",
        "",
        "## 数据集",
        "",
        f"- dataset: `{dataset}`",
        "",
        "| split | images | labels |",
        "| --- | ---: | ---: |",
    ]
    for split in SPLITS:
        lines.append(f"| {split} | {image_counts.get(split, 0)} | {label_counts.get(split, 0)} |")

    lines.extend(
        [
            "",
            "## 训练后评估",
            "",
            f"- after_report: {report_status(after)}",
            f"- comparison_report: {report_status(comparison)}",
            "",
            "| 模式 | 字段 | 训练后准确率 | 相对训练前变化 | 方向 |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    after_metrics = after.get("metrics") if isinstance(after.get("metrics"), dict) else {}
    comparison_metrics = comparison.get("comparison") if isinstance(comparison.get("comparison"), dict) else {}
    for mode in MODES:
        for field in FIELDS:
            after_accuracy = (((after_metrics.get(mode) or {}).get(field) or {}).get("accuracy"))
            comp_metric = ((comparison_metrics.get(mode) or {}).get(field) or {})
            lines.append(
                "| {mode} | {field} | {accuracy} | {delta} | {direction} |".format(
                    mode=mode,
                    field=FIELD_LABELS[field],
                    accuracy=format_percent(after_accuracy),
                    delta=format_delta(comp_metric.get("delta")),
                    direction=comp_metric.get("direction") or "unknown",
                )
            )

    gate = comparison.get("gate") if isinstance(comparison.get("gate"), dict) else {}
    lines.extend(
        [
            "",
            "## 质量 Gate",
            "",
            f"- status: `{gate.get('status', 'unknown')}`",
            f"- failures: `{json.dumps(gate.get('failures', []), ensure_ascii=False)}`",
            "",
            "## 使用说明",
            "",
            "- 图像侧以 `models/jade-yolo.pt` 为本地翡翠 YOLO 模型。",
            "- 文本侧继续使用主播讲解/STT 的关键词和反馈学习。",
            "- `fused` 指标是最终多模态融合结果，应优先作为产品效果参考。",
            "- 颜色和种水容易受光照、白平衡、压缩影响，建议继续用人工反馈闭环迭代。",
            "",
            "## 限制",
            "",
            "- 样本量不足或类别不均衡时，不应把评估结果视为稳定泛化能力。",
            "- 多主体图片必须有人工框，否则 YOLO 标签会污染。",
            "- 训练后若 `image.style/theme` 未提升，应优先补充对应类别图片和框。",
            "",
        ]
    )
    return "\n".join(lines)


def split_counts(dataset: Path, group: str, extensions: set[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for split in SPLITS:
        folder = dataset / group / split
        result[split] = count_files(folder, extensions)
    return result


def count_files(folder: Path, extensions: set[str]) -> int:
    if not folder.exists():
        return 0
    return sum(1 for item in folder.iterdir() if item.is_file() and item.suffix.lower() in extensions)


def report_status(report: dict[str, Any]) -> str:
    if report.get("_missing"):
        return f"missing `{report.get('_path')}`"
    if report.get("_invalid"):
        return f"invalid `{report.get('_path')}`"
    return f"ok rows=`{report.get('rows', 'unknown')}`"


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
