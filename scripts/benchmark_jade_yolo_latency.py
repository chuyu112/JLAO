from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark jade YOLO inference latency on local images.")
    parser.add_argument("--model", default="backend/yolov8n.pt", help="YOLO model path or model name")
    parser.add_argument("--images", default="data/jade_ai_batch_01/images", help="Directory containing images")
    parser.add_argument("--device", default="auto", help="'auto', 'cpu', '0', 'cuda:0', etc.")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.15)
    parser.add_argument("--max-det", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--output", default="", help="Optional JSON output path")
    args = parser.parse_args()

    try:
        import torch
        from ultralytics import YOLO
    except Exception as exc:
        print(f"failed to import torch/ultralytics: {exc}")
        return 2

    model_ref = _resolve_model_ref(args.model)
    images = _image_files(Path(args.images))
    if not images:
        print(f"no images found: {args.images}")
        return 2

    device = _resolve_device(args.device, torch)
    t0 = time.perf_counter()
    model = YOLO(model_ref)
    load_ms = (time.perf_counter() - t0) * 1000

    warmup_times: list[float] = []
    for index in range(max(0, args.warmup)):
        path = images[index % len(images)]
        elapsed, _, _ = _predict_once(model, path, device, args, torch)
        warmup_times.append(elapsed)

    rows: list[dict[str, Any]] = []
    for repeat in range(max(1, args.repeat)):
        for path in images:
            elapsed_ms, count, speed = _predict_once(model, path, device, args, torch)
            rows.append(
                {
                    "repeat": repeat + 1,
                    "image": path.name,
                    "elapsed_ms": round(elapsed_ms, 3),
                    "detections": count,
                    "speed": speed,
                }
            )

    elapsed_values = [row["elapsed_ms"] for row in rows]
    summary = {
        "model": model_ref,
        "images_dir": str(Path(args.images).resolve()),
        "device": device,
        "torch": getattr(torch, "__version__", ""),
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
        "imgsz": args.imgsz,
        "conf": args.conf,
        "max_det": args.max_det,
        "image_count": len(images),
        "sample_count": len(rows),
        "model_load_ms": round(load_ms, 3),
        "warmup_ms": [round(value, 3) for value in warmup_times],
        "mean_ms": round(statistics.mean(elapsed_values), 3),
        "median_ms": round(statistics.median(elapsed_values), 3),
        "p95_ms": round(_percentile(elapsed_values, 95), 3),
        "min_ms": round(min(elapsed_values), 3),
        "max_ms": round(max(elapsed_values), 3),
        "fps_mean": round(1000 / statistics.mean(elapsed_values), 3),
        "detections_total": sum(int(row["detections"]) for row in rows),
        "ultralytics_speed_mean": _mean_speed(rows),
    }
    report = {"summary": summary, "rows": rows}

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
        print(f"saved: {output_path}")
    return 0


def _resolve_model_ref(value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return str(path) if path.exists() else value


def _image_files(path: Path) -> list[Path]:
    if not path.is_absolute():
        path = ROOT / path
    files = [item for item in path.iterdir() if item.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    return sorted(files, key=lambda item: (0, int(item.stem)) if item.stem.isdigit() else (1, item.name))


def _resolve_device(value: str, torch: Any) -> str:
    if value != "auto":
        return value
    return "0" if torch.cuda.is_available() else "cpu"


def _predict_once(model: Any, path: Path, device: str, args: argparse.Namespace, torch: Any) -> tuple[float, int, dict[str, float]]:
    start = time.perf_counter()
    result = model.predict(
        source=str(path),
        imgsz=args.imgsz,
        conf=args.conf,
        max_det=args.max_det,
        device=device,
        verbose=False,
    )[0]
    if device != "cpu" and getattr(torch, "cuda", None) is not None and torch.cuda.is_available():
        torch.cuda.synchronize()
    elapsed_ms = (time.perf_counter() - start) * 1000
    boxes = getattr(result, "boxes", None)
    count = len(boxes) if boxes is not None else 0
    speed = {key: round(float(value), 3) for key, value in (getattr(result, "speed", {}) or {}).items()}
    return elapsed_ms, count, speed


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((percentile / 100) * len(ordered) + 0.5) - 1))
    return ordered[index]


def _mean_speed(rows: list[dict[str, Any]]) -> dict[str, float]:
    keys = sorted({key for row in rows for key in (row.get("speed") or {})})
    result: dict[str, float] = {}
    for key in keys:
        values = [float(row["speed"][key]) for row in rows if key in (row.get("speed") or {})]
        if values:
            result[key] = round(statistics.mean(values), 3)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
