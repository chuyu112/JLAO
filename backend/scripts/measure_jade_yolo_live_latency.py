#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = ROOT / "models" / "jade-yolo.pt"
DEFAULT_ADB = Path(r"D:\scrcpy-win64-v4.0\adb.exe")


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure live adb capture + jade YOLO latency.")
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--adb", default=os.getenv("JLAO_ADB") or str(DEFAULT_ADB if DEFAULT_ADB.exists() else "adb"))
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--interval", type=float, default=0.05)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.15)
    parser.add_argument("--max-det", type=int, default=1)
    parser.add_argument("--area-threshold", type=float, default=0.15)
    parser.add_argument("--roi", nargs=4, type=float, default=(0.05, 0.15, 0.95, 0.55), metavar=("X1", "Y1", "X2", "Y2"))
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    try:
        import torch
    except Exception:
        torch = None

    model_path = Path(args.model)
    if not model_path.is_absolute():
        model_path = ROOT / model_path
    if not model_path.exists():
        print(f"model not found: {model_path}")
        return 2

    device = resolve_device(args.device, torch)
    model = YOLO(str(model_path))

    rows: list[dict[str, Any]] = []
    total_frames = max(1, args.frames) + max(0, args.warmup)
    for index in range(total_frames):
        is_warmup = index < args.warmup
        row = measure_once(model, args, device, torch)
        row["frame"] = index + 1
        row["warmup"] = is_warmup
        if not is_warmup:
            rows.append(row)
        print(
            f"[{'warmup' if is_warmup else 'sample'} #{index + 1}] "
            f"det={row['detections']} capture={row['capture_ms']:.1f}ms "
            f"decode={row['decode_ms']:.1f}ms yolo={row['yolo_ms']:.1f}ms "
            f"total={row['total_ms']:.1f}ms"
        )
        if args.interval > 0:
            time.sleep(args.interval)

    if not rows:
        print("no measured rows")
        return 2

    summary = {
        "model": str(model_path),
        "adb": args.adb,
        "device": device,
        "conf": args.conf,
        "max_det": args.max_det,
        "frames": len(rows),
        "detected_frames": sum(1 for row in rows if row["detections"] > 0),
        "capture_mean_ms": round(mean(row["capture_ms"] for row in rows), 3),
        "decode_mean_ms": round(mean(row["decode_ms"] for row in rows), 3),
        "yolo_mean_ms": round(mean(row["yolo_ms"] for row in rows), 3),
        "yolo_p95_ms": round(percentile([row["yolo_ms"] for row in rows], 95), 3),
        "total_mean_ms": round(mean(row["total_ms"] for row in rows), 3),
        "total_p95_ms": round(percentile([row["total_ms"] for row in rows], 95), 3),
        "fps_mean": round(1000 / mean(row["total_ms"] for row in rows), 3),
    }
    report = {"summary": summary, "rows": rows}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)

    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
        print(f"saved: {output}")
    return 0


def measure_once(model: Any, args: argparse.Namespace, device: str, torch: Any) -> dict[str, Any]:
    total_start = time.perf_counter()

    capture_start = time.perf_counter()
    result = subprocess.run([args.adb, "exec-out", "screencap", "-p"], capture_output=True, timeout=8)
    capture_ms = (time.perf_counter() - capture_start) * 1000
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(f"adb screencap failed: {result.stderr[:200]!r}")

    decode_start = time.perf_counter()
    img = np.frombuffer(result.stdout, dtype=np.uint8)
    frame = cv2.imdecode(img, cv2.IMREAD_COLOR)
    decode_ms = (time.perf_counter() - decode_start) * 1000
    if frame is None:
        raise RuntimeError("failed to decode adb screencap")

    h, w = frame.shape[:2]
    x1, y1, x2, y2 = args.roi
    rx1, rx2 = int(w * x1), int(w * x2)
    ry1, ry2 = int(h * y1), int(h * y2)
    roi = frame[ry1:ry2, rx1:rx2]

    yolo_start = time.perf_counter()
    prediction = model.predict(
        roi,
        imgsz=args.imgsz,
        conf=args.conf,
        max_det=args.max_det,
        device=device,
        verbose=False,
    )[0]
    if torch is not None and device != "cpu" and torch.cuda.is_available():
        torch.cuda.synchronize()
    yolo_ms = (time.perf_counter() - yolo_start) * 1000

    boxes = getattr(prediction, "boxes", None)
    detections = 0
    if boxes is not None:
        roi_h, roi_w = roi.shape[:2]
        for box in boxes:
            _, _, bw, bh = box.xywh[0].cpu().numpy()
            if (bw * bh) / (roi_w * roi_h) >= args.area_threshold:
                detections += 1

    total_ms = (time.perf_counter() - total_start) * 1000
    return {
        "capture_ms": round(capture_ms, 3),
        "decode_ms": round(decode_ms, 3),
        "yolo_ms": round(yolo_ms, 3),
        "total_ms": round(total_ms, 3),
        "detections": detections,
    }


def resolve_device(value: str, torch: Any) -> str:
    if value != "auto":
        return value
    if torch is not None and torch.cuda.is_available():
        return "0"
    return "cpu"


def mean(values: Any) -> float:
    return statistics.mean(list(values))


def percentile(values: list[float], pct: int) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((pct / 100) * len(ordered) + 0.5) - 1))
    return ordered[index]


if __name__ == "__main__":
    raise SystemExit(main())
