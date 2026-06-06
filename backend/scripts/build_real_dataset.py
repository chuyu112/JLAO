#!/usr/bin/env python3
"""build dataset from REAL images only (accurate orange boxes)"""
import cv2
import numpy as np
from pathlib import Path

REAL_DIR = Path(r"C:\Users\Administrator\Desktop\sample")
OUTPUT_DIR = Path("data/jade_real_only")
CLASS_ID = 0

ROI_X1, ROI_X2 = 0.05, 0.95
ROI_Y1, ROI_Y2 = 0.15, 0.60


def detect_orange_box(image_path):
    img = cv2.imread(str(image_path))
    if img is None:
        return None
    h, w = img.shape[:2]
    rx1, rx2 = int(w * ROI_X1), int(w * ROI_X2)
    ry1, ry2 = int(h * ROI_Y1), int(h * ROI_Y2)
    roi_img = img[ry1:ry2, rx1:rx2]

    hsv = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
    lower = np.array([10, 100, 100])
    upper = np.array([25, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    ih, iw = roi_img.shape[:2]
    candidates = []
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        ratio = (bw * bh) / (ih * iw)
        if 0.03 < ratio < 0.90:
            candidates.append({
                "x": (x + bw / 2) / iw,
                "y": (y + bh / 2) / ih,
                "w": bw / iw,
                "h": bh / ih,
            })
    candidates.sort(key=lambda c: c["w"] * c["h"], reverse=True)
    return candidates[0] if candidates else None


def build():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for s in ["train", "val"]:
        (OUTPUT_DIR / "images" / s).mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "labels" / s).mkdir(parents=True, exist_ok=True)

    # only *-*.png (annotated real images)
    annotated = sorted(REAL_DIR.glob("*-*.png"))
    print(f"found {len(annotated)} real annotated images\n")

    all_items = []
    for i, img_path in enumerate(annotated):
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        h, w = img.shape[:2]
        rx1, rx2 = int(w * ROI_X1), int(w * ROI_X2)
        ry1, ry2 = int(h * ROI_Y1), int(h * ROI_Y2)
        roi = img[ry1:ry2, rx1:rx2]

        box = detect_orange_box(img_path)
        if box:
            all_items.append({
                "img": roi,
                "label": f"{CLASS_ID} {box['x']:.6f} {box['y']:.6f} {box['w']:.6f} {box['h']:.6f}\n",
                "name": f"real_{i+1:03d}",
            })
            print(f"  OK {img_path.name} box=({box['x']:.2f},{box['y']:.2f},{box['w']:.2f},{box['h']:.2f})")
        else:
            print(f"  WARN no box in {img_path.name}")

    # 4 train, 2 val (80/20 split)
    n_train = int(len(all_items) * 0.67)  # 4 train, 2 val
    for idx, item in enumerate(all_items):
        split = "train" if idx < n_train else "val"
        cv2.imwrite(str(OUTPUT_DIR / "images" / split / f"{item['name']}.jpg"), item['img'])
        (OUTPUT_DIR / "labels" / split / f"{item['name']}.txt").write_text(item['label'])

    (OUTPUT_DIR / "data.yaml").write_text(
        f"path: {OUTPUT_DIR.absolute().as_posix()}\n"
        f"train: images/train\nval: images/val\nnc: 1\nnames:\n  0: jade\n"
    )
    nt = len(list((OUTPUT_DIR / "images" / "train").glob("*")))
    nv = len(list((OUTPUT_DIR / "images" / "val").glob("*")))
    print(f"\ndataset ready: {OUTPUT_DIR}  train={nt}  val={nv}")


if __name__ == "__main__":
    build()
