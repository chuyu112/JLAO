from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
YOLO_CONFIG_DIR = ROOT / ".ultralytics"
YOLO_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(YOLO_CONFIG_DIR))
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_training_config import JADE_YOLO_CLASS_NAMES, build_jade_dataset_yaml


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a small YOLO model for jade live product detection.")
    parser.add_argument("--data", default="data/jade_yolo/dataset.yaml", help="YOLO dataset yaml path")
    parser.add_argument("--model", default="yolo11n.pt", help="pretrained YOLO model, e.g. yolo11n.pt or yolov8n.pt")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", default="auto")
    parser.add_argument("--project", default="runs/jade-yolo")
    parser.add_argument("--name", default="jade-yolo")
    parser.add_argument("--output", default="models/jade-yolo.pt")
    parser.add_argument("--device", default="", help="Ultralytics device argument, e.g. 0, cpu, or empty for auto")
    parser.add_argument("--min-train-labels", type=int, default=10)
    parser.add_argument("--min-val-labels", type=int, default=2)
    parser.add_argument("--write-yaml", action="store_true", help="rewrite dataset yaml from the built-in class config")
    args = parser.parse_args()

    data_path = (ROOT / args.data).resolve() if not Path(args.data).is_absolute() else Path(args.data)
    output_path = (ROOT / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)

    if args.write_yaml:
        data_path.parent.mkdir(parents=True, exist_ok=True)
        data_path.write_text(build_jade_dataset_yaml(data_path.parent.relative_to(ROOT)), encoding="utf-8")

    validation_error = validate_dataset(data_path, min_train_labels=args.min_train_labels, min_val_labels=args.min_val_labels)
    if validation_error:
        print(validation_error, file=sys.stderr)
        return 2

    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics is not installed. Run: pip install ultralytics", file=sys.stderr)
        return 2

    print(f"[JLAO] Training jade YOLO model with {len(JADE_YOLO_CLASS_NAMES)} classes")
    print(f"[JLAO] Dataset: {data_path}")
    print(f"[JLAO] Base model: {args.model}")
    print(f"[JLAO] Min labels: train={args.min_train_labels}, val={args.min_val_labels}")

    batch = _normalize_batch_arg(args.batch)
    model = YOLO(args.model)
    result = model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=batch,
        project=str((ROOT / args.project).resolve()),
        name=args.name,
        **({"device": args.device} if args.device else {}),
    )

    save_dir = Path(getattr(result, "save_dir", ""))
    best_weight = save_dir / "weights" / "best.pt"
    if not best_weight.exists():
        print(f"training finished but best.pt was not found under {save_dir}", file=sys.stderr)
        return 3

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_weight, output_path)
    print(f"[JLAO] Saved model: {output_path}")
    return 0


def validate_dataset(data_path: Path, *, min_train_labels: int = 10, min_val_labels: int = 2) -> str:
    if not data_path.exists():
        return f"dataset yaml not found: {data_path}"
    root = _dataset_root_from_yaml(data_path)
    missing_dirs = []
    for relative in ["images/train", "images/val", "labels/train", "labels/val"]:
        path = root / relative
        if not path.exists():
            missing_dirs.append(str(path))
    if missing_dirs:
        return "missing dataset directories:\n" + "\n".join(missing_dirs)
    train_labels = list((root / "labels" / "train").glob("*.txt"))
    val_labels = list((root / "labels" / "val").glob("*.txt"))
    if len(train_labels) < min_train_labels or len(val_labels) < min_val_labels:
        return (
            "training requires at least "
            f"{min_train_labels} train labels and {min_val_labels} val labels "
            f"(found train={len(train_labels)}, val={len(val_labels)})"
        )
    return ""


def _dataset_root_from_yaml(data_path: Path) -> Path:
    for line in data_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("path:"):
            raw = line.split(":", 1)[1].strip().strip("'\"")
            path = Path(raw)
            return path if path.is_absolute() else (ROOT / path).resolve()
    return data_path.parent.resolve()


def _normalize_batch_arg(raw: str) -> int | float:
    value = str(raw).strip().lower()
    if value == "auto":
        return -1
    try:
        parsed = float(value)
    except ValueError as exc:
        raise SystemExit("--batch must be auto, an int, or a float") from exc
    if parsed.is_integer():
        return int(parsed)
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
