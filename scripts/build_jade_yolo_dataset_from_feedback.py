from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_training_service import auto_prepare_validation_split, build_jade_feedback_dataset


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build weak YOLO labels from jade sample-analysis feedback."
    )
    parser.add_argument("--feedback", default="data/jade_feedback.jsonl")
    parser.add_argument("--dataset", default="data/jade_yolo")
    parser.add_argument("--split", choices=["train", "val"], default="train")
    parser.add_argument("--val-every", type=int, default=5, help="send every Nth sample to val; 0 disables")
    parser.add_argument("--auto-val", action="store_true", help="move a ratio of train labels into val after building")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="validation split ratio used with --auto-val")
    parser.add_argument("--write-yaml", action="store_true", help="rewrite dataset.yaml")
    args = parser.parse_args()

    stats = build_jade_feedback_dataset(
        feedback_path=resolve_workspace_path(args.feedback),
        dataset_root=resolve_workspace_path(args.dataset),
        split=args.split,
        val_every=args.val_every,
        write_yaml=args.write_yaml,
    )
    if args.auto_val:
        stats["validation_split"] = auto_prepare_validation_split(
            dataset_root=resolve_workspace_path(args.dataset),
            val_ratio=args.val_ratio,
        )
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0 if stats["status"] == "ok" else 2


def resolve_workspace_path(raw: str | Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
