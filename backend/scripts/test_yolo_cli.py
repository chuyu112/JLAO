#!/usr/bin/env python3
"""
纯命令行 YOLO 检测：adb 截图 → ROI → YOLO → 打印结果
无 GUI，在当前 bash 环境直接运行。
"""
import time
import sys
import subprocess
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

MODEL_NAME = "yolov8n.pt"
AREA_THRESHOLD = 0.15
ROI_X1, ROI_X2 = 0.05, 0.95
ROI_Y1, ROI_Y2 = 0.15, 0.55


ADB_EXE = r"D:\scrcpy-win64-v4.0\adb.exe"


def capture_adb():
    result = subprocess.run(
        [ADB_EXE, "exec-out", "screencap", "-p"],
        capture_output=True, timeout=5
    )
    if result.returncode != 0:
        return None
    img = np.frombuffer(result.stdout, dtype=np.uint8)
    return cv2.imdecode(img, cv2.IMREAD_COLOR)


def main():
    print(f"加载模型: {MODEL_NAME}")
    model = YOLO(MODEL_NAME)
    print("模型就绪。开始检测...\n")

    frame_count = 0
    while True:
        frame = capture_adb()
        if frame is None:
            print("[截图失败]")
            time.sleep(0.5)
            continue

        h, w = frame.shape[:2]
        rx1, rx2 = int(w * ROI_X1), int(w * ROI_X2)
        ry1, ry2 = int(h * ROI_Y1), int(h * ROI_Y2)
        roi = frame[ry1:ry2, rx1:rx2]

        results = model(roi, verbose=False)
        roi_h, roi_w = roi.shape[:2]

        dets = []
        for box in results[0].boxes:
            bx, by, bw, bh = box.xywh[0].cpu().numpy()
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            name = results[0].names[cls_id]
            ratio = (bw * bh) / (roi_w * roi_h)
            if ratio < AREA_THRESHOLD:
                continue
            dets.append({
                "name": name,
                "conf": conf,
                "ratio": ratio * 100,
                "x": int(bx - bw / 2), "y": int(by - bh / 2),
                "w": int(bw), "h": int(bh)
            })

        frame_count += 1
        if dets:
            print(f"[帧 #{frame_count}] 检测到 {len(dets)} 个目标:")
            for d in dets:
                print(f"  → {d['name']} 置信度={d['conf']:.2f} 占比={d['ratio']:.1f}% 框=({d['x']},{d['y']},{d['w']},{d['h']})")
        else:
            print(f"[帧 #{frame_count}] 无有效目标 (ROI面积占比均<{AREA_THRESHOLD*100:.0f}%)")

        time.sleep(0.3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已退出")
