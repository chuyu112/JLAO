from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate YOLO confidence on a YOLO image split.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset", default="data/jade_bangle_composite_200_v2")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.001)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--out-dir", default="runs/jade-yolo-confidence")
    parser.add_argument("--name", default="")
    parser.add_argument("--preview-count", type=int, default=50)
    return parser.parse_args()


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def image_files(root: Path, split: str) -> list[Path]:
    path = root / "images" / split
    files = sorted([p for p in path.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}])
    if not files:
        raise FileNotFoundError(f"no images found: {path}")
    return files


def load_yolo() -> Any:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("ultralytics is not installed in this Python environment") from exc
    return YOLO


def box_iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom else 0.0


def read_label(label_path: Path, size: tuple[int, int]) -> list[float] | None:
    if not label_path.exists():
        return None
    line = label_path.read_text(encoding="utf-8").strip().splitlines()
    if not line:
        return None
    parts = line[0].split()
    if len(parts) != 5:
        return None
    _, cx, cy, bw, bh = parts
    width, height = size
    cx_f = float(cx) * width
    cy_f = float(cy) * height
    bw_f = float(bw) * width
    bh_f = float(bh) * height
    return [
        cx_f - bw_f / 2,
        cy_f - bh_f / 2,
        cx_f + bw_f / 2,
        cy_f + bh_f / 2,
    ]


def summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            "mean": 0.0,
            "median": 0.0,
            "min": 0.0,
            "max": 0.0,
            "p10": 0.0,
            "p90": 0.0,
        }
    ordered = sorted(values)

    def pct(p: float) -> float:
        index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * p)))
        return ordered[index]

    return {
        "mean": round(sum(values) / len(values), 4),
        "median": round(statistics.median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "p10": round(pct(0.10), 4),
        "p90": round(pct(0.90), 4),
    }


def draw_prediction_preview(image_path: Path, gt: list[float] | None, pred: dict[str, Any] | None) -> Image.Image:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    if gt:
        draw.rectangle(gt, outline=(255, 0, 0), width=5)
    if pred:
        box = pred["xyxy"]
        draw.rectangle(box, outline=(255, 165, 0), width=4)
    return image


def make_contact_sheet(paths: list[Path], out_path: Path, cols: int = 5, cell: tuple[int, int] = (168, 299)) -> None:
    rows = max(1, (len(paths) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * cell[0], rows * cell[1]), (18, 20, 22))
    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGB")
        image.thumbnail(cell, Image.Resampling.LANCZOS)
        tile = Image.new("RGB", cell, (18, 20, 22))
        tile.paste(image, ((cell[0] - image.width) // 2, (cell[1] - image.height) // 2))
        sheet.paste(tile, ((index % cols) * cell[0], (index // cols) * cell[1]))
    sheet.save(out_path, quality=90, subsampling=1)


def main() -> int:
    args = parse_args()
    dataset_root = resolve(args.dataset)
    model_path = resolve(args.model)
    if not model_path.exists():
        raise FileNotFoundError(f"model not found: {model_path}")
    files = image_files(dataset_root, args.split)

    out_name = args.name or f"{model_path.stem}-{args.split}"
    out_dir = resolve(args.out_dir) / out_name
    out_dir.mkdir(parents=True, exist_ok=True)
    preview_dir = out_dir / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)

    YOLO = load_yolo()
    model = YOLO(str(model_path))

    rows: list[dict[str, Any]] = []
    preview_paths: list[Path] = []
    for image_path in files:
        result = model.predict(
            source=str(image_path),
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.iou,
            verbose=False,
            device="cpu",
        )[0]
        image = Image.open(image_path)
        gt = read_label(dataset_root / "labels" / args.split / f"{image_path.stem}.txt", image.size)

        predictions = []
        if result.boxes is not None:
            for box in result.boxes:
                xyxy = [float(v) for v in box.xyxy[0].tolist()]
                conf = float(box.conf[0].item())
                cls = int(box.cls[0].item())
                iou = box_iou(xyxy, gt) if gt else 0.0
                predictions.append({"xyxy": xyxy, "conf": conf, "cls": cls, "iou": iou})
        predictions.sort(key=lambda row: row["conf"], reverse=True)
        top = predictions[0] if predictions else None
        best_iou = max(predictions, key=lambda row: row["iou"]) if predictions else None
        row = {
            "image": str(image_path.relative_to(ROOT)).replace("\\", "/"),
            "prediction_count": len(predictions),
            "top_conf": round(top["conf"], 6) if top else 0.0,
            "top_cls": top["cls"] if top else "",
            "top_iou": round(top["iou"], 6) if top else 0.0,
            "best_iou": round(best_iou["iou"], 6) if best_iou else 0.0,
            "best_iou_conf": round(best_iou["conf"], 6) if best_iou else 0.0,
            "hit_iou50": bool(best_iou and best_iou["iou"] >= 0.5),
        }
        rows.append(row)

        if len(preview_paths) < args.preview_count:
            preview = draw_prediction_preview(image_path, gt, top)
            preview_path = preview_dir / f"{image_path.stem}.jpg"
            preview.save(preview_path, quality=90, subsampling=1)
            preview_paths.append(preview_path)

    top_conf_values = [float(row["top_conf"]) for row in rows]
    matched_conf_values = [float(row["best_iou_conf"]) for row in rows if bool(row["hit_iou50"])]
    summary = {
        "model": str(model_path),
        "dataset": str(dataset_root),
        "split": args.split,
        "images": len(rows),
        "detected_images": sum(1 for row in rows if int(row["prediction_count"]) > 0),
        "hit_iou50_images": sum(1 for row in rows if bool(row["hit_iou50"])),
        "hit_iou50_rate": round(sum(1 for row in rows if bool(row["hit_iou50"])) / max(1, len(rows)), 4),
        "top_conf": summarize(top_conf_values),
        "matched_iou50_conf": summarize(matched_conf_values),
        "top_conf_ge_050_rate": round(sum(1 for value in top_conf_values if value >= 0.5) / max(1, len(rows)), 4),
        "top_conf_ge_080_rate": round(sum(1 for value in top_conf_values if value >= 0.8) / max(1, len(rows)), 4),
        "matched_conf_ge_080_rate": round(sum(1 for value in matched_conf_values if value >= 0.8) / max(1, len(rows)), 4),
        "csv": str((out_dir / "predictions.csv").resolve()),
        "preview": str((out_dir / "preview_contact_sheet.jpg").resolve()),
    }

    with (out_dir / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    make_contact_sheet(preview_paths, out_dir / "preview_contact_sheet.jpg")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
