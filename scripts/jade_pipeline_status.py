from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
LABEL_EXTENSIONS = {".txt"}
SPLITS = ["train", "val", "test"]


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Report local jade multimodal recognition pipeline status.")
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "jade_yolo")
    parser.add_argument("--feedback", type=Path, default=ROOT / "data" / "jade_feedback.jsonl")
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "jade-yolo.pt")
    parser.add_argument("--model-card", type=Path, default=ROOT / "models" / "jade-yolo-card.md")
    parser.add_argument("--artifacts", type=Path, default=ROOT / "models" / "jade-yolo-artifacts.zip")
    parser.add_argument("--baseline", type=Path, default=ROOT / "data" / "jade_eval_baseline.json")
    parser.add_argument("--after", type=Path, default=ROOT / "data" / "jade_eval_after_train.json")
    parser.add_argument("--comparison", type=Path, default=ROOT / "data" / "jade_eval_comparison.json")
    parser.add_argument("--summary", type=Path, default=ROOT / "data" / "jade_eval_summary.md")
    parser.add_argument("--mistakes", type=Path, default=ROOT / "data" / "jade_eval_mistakes.csv")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    dataset = resolve_path(args.dataset)
    feedback = resolve_path(args.feedback)
    model = resolve_path(args.model)
    model_card = resolve_path(args.model_card)
    artifacts = resolve_path(args.artifacts)
    baseline = resolve_path(args.baseline)
    after = resolve_path(args.after)
    comparison = resolve_path(args.comparison)
    summary = resolve_path(args.summary)
    mistakes = resolve_path(args.mistakes)

    label_counts = split_counts(dataset, "labels", LABEL_EXTENSIONS)
    image_counts = split_counts(dataset, "images", IMAGE_EXTENSIONS)
    payload = {
        "status": "ok",
        "dataset": {
            "path": str(dataset),
            "dataset_yaml": file_status(dataset / "dataset.yaml"),
            "images": image_counts,
            "labels": label_counts,
            "training_thresholds": {
                "min_train_labels": 10,
                "min_val_labels": 2,
                "train_labels": label_counts.get("train", 0),
                "val_labels": label_counts.get("val", 0),
                "missing_train_labels": max(0, 10 - int(label_counts.get("train", 0))),
                "missing_val_labels": max(0, 2 - int(label_counts.get("val", 0))),
                "ready": label_counts.get("train", 0) >= 10 and label_counts.get("val", 0) >= 2,
            },
        },
        "feedback": {
            **file_status(feedback),
            "records": count_jsonl_lines(feedback),
        },
        "model": file_status(model),
        "model_card": file_status(model_card),
        "artifacts": file_status(artifacts),
        "reports": {
            "baseline": report_status(baseline),
            "after_train": report_status(after),
            "comparison": report_status(comparison),
            "summary": file_status(summary),
            "mistakes": {
                **file_status(mistakes),
                "rows": count_csv_rows(mistakes),
            },
        },
        "next_missing": next_missing(
            label_counts,
            model,
            model_card,
            artifacts,
            baseline,
            after,
            comparison,
            summary,
            mistakes,
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


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


def count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8-sig") as handle:
        for index, line in enumerate(handle):
            if index == 0:
                continue
            if line.strip():
                count += 1
    return count


def file_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "size": 0,
        }
    return {
        "path": str(path),
        "exists": True,
        "size": path.stat().st_size,
        "modified": path.stat().st_mtime,
    }


def report_status(path: Path) -> dict[str, Any]:
    status = file_status(path)
    if not path.exists():
        return status
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        status["valid_json"] = False
        return status
    status["valid_json"] = isinstance(payload, dict)
    if isinstance(payload, dict):
        status["rows"] = payload.get("rows")
        status["gate"] = payload.get("gate")
    return status


def next_missing(
    label_counts: dict[str, int],
    model: Path,
    model_card: Path,
    artifacts: Path,
    baseline: Path,
    after: Path,
    comparison: Path,
    summary: Path,
    mistakes: Path,
) -> list[str]:
    missing: list[str] = []
    if label_counts.get("train", 0) < 10 or label_counts.get("val", 0) < 2:
        missing.append("import enough labeled jade samples and build train/val dataset")
    if not model.exists():
        missing.append("train models/jade-yolo.pt")
    if not model_card.exists():
        missing.append("generate models/jade-yolo-card.md")
    if not artifacts.exists():
        missing.append("optionally package models/jade-yolo-artifacts.zip")
    if not baseline.exists():
        missing.append("generate baseline evaluation report")
    if not after.exists():
        missing.append("generate after-training evaluation report")
    if not comparison.exists():
        missing.append("generate baseline vs after-training comparison report")
    if not summary.exists():
        missing.append("generate Markdown evaluation summary")
    if not mistakes.exists():
        missing.append("optionally export evaluation mistakes for next review loop")
    return missing


if __name__ == "__main__":
    raise SystemExit(main())
