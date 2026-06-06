#!/usr/bin/env python3
import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO

MODEL = "runs/detect/jade_train/weights/best.pt"
INPUT_DIR = Path(r"C:\Users\Administrator\Desktop\AI sample")
OUTPUT_DIR = INPUT_DIR / "output"
ROI_X1, ROI_X2 = 0.05, 0.95
ROI_Y1, ROI_Y2 = 0.15, 0.60


def main():
    print(f"Loading: {MODEL}")
    model = YOLO(MODEL)
    OUTPUT_DIR.mkdir(exist_ok=True)

    images = sorted(INPUT_DIR.glob("*.png"))
    print(f"Found {len(images)} images\n")

    for img_path in images:
        img = cv2.imread(str(img_path))
        if img is None:
            continue

        h, w = img.shape[:2]
        rx1, rx2 = int(w * ROI_X1), int(w * ROI_X2)
        ry1, ry2 = int(h * ROI_Y1), int(h * ROI_Y2)
        roi = img[ry1:ry2, rx1:rx2]

        results = model(roi, verbose=False)

        annotated = roi.copy()
        dets = []
        for box in results[0].boxes:
            bx, by, bw, bh = box.xywh[0].cpu().numpy()
            conf = float(box.conf[0])
            x1, y1 = int(bx - bw/2), int(by - bh/2)
            x2, y2 = int(bx + bw/2), int(by + bh/2)
            dets.append(conf)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 165, 255), 3)
            cv2.putText(annotated, f"jade {conf:.2f}", (x1, y1-5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

        cv2.imwrite(str(OUTPUT_DIR / f"det_{img_path.name}"), annotated)

        if dets:
            print(f"  {img_path.name}: {len(dets)} box(es), best conf={max(dets):.2f}")
        else:
            print(f"  {img_path.name}: NO DETECTION")

    print(f"\nDone. Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
